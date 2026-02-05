"""
Router de Administrador - Panel de Control
"""
from datetime import date, datetime, time
from typing import Optional, List
from fastapi import APIRouter, Request, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from sqlalchemy import func
import pytz
import shutil
import uuid
from pathlib import Path

from database import get_session
from models.user import User, UserCreate
from models.document import get_bogota_today
from models.contract import Contract
from routers.auth import require_admin, generate_access_code
from config import TIMEZONE, PDF_DIR, UPLOADS_DIR

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_conductor_status(conductor: User) -> dict:
    """Obtener estado de documentos de un conductor y su vehículo"""
    today = get_bogota_today()
    
    status = {
        "ok": True,
        "expired": [],
        "missing": [],
        "warning": []
    }
    
    # Verificar documentos del vehículo
    docs_to_check = [
        ("SOAT", conductor.soat_vigencia),
        ("Tecnomecánica", conductor.tecnomecanica_vigencia),
        ("Póliza", conductor.poliza_vigencia),
        ("Tarjeta de Operación", conductor.tarjeta_operacion_vigencia),
        ("Licencia", conductor.licencia_vigencia),
    ]
    
    for doc_name, fecha in docs_to_check:
        if not fecha:
            status["missing"].append(doc_name)
            status["ok"] = False
        elif fecha < today:
            status["expired"].append({
                "type": doc_name,
                "date": fecha.strftime("%d/%m/%Y")
            })
            status["ok"] = False
        elif (fecha - today).days <= 30:
            status["warning"].append({
                "type": doc_name,
                "date": fecha.strftime("%d/%m/%Y"),
                "days": (fecha - today).days
            })
    
    return status


def save_image_to_cloud(upload_file: UploadFile, subfolder: str) -> Optional[str]:
    """
    Sube imagen a Cloudinary y retorna la URL.
    
    Args:
        upload_file: Archivo subido (FastAPI UploadFile)
        subfolder: Subcarpeta en Cloudinary (ej: "conductores", "vehiculos")
        
    Returns:
        URL pública de la imagen o None si falla/no hay archivo
    """
    if not upload_file or not upload_file.filename:
        return None
        
    from services.cloudinary_service import upload_image_to_cloudinary
    
    # Subir a carpeta especifica: "fotos_usuarios/conductores", etc.
    folder_path = f"fotos_usuarios/{subfolder}"
    
    # upload_file.file es un objeto file-like compatible
    return upload_image_to_cloudinary(upload_file.file, folder=folder_path)


# ============== DASHBOARD ==============

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_session), user: User = Depends(require_admin)):
    """Dashboard principal del administrador"""
    # Estadísticas
    conductores = db.exec(select(User).where(User.role == "conductor")).all()
    contratos = db.exec(select(Contract)).all()
    
    # Conductores con problemas de documentos
    conductores_problema = 0
    for c in conductores:
        status = get_conductor_status(c)
        if not status["ok"]:
            conductores_problema += 1
    
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": user,
            "stats": {
                "conductores": len(conductores),
                "conductores_activos": len([c for c in conductores if c.is_active]),
                "conductores_problema": conductores_problema,
                "contratos": len(contratos)
            }
        }
    )


# ============== CONDUCTORES ==============

@router.get("/conductores", response_class=HTMLResponse)
async def list_conductores(
    request: Request, 
    nuevo: str = None,
    db: Session = Depends(get_session), 
    user: User = Depends(require_admin)
):
    """Lista de conductores con estado de documentos"""
    conductores = db.exec(
        select(User).where(User.role == "conductor").order_by(User.full_name)
    ).all()
    
    # Agregar estado a cada conductor
    conductores_data = []
    for c in conductores:
        status = get_conductor_status(c)
        conductores_data.append({
            "conductor": c,
            "status": status
        })
    
    return templates.TemplateResponse(
        "admin/conductores.html",
        {
            "request": request,
            "user": user,
            "conductores": conductores_data,
            "codigo_nuevo": nuevo
        }
    )


