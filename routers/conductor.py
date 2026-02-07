"""
Router de Conductor - Flujo de generación de contratos (Móvil)
"""
from datetime import date
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional

from database import get_session
from models.user import User
from models.document import get_bogota_today
from models.contract import Contract, generate_contract_number
from routers.auth import require_conductor
from config import PDF_DIR

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def validate_conductor_documents(conductor: User) -> dict:
    """
    Validar documentos del conductor y su vehículo asociado.
    Retorna el estado para el semáforo.
    """
    today = get_bogota_today()
    
    status = {
        "ok": True,
        "blocked": False,
        "expired": [],
        "missing": []
    }
    
    # Verificar documentos con fecha
    docs_to_check = [
        ("SOAT", conductor.soat_vigencia),
        ("Tecnomecánica", conductor.tecnomecanica_vigencia),
        ("Licencia", conductor.licencia_vigencia),
    ]
    
    for doc_name, fecha in docs_to_check:
        if not fecha:
            status["missing"].append(doc_name)
            status["ok"] = False
            status["blocked"] = True
        elif fecha < today:
            status["expired"].append({
                "type": doc_name,
                "date": fecha.strftime("%d/%m/%Y")
            })
            status["ok"] = False
            status["blocked"] = True
    
    # Verificar documentos mensuales (Póliza y Administración)
    dia_actual = today.day
    for doc_name, tipo in [("Póliza", "poliza"), ("Administración", "admin")]:
        estado = conductor.get_estado_documento_mensual(tipo)
        if estado == 'vencido':
            status["expired"].append({
                "type": doc_name,
                "date": "Mes actual"
            })
            status["ok"] = False
            status["blocked"] = True
    
    # También verificar que tenga vehículo asignado
    if not conductor.vehiculo_placa:
        status["missing"].append("Vehículo")
        status["ok"] = False
        status["blocked"] = True
    
    return status


# ============== INICIO: VERIFICACIÓN AUTOMÁTICA ==============

@router.get("/", response_class=HTMLResponse)
async def inicio_conductor(
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(require_conductor)
):
    """Inicio: Verificar documentos automáticamente"""
    status = validate_conductor_documents(user)
    today = get_bogota_today()
    
    # Obtener historial de contratos del conductor
    contratos = db.exec(
        select(Contract)
        .where(Contract.conductor_id == user.id)
        .order_by(Contract.created_at.desc())
        .limit(10)
    ).all()
    
    return templates.TemplateResponse(
        "conductor/inicio.html",
        {
            "request": request,
            "user": user,
            "status": status,
            "contratos": contratos,
            "today": today
        }
    )


# ============== CREAR CONTRATO ==============

@router.get("/crear-contrato", response_class=HTMLResponse)
async def crear_contrato_form(
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(require_conductor)
):
    """Formulario para crear contrato"""
    # Validar documentos por seguridad
    status = validate_conductor_documents(user)
    if status["blocked"]:
        return RedirectResponse(url="/app", status_code=302)
    
    today = get_bogota_today()
    
    return templates.TemplateResponse(
        "conductor/crear_contrato.html",
        {
            "request": request,
            "user": user,
            "today": today.isoformat(),
            "today_display": today.strftime("%d/%m/%Y")
        }
    )


@router.post("/crear-contrato")
async def crear_contrato(
    request: Request,
    tipo_servicio: str = Form(...),
    ciudad: str = Form(...),
    fecha_servicio: Optional[date] = Form(None),
    hora_inicio: Optional[str] = Form(None),
    hora_fin: Optional[str] = Form(None),
    signature: str = Form(...),
    db: Session = Depends(get_session),
    user: User = Depends(require_conductor)
):
    """Procesar y generar contrato"""
    from services.pdf_generator import PDFGenerator
    from services.cloudinary_service import upload_pdf_to_cloudinary
    
    # Validar que tiene vehículo
    if not user.vehiculo_placa:
        raise HTTPException(status_code=400, detail="No tiene vehículo asignado")
    
    # Validar firma
    if not signature or signature == "data:,":
        raise HTTPException(status_code=400, detail="Firma requerida")
    
    # Validar datos según tipo de servicio
    if tipo_servicio == "dia" and not fecha_servicio:
        raise HTTPException(status_code=400, detail="Debe seleccionar la fecha del servicio")
    
    if tipo_servicio == "hora" and (not hora_inicio or not hora_fin):
        raise HTTPException(status_code=400, detail="Debe indicar hora de inicio y fin")
    
    # Generar número de contrato
    last_contract = db.exec(
        select(Contract).order_by(Contract.id.desc())
    ).first()
    last_id = last_contract.id if last_contract else 0
    contract_number = generate_contract_number(last_id)
    
    # Crear contrato en BD
    new_contract = Contract(
        contract_number=contract_number,
        conductor_id=user.id,
        tipo_servicio=tipo_servicio,
        fecha_servicio=fecha_servicio if tipo_servicio == "dia" else None,
        hora_inicio=hora_inicio if tipo_servicio == "hora" else None,
        hora_fin=hora_fin if tipo_servicio == "hora" else None,
        ciudad=ciudad,
        signature_base64=signature,
        pdf_path=str(PDF_DIR / f"{contract_number}.pdf")
    )
    db.add(new_contract)
    db.commit()
    db.refresh(new_contract)
    
    # Generar PDF
    pdf_generator = PDFGenerator()
    pdf_path = pdf_generator.generate_contract_pdf_with_signature(
        contract=new_contract,
        conductor=user,
        signature_base64=signature
    )
    
    # Subir PDF a Cloudinary y guardar URL
    cloudinary_url = upload_pdf_to_cloudinary(
        pdf_path,
        public_id=f"contratos/{contract_number}"
    )
    if cloudinary_url:
        new_contract.pdf_url = cloudinary_url
        db.add(new_contract)
        db.commit()
    
    # Redirigir a confirmación
    return RedirectResponse(
        url=f"/app/confirmacion?contract_number={contract_number}",
        status_code=302
    )


@router.get("/confirmacion", response_class=HTMLResponse)
async def confirmation(
    request: Request,
    contract_number: str,
    db: Session = Depends(get_session),
    user: User = Depends(require_conductor)
):
    """Pantalla de confirmación"""
    contract = db.exec(
        select(Contract).where(Contract.contract_number == contract_number)
    ).first()
    
    if not contract:
        return RedirectResponse(url="/app", status_code=302)
    
    return templates.TemplateResponse(
        "conductor/confirmacion.html",
        {
            "request": request,
            "user": user,
            "contract": contract
        }
    )


@router.get("/descargar/{contract_number}")
async def download_pdf(
    contract_number: str,
    db: Session = Depends(get_session),
    user: User = Depends(require_conductor)
):
    """Descargar PDF del contrato"""
    contract = db.exec(
        select(Contract).where(Contract.contract_number == contract_number)
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    
    # Si hay URL de Cloudinary, redirigir allí
    if contract.pdf_url:
        return RedirectResponse(url=contract.pdf_url, status_code=302)
    
    # Fallback a archivo local
    pdf_path = PDF_DIR / f"{contract_number}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    
    return FileResponse(
        path=str(pdf_path),
        filename=f"Contrato_{contract_number}.pdf",
        media_type="application/pdf"
    )
