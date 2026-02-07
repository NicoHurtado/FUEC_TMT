"""
Servicio de Envío de Emails
"""
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Dict

from config import (
    SMTP_HOST, 
    SMTP_PORT, 
    SMTP_USER, 
    SMTP_PASSWORD, 
    ADMIN_EMAIL,
    COMPANY_NAME
)
from models.contract import Contract


class EmailService:
    """Servicio para envío de notificaciones por email"""
    
    def __init__(self):
        self.smtp_host = SMTP_HOST
        self.smtp_port = SMTP_PORT
        self.smtp_user = SMTP_USER
        self.smtp_password = SMTP_PASSWORD
        self.admin_email = ADMIN_EMAIL
    
    async def send_contract_notification(self, contract: Contract, pdf_path: Path) -> bool:
        """
        Envía notificación de nuevo contrato al administrador con PDF adjunto.
        
        Args:
            contract: Contrato generado
            pdf_path: Ruta al archivo PDF
            
        Returns:
            True si el envío fue exitoso
        """
        if not self.smtp_user or not self.smtp_password:
            print("Email no configurado. Saltando envío...")
            return False
        
        try:
            # Crear mensaje
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = self.admin_email
            msg['Subject'] = f"[FUEC] Nuevo Contrato Generado - {contract.contract_number}"
            
            # Info del servicio
            tipo_servicio_text = "Por Día" if contract.tipo_servicio == "dia" else "Por Hora"
            servicio_detalle = ""
            if contract.tipo_servicio == "dia" and contract.fecha_servicio:
                servicio_detalle = f"Fecha: {contract.fecha_servicio.strftime('%d/%m/%Y')}"
            elif contract.tipo_servicio == "hora":
                servicio_detalle = f"Horario: {contract.hora_inicio} - {contract.hora_fin}"
            
            # Cuerpo del mensaje
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #C5A065;">Nuevo Contrato de Arrendamiento</h2>
                
                <p>Se ha generado un nuevo contrato de arrendamiento de vehículo:</p>
                
                <table style="border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>N° Contrato:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{contract.contract_number}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Tipo de Servicio:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{tipo_servicio_text}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Detalle:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{servicio_detalle}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Ciudad:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{contract.ciudad}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Generado:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{contract.created_at.strftime('%d/%m/%Y %H:%M')}</td>
                    </tr>
                </table>
                
                <p>El documento PDF se encuentra adjunto a este correo.</p>
                
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">
                    Este es un mensaje automático del Sistema de Contratos de {COMPANY_NAME}.<br>
                    Por favor no responda a este correo.
                </p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Adjuntar PDF
            if pdf_path.exists():
                with open(pdf_path, 'rb') as attachment:
                    part = MIMEBase('application', 'pdf')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{contract.contract_number}.pdf"'
                    )
                    msg.attach(part)
            
            # Enviar email
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True
            )
            
            print(f"Email enviado exitosamente para contrato {contract.contract_number}")
            return True
            
        except Exception as e:
            print(f"Error enviando email: {e}")
            return False
    
    async def send_expiry_alert(self, vehicle_placa: str, doc_type: str, expiry_date: str) -> bool:
        """
        Envía alerta de documento próximo a vencer al admin.
        
        Args:
            vehicle_placa: Placa del vehículo
            doc_type: Tipo de documento
            expiry_date: Fecha de vencimiento
            
        Returns:
            True si el envío fue exitoso
        """
        if not self.smtp_user or not self.smtp_password:
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = self.admin_email
            msg['Subject'] = f"[ALERTA] Documento próximo a vencer - {vehicle_placa}"
            
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #dc2626;">⚠️ Alerta de Vencimiento</h2>
                
                <p>El siguiente documento está próximo a vencer:</p>
                
                <table style="border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Vehículo:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{vehicle_placa}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Documento:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{doc_type}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Vence:</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd; color: #dc2626;"><strong>{expiry_date}</strong></td>
                    </tr>
                </table>
                
                <p>Por favor, renueve el documento antes de su vencimiento para evitar bloqueos en el sistema.</p>
                
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">
                    Sistema FUEC - {COMPANY_NAME}
                </p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True
            )
            
            return True
            
        except Exception as e:
            print(f"Error enviando alerta: {e}")
            return False

    async def send_conductor_document_alert(
        self, 
        conductor_email: str,
        conductor_name: str,
        vehicle_placa: str,
        alerts: List[Dict]
    ) -> bool:
        """
        Envía alerta de documentos vencidos o por vencer al conductor.
        
        Args:
            conductor_email: Email del conductor
            conductor_name: Nombre del conductor
            vehicle_placa: Placa del vehículo
            alerts: Lista de alertas con {tipo, fecha, estado, dias}
            
        Returns:
            True si el envío fue exitoso
        """
        if not self.smtp_user or not self.smtp_password:
            print("Email no configurado. Saltando envío...")
            return False
        
        if not conductor_email:
            print(f"Conductor {conductor_name} no tiene email registrado")
            return False
        
        try:
            # Separar por estado
            vencidos = [a for a in alerts if a['estado'] == 'vencido']
            vence_hoy = [a for a in alerts if a['estado'] == 'vence_hoy']
            por_vencer = [a for a in alerts if a['estado'] == 'por_vencer']
            
            # Determinar tipo de alerta y prioridad
            if vencidos:
                subject = f"🚨 [URGENTE] Documentos VENCIDOS - {vehicle_placa}"
                header_color = "#dc2626"
                header_text = "🚨 DOCUMENTOS VENCIDOS"
                intro_text = "tiene documentos <strong style='color: #dc2626;'>VENCIDOS</strong>. Su acceso al sistema está <strong>BLOQUEADO</strong>."
            elif vence_hoy:
                subject = f"⚠️ [HOY] Documentos vencen HOY - {vehicle_placa}"
                header_color = "#dc2626"
                header_text = "⚠️ DOCUMENTOS VENCEN HOY"
                intro_text = "tiene documentos que <strong style='color: #dc2626;'>VENCEN HOY</strong>. Renuévelos de inmediato para evitar bloqueos."
            else:
                subject = f"📋 [AVISO] Documentos por vencer - {vehicle_placa}"
                header_color = "#f59e0b"
                header_text = "📋 DOCUMENTOS POR VENCER"
                intro_text = "tiene documentos <strong style='color: #f59e0b;'>próximos a vencer</strong>. Renuévelos a tiempo."
            
            # Construir tabla de documentos
            docs_html = ""
            for alert in alerts:
                dias = alert['dias']
                
                if alert['estado'] == 'vencido':
                    status_color = "#dc2626"
                    bg_color = "#fef2f2"
                    if dias == -1:
                        status_text = "VENCIDO AYER"
                    else:
                        status_text = f"VENCIDO desde el {alert['fecha']} (hace {abs(dias)} días)"
                elif alert['estado'] == 'vence_hoy':
                    status_color = "#dc2626"
                    bg_color = "#fef2f2"
                    status_text = "¡VENCE HOY!"
                else:
                    if dias <= 10:
                        status_color = "#ea580c"
                        bg_color = "#fff7ed"
                        status_text = f"⚠️ Vence en {dias} días"
                    else:
                        status_color = "#f59e0b"
                        bg_color = "#fffbeb"
                        status_text = f"Vence en {dias} días"
                
                docs_html += f"""
                <tr style="background: {bg_color};">
                    <td style="padding: 12px; border: 1px solid #ddd; font-weight: bold;">{alert['tipo']}</td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{alert['fecha']}</td>
                    <td style="padding: 12px; border: 1px solid #ddd; color: {status_color}; font-weight: bold;">{status_text}</td>
                </tr>
                """
            
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = conductor_email
            msg['Subject'] = subject
            
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 0;">
                <div style="background: {header_color}; color: white; padding: 25px; text-align: center;">
                    <h1 style="margin: 0; font-size: 24px;">{header_text}</h1>
                    <p style="margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">Vehículo: {vehicle_placa}</p>
                </div>
                
                <div style="padding: 25px; background: #ffffff;">
                    <p style="font-size: 16px;">Estimado(a) <strong>{conductor_name}</strong>,</p>
                    
                    <p style="font-size: 15px; line-height: 1.6;">
                        Le informamos que su vehículo <strong>{vehicle_placa}</strong> {intro_text}
                    </p>
                    
                    <table style="border-collapse: collapse; margin: 25px 0; width: 100%; font-size: 14px;">
                        <thead>
                            <tr style="background: #1a1a1a; color: white;">
                                <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">Documento</th>
                                <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">Vigencia</th>
                                <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">Estado</th>
                            </tr>
                        </thead>
                        <tbody>
                            {docs_html}
                        </tbody>
                    </table>
                    
                    {"<div style='background: #fef2f2; border-left: 4px solid #dc2626; padding: 15px; margin: 20px 0;'><p style='margin: 0; color: #dc2626; font-weight: bold;'>⛔ Su acceso al sistema está BLOQUEADO hasta que renueve los documentos vencidos.</p></div>" if vencidos else ""}
                    
                    <p style="font-size: 15px;">Por favor, comuníquese con la administración para actualizar sus documentos lo antes posible.</p>
                    
                    <div style="background: #C5A065; color: white; padding: 20px; margin-top: 25px; text-align: center;">
                        <p style="margin: 0; font-size: 16px; font-weight: bold;">{COMPANY_NAME}</p>
                        <p style="margin: 8px 0 0 0; font-size: 13px;">📧 logisticatmtv@gmail.com</p>
                    </div>
                </div>
                
                <div style="padding: 15px; text-align: center; font-size: 11px; color: #666; background: #f5f5f5;">
                    Este es un mensaje automático del Sistema FUEC.<br>
                    Por favor no responda a este correo.
                </div>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True
            )
            
            print(f"✓ Alerta enviada a {conductor_name} ({conductor_email})")
            return True
            
        except Exception as e:
            print(f"Error enviando alerta a {conductor_email}: {e}")
            return False

    async def send_contract_to_driver(
        self, 
        contract: Contract, 
        driver_email: str,
        driver_name: str,
        pdf_path: Path
    ) -> bool:
        """
        Envía el contrato generado al conductor.
        
        Args:
            contract: Contrato generado
            driver_email: Email del conductor
            driver_name: Nombre del conductor
            pdf_path: Ruta al archivo PDF
            
        Returns:
            True si el envío fue exitoso
        """
        if not self.smtp_user or not self.smtp_password:
            print("Email no configurado. Saltando envío...")
            return False
        
        if not driver_email:
            print(f"Conductor {driver_name} no tiene email registrado")
            return False
            
        try:
            # Crear mensaje
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = driver_email
            msg['Subject'] = f"Contrato de Arrendamiento - {contract.contract_number}"
            
            # Cuerpo del mensaje
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <p>Hola <strong>{driver_name}</strong>,</p>
                
                <p>Se ha generado el contrato de arrendamiento de vehículo automotor con conductor número <strong>{contract.contract_number}</strong> con éxito.</p>
                
                <p>Adjunto encontrará el archivo PDF correspondiente.</p>
                
                <p>Saludos,</p>
                <p><strong>{COMPANY_NAME}</strong></p>
                
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #666; font-size: 11px;">
                    Este es un mensaje automático. Por favor no responda a este correo.
                </p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Adjuntar PDF
            if pdf_path.exists():
                with open(pdf_path, 'rb') as attachment:
                    part = MIMEBase('application', 'pdf')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="Contrato_{contract.contract_number}.pdf"'
                    )
                    msg.attach(part)
            
            # Enviar email
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True
            )
            
            print(f"✓ Contrato enviado a conductor: {driver_email}")
            return True
            
        except Exception as e:
            print(f"Error enviando contrato al conductor {driver_email}: {e}")
            return False