@router.get("/conductores/nuevo", response_class=HTMLResponse)
async def nuevo_conductor_form(
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Formulario para crear nuevo conductor"""
    return templates.TemplateResponse(
        "admin/conductor_form.html",
        {
            "request": request,
            "user": user,
            "conductor": None,
            "modo": "crear"
        }
    )


@router.post("/conductores")
async def create_conductor(
    request: Request,
    # Datos personales
    full_name: str = Form(...),
    cedula: str = Form(...),
    celular: str = Form(None),
    email: str = Form(None),
    # Datos de licencia
    licencia_fecha_expedicion: date = Form(None),
    licencia_restricciones: str = Form(None),
    licencia_categoria: str = Form(None),
    licencia_vigencia: date = Form(None),
    licencia_servicio: str = Form(None),
    # Datos del vehículo
    vehiculo_placa: str = Form(...),
    vehiculo_marca: str = Form(None),
    vehiculo_modelo: str = Form(None),
    vehiculo_color: str = Form(None),
    # Vigencias del vehículo
    soat_vigencia: date = Form(None),
    tecnomecanica_vigencia: date = Form(None),
    poliza_vigencia: date = Form(None),
    tarjeta_operacion_vigencia: date = Form(None),
    # Fotos
    foto_conductor: UploadFile = File(None),
    foto_vehiculo: UploadFile = File(None),
    foto_licencia: UploadFile = File(None),
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Crear nuevo conductor con vehículo asociado"""
    # Generar código único
    while True:
        access_code = generate_access_code(6)
        existing = db.exec(select(User).where(User.access_code == access_code)).first()
        if not existing:
            break
    
    # Normalizar placa
    vehiculo_placa = vehiculo_placa.upper().strip() if vehiculo_placa else None
    
    # Guardar fotos en Cloudinary
    foto_conductor_path = save_image_to_cloud(foto_conductor, "conductores") if foto_conductor else None
    foto_vehiculo_path = save_image_to_cloud(foto_vehiculo, "vehiculos") if foto_vehiculo else None
    foto_licencia_path = save_image_to_cloud(foto_licencia, "licencias") if foto_licencia else None
    
    # Crear conductor
    new_conductor = User(
        access_code=access_code,
        role="conductor",
        is_active=True,
        # Datos personales
        full_name=full_name,
        cedula=cedula,
        celular=celular,
        email=email,
        # Fotos
        foto_conductor=foto_conductor_path,
        foto_vehiculo=foto_vehiculo_path,
        foto_licencia=foto_licencia_path,
        # Licencia
        licencia_fecha_expedicion=licencia_fecha_expedicion,
        licencia_restricciones=licencia_restricciones,
        licencia_categoria=licencia_categoria,
        licencia_vigencia=licencia_vigencia,
        licencia_servicio=licencia_servicio,
        # Vehículo
        vehiculo_placa=vehiculo_placa,
        vehiculo_marca=vehiculo_marca,
        vehiculo_modelo=vehiculo_modelo,
        vehiculo_color=vehiculo_color,
        # Vigencias
        soat_vigencia=soat_vigencia,
        tecnomecanica_vigencia=tecnomecanica_vigencia,
        poliza_vigencia=poliza_vigencia,
        tarjeta_operacion_vigencia=tarjeta_operacion_vigencia,
    )
    db.add(new_conductor)
    db.commit()
    db.refresh(new_conductor)
    
    return RedirectResponse(url=f"/admin/conductores?nuevo={access_code}", status_code=302)


@router.get("/conductores/{conductor_id}", response_class=HTMLResponse)
async def ver_conductor(
    request: Request,
    conductor_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Ver detalles de un conductor"""
    conductor = db.get(User, conductor_id)
    if not conductor or conductor.role != "conductor":
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    
    status = get_conductor_status(conductor)
    today = get_bogota_today()
    
    return templates.TemplateResponse(
        "admin/conductor_detalle.html",
        {
            "request": request,
            "user": user,
            "conductor": conductor,
            "status": status,
            "today": today
        }
    )


@router.get("/conductores/{conductor_id}/editar", response_class=HTMLResponse)
async def editar_conductor_form(
    request: Request,
    conductor_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Formulario para editar conductor"""
    conductor = db.get(User, conductor_id)
    if not conductor or conductor.role != "conductor":
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    
    return templates.TemplateResponse(
        "admin/conductor_form.html",
        {
            "request": request,
            "user": user,
            "conductor": conductor,
            "modo": "editar"
        }
    )


@router.post("/conductores/{conductor_id}/editar")
async def update_conductor(
    request: Request,
    conductor_id: int,
    # Datos personales
    full_name: str = Form(...),
    cedula: str = Form(...),
    celular: str = Form(None),
    email: str = Form(None),
    # Datos de licencia
    licencia_fecha_expedicion: date = Form(None),
    licencia_restricciones: str = Form(None),
    licencia_categoria: str = Form(None),
    licencia_vigencia: date = Form(None),
    licencia_servicio: str = Form(None),
    # Datos del vehículo
    vehiculo_placa: str = Form(...),
    vehiculo_marca: str = Form(None),
    vehiculo_modelo: str = Form(None),
    vehiculo_color: str = Form(None),
    # Vigencias del vehículo
    soat_vigencia: date = Form(None),
    tecnomecanica_vigencia: date = Form(None),
    poliza_vigencia: date = Form(None),
    tarjeta_operacion_vigencia: date = Form(None),
    # Fotos (opcionales en edición)
    foto_conductor: UploadFile = File(None),
    foto_vehiculo: UploadFile = File(None),
    foto_licencia: UploadFile = File(None),
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Actualizar conductor"""
    conductor = db.get(User, conductor_id)
    if not conductor or conductor.role != "conductor":
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    
    # Actualizar datos
    conductor.full_name = full_name
    conductor.cedula = cedula
    conductor.celular = celular
    conductor.email = email
    conductor.licencia_fecha_expedicion = licencia_fecha_expedicion
    conductor.licencia_restricciones = licencia_restricciones
    conductor.licencia_categoria = licencia_categoria
    conductor.licencia_vigencia = licencia_vigencia
    conductor.licencia_servicio = licencia_servicio
    conductor.vehiculo_placa = vehiculo_placa.upper().strip() if vehiculo_placa else None
    conductor.vehiculo_marca = vehiculo_marca
    conductor.vehiculo_modelo = vehiculo_modelo
    conductor.vehiculo_color = vehiculo_color
    conductor.soat_vigencia = soat_vigencia
    conductor.tecnomecanica_vigencia = tecnomecanica_vigencia
    conductor.poliza_vigencia = poliza_vigencia
    conductor.tarjeta_operacion_vigencia = tarjeta_operacion_vigencia
    
    # Actualizar fotos solo si se subieron nuevas
    if foto_conductor and foto_conductor.filename:
        conductor.foto_conductor = save_image_to_cloud(foto_conductor, "conductores")
    if foto_vehiculo and foto_vehiculo.filename:
        conductor.foto_vehiculo = save_image_to_cloud(foto_vehiculo, "vehiculos")
    if foto_licencia and foto_licencia.filename:
        conductor.foto_licencia = save_image_to_cloud(foto_licencia, "licencias")
    
    db.add(conductor)
    db.commit()
    
    return RedirectResponse(url=f"/admin/conductores/{conductor_id}", status_code=302)


@router.put("/conductores/{conductor_id}/toggle", response_class=HTMLResponse)
async def toggle_conductor(
    request: Request,
    conductor_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Activar/Desactivar conductor (HTMX)"""
    conductor = db.get(User, conductor_id)
    if not conductor or conductor.role != "conductor":
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    
    conductor.is_active = not conductor.is_active
    db.add(conductor)
    db.commit()
    db.refresh(conductor)
    
    status = get_conductor_status(conductor)
    
    # Retornar HTML parcial para HTMX
    return templates.TemplateResponse(
        "partials/conductor_row.html",
        {"request": request, "item": {"conductor": conductor, "status": status}}
    )


@router.post("/conductores/{conductor_id}/regenerar-codigo")
async def regenerar_codigo_conductor(
    conductor_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Regenerar código de acceso del conductor"""
    conductor = db.get(User, conductor_id)
    if not conductor or conductor.role != "conductor":
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    
    # Generar nuevo código único
    while True:
        new_code = generate_access_code(6)
        existing = db.exec(select(User).where(User.access_code == new_code)).first()
        if not existing:
            break
    
    conductor.access_code = new_code
    db.add(conductor)
    db.commit()
    
    return RedirectResponse(url=f"/admin/conductores?nuevo={new_code}", status_code=302)


@router.delete("/conductores/{conductor_id}", response_class=HTMLResponse)
async def delete_conductor(
    request: Request,
    conductor_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Eliminar conductor (HTMX)"""
    conductor = db.get(User, conductor_id)
    if not conductor or conductor.role != "conductor":
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    
    # Eliminar conductor
    db.delete(conductor)
    db.commit()
    
    # Retornar vacío para que HTMX elimine la fila
    return ""


@router.post("/conductores/{conductor_id}/eliminar")
async def delete_conductor_post(
    conductor_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Eliminar conductor (POST fallback)"""
    conductor = db.get(User, conductor_id)
    if not conductor or conductor.role != "conductor":
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    
    db.delete(conductor)
    db.commit()
    
    return RedirectResponse(url="/admin/conductores", status_code=302)


# ============== ALERTAS DE DOCUMENTOS ==============

@router.get("/alertas", response_class=HTMLResponse)
async def alertas_page(
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Página de gestión de alertas de documentos"""
    from services.alert_service import AlertService
    from services.scheduler import get_proxima_ejecucion
    
    alert_service = AlertService(db)
    
    # Obtener conductores con alertas
    conductores = db.exec(
        select(User).where(User.role == "conductor").order_by(User.full_name)
    ).all()
    
    conductores_alertas = []
    for c in conductores:
        alerts = alert_service.get_conductor_alerts(c)
        if alerts:
            conductores_alertas.append({
                "conductor": c,
                "alertas": alerts,
                "tiene_email": bool(c.email)
            })
    
    # Obtener próxima ejecución programada
    proxima_ejecucion = get_proxima_ejecucion()
    
    return templates.TemplateResponse(
        "admin/alertas.html",
        {
            "request": request,
            "user": user,
            "conductores_alertas": conductores_alertas,
            "total_alertas": len(conductores_alertas),
            "proxima_ejecucion": proxima_ejecucion
        }
    )


@router.post("/alertas/enviar-todas")
async def enviar_todas_alertas(
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Enviar alertas a todos los conductores con documentos vencidos/por vencer"""
    from services.alert_service import AlertService
    
    alert_service = AlertService(db)
    results = await alert_service.check_all_conductors()
    
    # Guardar resultado en session o query param
    mensaje = f"Enviados: {results['emails_enviados']}, Fallidos: {results['emails_fallidos']}, Sin email: {results['sin_email']}"
    
    return RedirectResponse(
        url=f"/admin/alertas?msg={mensaje}",
        status_code=302
    )


@router.post("/alertas/enviar/{conductor_id}")
async def enviar_alerta_conductor(
    conductor_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Enviar alerta a un conductor específico"""
    from services.alert_service import AlertService
    
    alert_service = AlertService(db)
    result = await alert_service.send_alert_to_conductor(conductor_id)
    
    if result["success"]:
        msg = f"Alerta enviada a {result['conductor']}"
    else:
        msg = f"Error: {result.get('error', 'Error desconocido')}"
    
    return RedirectResponse(
        url=f"/admin/alertas?msg={msg}",
        status_code=302
    )


# ============== HISTORIAL ==============

@router.get("/historial", response_class=HTMLResponse)
async def historial(
    request: Request,
    page: int = 1,
    page_size: int = 10,
    q: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    tipo_servicio: str | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    """
    Historial de contratos generados (paginado y filtrable).
    """
    # Query base con join a conductor
    stmt = (
        select(Contract, User)
        .join(User, User.id == Contract.conductor_id)
    )

    # Filtro de texto libre (número, conductor, placa, ciudad)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (Contract.contract_number.ilike(like))
            | (User.full_name.ilike(like))
            | (User.vehiculo_placa.ilike(like))
            | (Contract.ciudad.ilike(like))
        )

    # Filtro por tipo de servicio
    if tipo_servicio in ("dia", "hora"):
        stmt = stmt.where(Contract.tipo_servicio == tipo_servicio)

    # Filtro por rango de fechas (fecha de creación del contrato)
    if fecha_desde:
        desde_dt = datetime.combine(fecha_desde, time.min)
        stmt = stmt.where(Contract.created_at >= desde_dt)
    if fecha_hasta:
        hasta_dt = datetime.combine(fecha_hasta, time.max)
        stmt = stmt.where(Contract.created_at <= hasta_dt)

    # Total para paginación
    count_stmt = (
        select(func.count())
        .select_from(stmt.subquery())
    )
    total = db.exec(count_stmt).one()

    # Orden y paginación
    stmt = stmt.order_by(Contract.created_at.desc())
    page = max(page, 1)
    page_size = max(min(page_size, 100), 5)
    offset = (page - 1) * page_size

    results = db.exec(stmt.offset(offset).limit(page_size)).all()

    contracts_data = []
    for contract, conductor in results:
        contracts_data.append(
            {
                "contract": contract,
                "conductor": conductor,
            }
        )

    total_pages = max((total + page_size - 1) // page_size, 1)

    return templates.TemplateResponse(
        "admin/historial.html",
        {
            "request": request,
            "user": user,
            "contracts": contracts_data,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "page_size": page_size,
            "q": q or "",
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "tipo_servicio": tipo_servicio or "",
        },
    )


@router.get("/historial/{contract_id}/pdf")
async def download_contract_pdf(
    contract_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(require_admin)
):
    """Descargar PDF de contrato"""
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    
    # Si hay URL de Cloudinary, redirigir allí
    if contract.pdf_url:
        return RedirectResponse(url=contract.pdf_url, status_code=302)
    
    # Fallback a archivo local
    pdf_path = PDF_DIR / f"{contract.contract_number}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Archivo PDF no encontrado")
    
    return FileResponse(
        path=str(pdf_path),
        filename=f"{contract.contract_number}.pdf",
        media_type="application/pdf"
    )
