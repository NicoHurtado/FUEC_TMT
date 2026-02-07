"""
Servicio de generación de uso EXCLUSIVO de PyMuPDF para máxima velocidad y compatibilidad.
"""
from pathlib import Path
from datetime import date
from typing import Optional
import base64
import sys
import os

import fitz  # PyMuPDF
from config import PDF_DIR
from models.contract import Contract
from models.user import User
from models.document import get_bogota_today

# Ruta al template del PDF
TEMPLATE_PATH = Path(__file__).parent.parent / "static" / "img" / "formato_contrato.pdf"

class PDFGenerator:
    """Genera PDFs llenando el formulario con los datos del contrato (Optimizado)"""

    def __init__(self):
        self.template_path = TEMPLATE_PATH
        PDF_DIR.mkdir(exist_ok=True)
        
        if not self.template_path.exists():
            # Rutas alternativas para robustez
            alt_path = Path("/app/static/img/formato_contrato.pdf")
            if alt_path.exists():
                self.template_path = alt_path
            else:
                raise FileNotFoundError(f"Template PDF no encontrado en {self.template_path} ni en {alt_path}")

    def generate_contract_pdf(
        self,
        contract: Contract,
        conductor: User,
        signature_base64: Optional[str] = None,
    ) -> Path:
        """
        Genera el PDF del contrato de la forma más rápida y segura posible.
        1. Llena campos.
        2. Inserta texto faltante.
        3. Inserta firma directamente.
        4. Renderiza a imagen (aplanado real) en un solo paso.
        """
        today = get_bogota_today()
        fecha_formateada = today.strftime("%d/%m/%Y")
        
        # Formato: "Medellín, 12/03/2024"
        ciudad_fecha = f"{contract.ciudad}, {fecha_formateada}"

        if contract.tipo_servicio == "dia":
            servicio_dia = (
                contract.fecha_servicio.strftime("%d/%m/%Y")
                if contract.fecha_servicio
                else ""
            )
            servicio_hora = ""
            hora_inicio = ""
            hora_fin = ""
        else:
            servicio_dia = ""
            servicio_hora = "X"
            hora_inicio = contract.hora_inicio or ""
            hora_fin = contract.hora_fin or ""

        # Mapeo de datos para campos del PDF
        field_data = {
            "numero": str(contract.contract_number),
            "marca": str(conductor.vehiculo_marca or ""),
            "color": str(conductor.vehiculo_color or ""),
            "placa": str(conductor.vehiculo_placa or ""),
            "modelo": str(conductor.vehiculo_modelo or ""),
            "conductor": str(conductor.full_name),
            "cedula": str(conductor.cedula or ""),
            "servicio_dia": servicio_dia,
            "servicio_hora": servicio_hora,
            "hora_inicio": hora_inicio,
            "hora_fin": hora_fin,
            "hora_final": hora_fin,
            "nombre_arrendador": str(contract.nombre_arrendador or ""),
            "documento_arrendador": str(contract.documento_arrendador or ""),
        }

        try:
            # 1) Abrir documento
            doc = fitz.open(str(self.template_path))
            page = doc[0]  # Asumimos página única

            # 2) Llenar campos de formulario (Widgets)
            for widget in page.widgets():
                if widget.field_name in field_data:
                    widget.field_value = field_data[widget.field_name]
                    widget.update()  # Reflejar cambios visualmente

            # 3) Insertar texto 'Ciudad y fecha' (Ya que el campo no existe)
            # Coord aproximada: X=165, Y=450 (encima de la firma)
            page.insert_text(
                (165, 450),
                ciudad_fecha,
                fontsize=11,
                fontname="helv",
                color=(0, 0, 0)
            )

            # 4) Insertar Firma (Si existe)
            if signature_base64 and signature_base64.startswith("data:image"):
                try:
                    # Decodificar base64 a bytes
                    header, encoded = signature_base64.split(",", 1)
                    sig_data = base64.b64decode(encoded)
                    
                    # Definir área de firma
                    # Buscamos widget o anotación 'firma' primero
                    firma_rect = None
                    
                    # Intentar encontrar widget 'firma'
                    for widget in page.widgets():
                        if widget.field_name == "firma":
                            firma_rect = widget.rect
                            break
                    
                    # Si no, buscar anotación
                    if not firma_rect:
                        for annot in page.annots():
                            if annot.info.get("title") == "firma":
                                firma_rect = annot.rect
                                break
                    
                    # Fallback visual si no se encuentra
                    if not firma_rect:
                        # Coordenadas estimadas PyMuPDF (Top-Left 0,0)
                        # X=85..310
                        # Y=460..535 (Encima de nombre_arrendador Y=538)
                        firma_rect = fitz.Rect(85, 460, 310, 535)

                    # Insertar imagen en el rectángulo
                    page.insert_image(firma_rect, stream=sig_data)
                    
                except Exception as e:
                    print(f"⚠ Error insertando firma: {e}")

            # 5) Aplanado final vía Rasterización (Imagen)
            # Optimización: Matrix(2.0, 2.0) = ~150 DPI.
            # - Suficiente para leer y firmar.
            # - Mucho más rápido que 3.0 (300 DPI).
            output_path = PDF_DIR / f"{contract.contract_number}.pdf"
            
            flat_doc = fitz.open()
            
            for p in doc:
                # Renderizar a imagen
                pix = p.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
                
                # Nueva página del tamaño de la imagen
                new_page = flat_doc.new_page(width=p.rect.width, height=p.rect.height)
                new_page.insert_image(p.rect, pixmap=pix)

            # Guardar optimizado
            flat_doc.save(str(output_path), garbage=4, deflate=True)
            flat_doc.close()
            doc.close()

            print(f"✓ PDF generado (Optimizado): {output_path}")
            return output_path

        except Exception as e:
            print(f"ERROR CRÍTICO generando PDF: {e}")
            raise e

    def generate_contract_pdf_with_signature(
        self,
        contract: Contract,
        conductor: User,
        signature_base64: str,
    ) -> Path:
        """Wrapper para mantener compatibilidad con llamadas existentes"""
        return self.generate_contract_pdf(
            contract, conductor, signature_base64=signature_base64
        )


def generate_pdf(contract: Contract, conductor: User) -> tuple:
    """Función helper principal usada por el router"""
    from services.cloudinary_service import upload_pdf_to_cloudinary
    
    generator = PDFGenerator()
    local_path = generator.generate_contract_pdf_with_signature(
        contract,
        conductor,
        contract.signature_base64,
    )
    
    # Subir a Cloudinary
    cloudinary_url = upload_pdf_to_cloudinary(
        local_path, 
        public_id=f"contratos/{contract.contract_number}"
    )
    
    return local_path, cloudinary_url

