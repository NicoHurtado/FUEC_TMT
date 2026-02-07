"""
Servicio de Alertas de Documentos
Verifica vencimientos y envía notificaciones a conductores
"""
from datetime import date
from typing import List, Dict
from sqlmodel import Session, select

from models.user import User
from models.document import get_bogota_today
from services.email_service import EmailService
from config import ALERT_DAYS


class AlertService:
    """Servicio para verificar documentos y enviar alertas"""
    
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()
        self.today = get_bogota_today()
    
    def get_conductor_alerts(self, conductor: User, include_all: bool = True) -> List[Dict]:
        """
        Obtiene las alertas de documentos de un conductor.
        
        Args:
            conductor: Usuario conductor
            include_all: Si True, incluye todos los documentos con alertas.
                        Si False, solo incluye los que coinciden exactamente con ALERT_DAYS.
        
        Returns:
            Lista de alertas con información del documento
        """
        alerts = []
        max_days = max(ALERT_DAYS)  # 30 días por defecto
        
        # Documentos a verificar
        docs_to_check = [
            ("SOAT", conductor.soat_vigencia),
            ("Tecnomecánica", conductor.tecnomecanica_vigencia),
            ("Póliza", conductor.poliza_vigencia),
            ("Administración", conductor.tarjeta_operacion_vigencia),
            ("Licencia de Conducción", conductor.licencia_vigencia),
        ]
        
        for doc_name, fecha in docs_to_check:
            if not fecha:
                continue  # Sin fecha registrada, se ignora para alertas de email
            
            days_until = (fecha - self.today).days
            
            # Determinar estado
            if days_until < 0:
                estado = "vencido"
            elif days_until == 0:
                estado = "vence_hoy"
            elif days_until <= max_days:
                estado = "por_vencer"
            else:
                continue  # No necesita alerta
            
            # Si include_all=False, solo incluir si coincide exactamente con ALERT_DAYS
            if not include_all:
                if estado == "vencido" and days_until != -1:
                    # Solo alertar el primer día de vencimiento para automático
                    continue
                if estado == "por_vencer" and days_until not in ALERT_DAYS:
                    continue
            
            alerts.append({
                "tipo": doc_name,
                "fecha": fecha.strftime("%d/%m/%Y"),
                "estado": estado,
                "dias": days_until
            })
        
        return alerts
    
    def get_automatic_alerts(self, conductor: User) -> List[Dict]:
        """
        Obtiene solo las alertas que deben enviarse automáticamente.
        Solo se envían en días específicos: 30, 10, 0 (día de vencimiento), -1 (vencido ayer)
        """
        alerts = []
        
        docs_to_check = [
            ("SOAT", conductor.soat_vigencia),
            ("Tecnomecánica", conductor.tecnomecanica_vigencia),
            ("Póliza", conductor.poliza_vigencia),
            ("Administración", conductor.tarjeta_operacion_vigencia),
            ("Licencia de Conducción", conductor.licencia_vigencia),
        ]
        
        for doc_name, fecha in docs_to_check:
            if not fecha:
                continue
            
            days_until = (fecha - self.today).days
            
            # Solo alertar en días específicos
            should_alert = False
            
            if days_until in ALERT_DAYS:  # 30, 10, 0 días
                should_alert = True
            elif days_until == -1:  # Venció ayer (primer día de vencido)
                should_alert = True
            
            if not should_alert:
                continue
            
            if days_until < 0:
                estado = "vencido"
            elif days_until == 0:
                estado = "vence_hoy"
            else:
                estado = "por_vencer"
            
            alerts.append({
                "tipo": doc_name,
                "fecha": fecha.strftime("%d/%m/%Y"),
                "estado": estado,
                "dias": days_until
            })
        
        return alerts
    
    async def check_all_conductors(self, automatic: bool = False) -> Dict:
        """
        Verifica todos los conductores y envía alertas.
        
        Args:
            automatic: Si True, solo envía alertas en días específicos (30, 10, 0, vencido ayer)
                      Si False, envía a todos los que tienen documentos por vencer/vencidos
        
        Returns:
            Resumen de alertas enviadas
        """
        # Obtener todos los conductores activos
        conductores = self.db.exec(
            select(User).where(
                User.role == "conductor",
                User.is_active == True
            )
        ).all()
        
        results = {
            "total_conductores": len(conductores),
            "con_alertas": 0,
            "emails_enviados": 0,
            "emails_fallidos": 0,
            "sin_email": 0,
            "detalles": []
        }
        
        for conductor in conductores:
            # Usar alertas automáticas o todas según el modo
            if automatic:
                alerts = self.get_automatic_alerts(conductor)
            else:
                alerts = self.get_conductor_alerts(conductor)
            
            if not alerts:
                continue
            
            results["con_alertas"] += 1
            
            if not conductor.email:
                results["sin_email"] += 1
                results["detalles"].append({
                    "conductor": conductor.full_name,
                    "placa": conductor.vehiculo_placa,
                    "alertas": len(alerts),
                    "estado": "SIN_EMAIL"
                })
                continue
            
            # Enviar alerta
            success = await self.email_service.send_conductor_document_alert(
                conductor_email=conductor.email,
                conductor_name=conductor.full_name,
                vehicle_placa=conductor.vehiculo_placa or "N/A",
                alerts=alerts
            )
            
            if success:
                results["emails_enviados"] += 1
                results["detalles"].append({
                    "conductor": conductor.full_name,
                    "email": conductor.email,
                    "placa": conductor.vehiculo_placa,
                    "alertas": len(alerts),
                    "estado": "ENVIADO"
                })
            else:
                results["emails_fallidos"] += 1
                results["detalles"].append({
                    "conductor": conductor.full_name,
                    "email": conductor.email,
                    "placa": conductor.vehiculo_placa,
                    "alertas": len(alerts),
                    "estado": "ERROR"
                })
        
        return results
    
    async def send_alert_to_conductor(self, conductor_id: int) -> Dict:
        """
        Envía alerta manual a un conductor específico.
        Incluye TODOS los documentos con problemas (vencidos o por vencer).
        
        Args:
            conductor_id: ID del conductor
            
        Returns:
            Resultado del envío
        """
        conductor = self.db.get(User, conductor_id)
        
        if not conductor or conductor.role != "conductor":
            return {"success": False, "error": "Conductor no encontrado"}
        
        # Para envío manual, incluir todas las alertas
        alerts = self.get_conductor_alerts(conductor, include_all=True)
        
        if not alerts:
            return {"success": False, "error": "No hay alertas para este conductor"}
        
        if not conductor.email:
            return {"success": False, "error": "Conductor no tiene email registrado"}
        
        success = await self.email_service.send_conductor_document_alert(
            conductor_email=conductor.email,
            conductor_name=conductor.full_name,
            vehicle_placa=conductor.vehiculo_placa or "N/A",
            alerts=alerts
        )
        
        return {
            "success": success,
            "conductor": conductor.full_name,
            "email": conductor.email,
            "alertas": len(alerts)
        }
    
    async def run_automatic_alerts(self) -> Dict:
        """
        Ejecuta el envío automático de alertas.
        Solo envía a conductores cuyos documentos vencen en 30, 10, 0 días
        o vencieron ayer.
        
        Diseñado para ser llamado diariamente por un cron job.
        """
        print(f"[{self.today}] Ejecutando verificación automática de alertas...")
        results = await self.check_all_conductors(automatic=True)
        
        print(f"Resultados: {results['emails_enviados']} enviados, "
              f"{results['emails_fallidos']} fallidos, "
              f"{results['sin_email']} sin email")
        
        return results
