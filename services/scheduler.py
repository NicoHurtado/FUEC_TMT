"""
Servicio de Tareas Programadas
Ejecuta verificaciones automáticas de documentos
"""
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from database import engine
from config import TIMEZONE, ALERT_HOUR, ALERT_MINUTE


# Instancia global del scheduler
scheduler = AsyncIOScheduler(timezone=TIMEZONE)


async def verificar_documentos_y_enviar_alertas():
    """
    Tarea programada que verifica documentos y envía alertas automáticamente.
    Se ejecuta cada día a las 8:00 AM.
    """
    from services.alert_service import AlertService
    
    print(f"\n{'='*50}")
    print(f"[{datetime.now()}] 🔔 Ejecutando verificación automática de alertas...")
    print(f"{'='*50}")
    
    try:
        with Session(engine) as db:
            alert_service = AlertService(db)
            results = await alert_service.run_automatic_alerts()
            
            print(f"\n📊 Resultados:")
            print(f"   - Conductores verificados: {results['total_conductores']}")
            print(f"   - Con documentos para alertar: {results['con_alertas']}")
            print(f"   - Emails enviados: {results['emails_enviados']}")
            print(f"   - Emails fallidos: {results['emails_fallidos']}")
            print(f"   - Sin email registrado: {results['sin_email']}")
            
            if results['detalles']:
                print(f"\n📧 Detalle de envíos:")
                for d in results['detalles']:
                    status_icon = "✅" if d['estado'] == 'ENVIADO' else "❌" if d['estado'] == 'ERROR' else "⚠️"
                    print(f"   {status_icon} {d['conductor']} ({d.get('email', 'sin email')}) - {d['estado']}")
            
            print(f"\n{'='*50}\n")
            return results
            
    except Exception as e:
        print(f"❌ Error en verificación automática: {e}")
        return None


def iniciar_scheduler():
    """
    Inicia el scheduler con las tareas programadas.
    """
    # Verificación diaria a la hora configurada (hora de Bogotá)
    scheduler.add_job(
        verificar_documentos_y_enviar_alertas,
        trigger=CronTrigger(hour=ALERT_HOUR, minute=ALERT_MINUTE),
        id="verificar_documentos_diario",
        name="Verificación diaria de documentos",
        replace_existing=True
    )
    
    scheduler.start()
    print(f"\n🔔 ALERTAS AUTOMÁTICAS ACTIVADAS")
    print(f"   ✅ Verificación diaria programada: {ALERT_HOUR:02d}:{ALERT_MINUTE:02d} hrs")
    print(f"   📍 Zona horaria: {TIMEZONE}")
    print(f"   📅 Alertas se envían: 30 días, 10 días, el día del vencimiento, y al día siguiente\n")


def detener_scheduler():
    """
    Detiene el scheduler.
    """
    if scheduler.running:
        scheduler.shutdown()
        print("🛑 Scheduler detenido")


def get_proxima_ejecucion():
    """
    Obtiene la próxima ejecución programada.
    """
    job = scheduler.get_job("verificar_documentos_diario")
    if job:
        return job.next_run_time
    return None
