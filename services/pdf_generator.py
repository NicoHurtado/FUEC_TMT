"""
Servicio de generación de PDF - Llena formulario PDF con datos del contrato
"""
from pathlib import Path
from datetime import date
from typing import Optional
import io
import base64

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
from PIL import Image
from fillpdf import fillpdfs
import fitz  # PyMuPDF para aplanar totalmente el formulario
import sys
import os

from config import PDF_DIR
from models.contract import Contract
from models.user import User
from models.document import get_bogota_today


# Ruta al template del PDF (formato rellenable)
TEMPLATE_PATH = Path(__file__).parent.parent / "static" / "img" / "formato_contrato.pdf"

# Posición del recuadro de firma (Arrendador), debajo de "Ciudad y fecha": [llx, lly, urx, ury] en puntos PDF (origen abajo-izq)
# Más lly/ury = firma más arriba.
FIRMA_RECT_DEFAULT = (85, 78, 310, 148)


def _get_firma_rect(reader: PdfReader) -> tuple:
    """Obtiene el rectángulo del campo 'firma' del PDF. Si no existe, devuelve default."""
    try:
        page = reader.pages[0]
        if "/Annots" not in page:
            return FIRMA_RECT_DEFAULT
        annots = page["/Annots"]
        for ref in annots:
            annot = ref.get_object() if hasattr(ref, "get_object") else ref
            if not hasattr(annot, "get"):
                continue
            name = annot.get("/T")
            if name and str(name) == "firma":
                rect = annot.get("/Rect")
                if rect and len(rect) >= 4:
                    return (float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3]))
    except Exception:
        pass
    return FIRMA_RECT_DEFAULT


