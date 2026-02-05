"""
Sistema FUEC - Transportes Medellín Travel
Entry point de la aplicación FastAPI
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from contextlib import asynccontextmanager

from database import create_db_and_tables
from routers import auth_router, admin_router, conductor_router
from config import COMPANY_NAME


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y limpieza de la aplicación"""
    # Startup: crear tablas
    create_db_and_tables()
    
    # Iniciar scheduler de alertas automáticas
    from services.scheduler import iniciar_scheduler, detener_scheduler
    iniciar_scheduler()
    
    yield
    
    # Shutdown: detener scheduler
    detener_scheduler()


app = FastAPI(
    title=f"Sistema FUEC - {COMPANY_NAME}",
    description="Sistema de gestión de contratos FUEC y control de documentación vehicular",
    version="1.0.0",
    lifespan=lifespan
)

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Montar directorio de uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Configurar templates
templates = Jinja2Templates(directory="templates")

# Incluir routers
app.include_router(auth_router, prefix="/auth", tags=["Autenticación"])
app.include_router(admin_router, prefix="/admin", tags=["Administrador"])
app.include_router(conductor_router, prefix="/app", tags=["Conductor"])


@app.get("/")
async def root():
    """Redirigir a login"""
    return RedirectResponse(url="/auth/login", status_code=302)


@app.get("/offline")
async def offline(request: Request):
    """Página offline para PWA"""
    return templates.TemplateResponse("offline.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "FUEC System"}


@app.post("/api/alertas/verificar")
async def verificar_alertas_automatico():
    """
    Endpoint para verificación automática de documentos.
    Solo envía alertas cuando faltan exactamente 30, 10, 0 días o venció ayer.
    
    Diseñado para ser llamado diariamente por un cron job (ej: cada día a las 8am).
    
    Ejemplo con curl:
    curl -X POST http://localhost:8000/api/alertas/verificar
    
    Para cron job (ejecutar cada día a las 8am):
    0 8 * * * curl -X POST http://localhost:8000/api/alertas/verificar
    """
    from sqlmodel import Session
    from database import engine
    from services.alert_service import AlertService
    
    with Session(engine) as db:
        alert_service = AlertService(db)
        results = await alert_service.run_automatic_alerts()
    
    return {
        "success": True,
        "message": "Verificación automática completada",
        "fecha": str(alert_service.today),
        "resultados": {
            "total_conductores": results["total_conductores"],
            "con_alertas": results["con_alertas"],
            "emails_enviados": results["emails_enviados"],
            "emails_fallidos": results["emails_fallidos"],
            "sin_email": results["sin_email"]
        },
        "nota": "Solo se envían alertas a 30, 10, 0 días de vencimiento o si venció ayer"
    }