def _create_signature_overlay_pdf(
    signature_base64: str,
    page_width: float,
    page_height: float,
    rect: tuple,
) -> bytes:
    """
    Crea un PDF de una página con la imagen de la firma en el rectángulo dado.
    rect = (llx, lly, urx, ury) en puntos PDF (origen abajo-izquierda).
    """
    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=(page_width, page_height))
    c.setPageSize((page_width, page_height))

    try:
        header, encoded = signature_base64.split(",", 1)
        img_data = base64.b64decode(encoded)
    except Exception:
        return buffer.getvalue()

    llx, lly, urx, ury = rect
    w = urx - llx
    h = ury - lly
    if w <= 0 or h <= 0:
        return buffer.getvalue()

    # Abrir imagen con PIL
    img = Image.open(io.BytesIO(img_data))
    img_w, img_h = img.size

    # Evitar que salga cuadro negro: si tiene transparencia (RGBA/P), compositar sobre fondo blanco
    if img.mode in ("RGBA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Guardar como RGB en memoria para ReportLab
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    # Escalar para caber en el rect manteniendo proporción
    scale = min(w / img_w, h / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale
    # Centrar en el rect
    x = llx + (w - draw_w) / 2
    y = lly + (h - draw_h) / 2

    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(img_buffer), x, y, width=draw_w, height=draw_h)
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


class PDFGenerator:
    """Genera PDFs llenando el formulario con los datos del contrato"""

    def __init__(self):
        self.template_path = TEMPLATE_PATH
        PDF_DIR.mkdir(exist_ok=True)
        
        # Validar que el template existe
        if not self.template_path.exists():
            # Intentar rutas alternativas
            alt_path = Path("/app/static/img/formato_contrato.pdf")
            if alt_path.exists():
                self.template_path = alt_path
                print(f"✓ Usando ruta alternativa: {alt_path}")
            else:
                error_msg = (
                    f"ERROR: Template PDF no encontrado.\n"
                    f"Ruta esperada: {self.template_path}\n"
                    f"Ruta absoluta: {self.template_path.absolute()}\n"
                    f"Existe: {self.template_path.exists()}\n"
                    f"Directorio padre: {self.template_path.parent}\n"
                    f"Contenido del directorio: {list(self.template_path.parent.iterdir()) if self.template_path.parent.exists() else 'No existe'}\n"
                    f"Working directory: {Path.cwd()}\n"
                    f"Ruta alternativa: {alt_path} (existe: {alt_path.exists()})"
                )
                print(error_msg)
                raise FileNotFoundError(error_msg)
        else:
            print(f"✓ Template PDF encontrado: {self.template_path}")

    def generate_contract_pdf(
        self,
        contract: Contract,
        conductor: User,
        signature_base64: Optional[str] = None,
    ) -> Path:
        """
        Llena el PDF del contrato con los datos proporcionados.
        1) Rellena el formulario con fillpdf (write_fillable_pdf)
        2) Aplana el formulario con PyMuPDF (queda NO editable)
        3) Superpone la firma como imagen.
        """
        today = get_bogota_today()
        fecha_formateada = today.strftime("%d/%m/%Y")
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

        # Datos que coinciden con los nombres de campos del PDF
        field_data = {
            "numero": contract.contract_number,
            "marca": conductor.vehiculo_marca or "",
            "color": conductor.vehiculo_color or "",
            "placa": conductor.vehiculo_placa or "",
            "modelo": conductor.vehiculo_modelo or "",
            "conductor": conductor.full_name,
            "cedula": conductor.cedula or "",
            "servicio_dia": servicio_dia,
            "servicio_hora": servicio_hora,
            "hora_inicio": hora_inicio,
            "hora_fin": hora_fin,
            "ciudad_fecha": ciudad_fecha,
            "arrendatario": "Transportes Medellín Travel S.A.S",
        }

        # 1) Llenar el formulario con fillpdfs (PDF aún editable)
        tmp_filled = PDF_DIR / f"{contract.contract_number}_filled.pdf"
        fillpdfs.write_fillable_pdf(
            str(self.template_path),
            str(tmp_filled),
            field_data,
        )

        # 2) Aplanar el PDF usando PyMuPDF
        tmp_flat = PDF_DIR / f"{contract.contract_number}_flat.pdf"
        
        # Context manager para silenciar stderr (errores de C de MuPDF)
        class StderrSilencer:
            def __enter__(self):
                self._original_stderr = sys.stderr
                self._null = open(os.devnull, 'w')
                sys.stderr = self._null
                # También intentar redirigir el FD 2 si es posible
                try:
                    self._original_stderr_fd = os.dup(2)
                    os.dup2(self._null.fileno(), 2)
                except Exception:
                    self._original_stderr_fd = None

            def __exit__(self, exc_type, exc_val, exc_tb):
                sys.stderr = self._original_stderr
                if self._original_stderr_fd is not None:
                    os.dup2(self._original_stderr_fd, 2)
                    os.close(self._original_stderr_fd)
                self._null.close()

        try:
            with StderrSilencer():
                doc = fitz.open(str(tmp_filled))
                for page in doc:
                    # Intentar transformar los widgets a texto o simplemente eliminarlos visualmente
                    # Para simplificar y evitar errores, recorreremos y trataremos de hacerlos readonly
                    # Si falla, simplemente continuamos.
                    for widget in page.widgets():
                        try:
                            widget.field_flags |= fitz.PDF_FIELD_IS_READ_ONLY
                            widget.update() 
                        except Exception:
                            pass
                
                # Guardar limpio
                doc.save(str(tmp_flat), garbage=4, deflate=True)
                doc.close()
                
        except Exception:
            # Fallback silencioso: copiar el archivo lleno original
            import shutil
            shutil.copy(str(tmp_filled), str(tmp_flat))

        # 3) Cargar el PDF ya aplanado y, si hay firma, superponerla como imagen
        writer = PdfWriter()
        base_reader = PdfReader(str(tmp_flat))
        writer.append(base_reader)

        # Obtener dimensiones de la página
        template_reader = PdfReader(str(self.template_path))
        mb = template_reader.pages[0].mediabox
        page_width = float(mb.width)
        page_height = float(mb.height)
        
        # Superponer firma del arrendador (conductor)
        if signature_base64 and signature_base64.startswith("data:image"):
            try:
                rect = _get_firma_rect(template_reader)
                overlay_pdf_bytes = _create_signature_overlay_pdf(
                    signature_base64, page_width, page_height, rect
                )
                overlay_reader = PdfReader(io.BytesIO(overlay_pdf_bytes))
                writer.pages[0].merge_page(overlay_reader.pages[0])
            except Exception as e:
                print(f"⚠ No se pudo superponer la firma: {e}")

        output_path = PDF_DIR / f"{contract.contract_number}.pdf"
        with open(output_path, "wb") as output_file:
            writer.write(output_file)

        print(f"✓ PDF generado: {output_path}")
        return output_path

    def generate_contract_pdf_with_signature(
        self,
        contract: Contract,
        conductor: User,
        signature_base64: str,
    ) -> Path:
        """Genera el PDF del contrato e inserta la firma en el campo correspondiente."""
        output_path = self.generate_contract_pdf(
            contract, conductor, signature_base64=signature_base64
        )

        if signature_base64 and signature_base64.startswith("data:image"):
            try:
                header, encoded = signature_base64.split(",", 1)
                signature_data = base64.b64decode(encoded)
                signature_path = PDF_DIR / f"{contract.contract_number}_firma.png"
                with open(signature_path, "wb") as f:
                    f.write(signature_data)
                print(f"✓ Firma guardada: {signature_path}")
            except Exception as e:
                print(f"⚠ Error guardando firma: {e}")

        return output_path


def generate_pdf(contract: Contract, conductor: User) -> tuple:
    """
    Genera PDF del contrato con firma y lo sube a Cloudinary.
    
    Returns:
        tuple: (local_path: Path, cloudinary_url: str | None)
    """
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
