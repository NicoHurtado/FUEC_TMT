"""
Configuración del Sistema FUEC - Transportes Medellín Travel
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Directorio base del proyecto
BASE_DIR = Path(__file__).resolve().parent

# Base de datos - Soporta PostgreSQL (producción) y SQLite (desarrollo)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/fuec.db")

# Seguridad
SECRET_KEY = os.getenv("SECRET_KEY", "fuec-transportes-medellin-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

# Timezone
TIMEZONE = "America/Bogota"

# Configuración de Email (SMTP)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "logisticatmtv@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # Configurar con App Password de Gmail
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "logisticatmtv@gmail.com")

# Días de anticipación para alertas de vencimiento
ALERT_DAYS = [30, 10, 0]  # Enviar alerta a 30 días, 10 días y el día del vencimiento

# Hora de ejecución de alertas automáticas (formato 24h)
ALERT_HOUR = 8  # 8:00 AM
ALERT_MINUTE = 0

# Directorio para PDFs generados (uso local/temporal)
PDF_DIR = BASE_DIR / "generated_pdfs"
PDF_DIR.mkdir(exist_ok=True)

# Directorio para uploads (fotos)
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
(UPLOADS_DIR / "conductores").mkdir(exist_ok=True)
(UPLOADS_DIR / "vehiculos").mkdir(exist_ok=True)
(UPLOADS_DIR / "licencias").mkdir(exist_ok=True)

# ========== CLOUDINARY ==========
CLOUDINARY_CLOUD_NAME = os.getenv("Cloud_name", os.getenv("CLOUDINARY_CLOUD_NAME", ""))
CLOUDINARY_API_KEY = os.getenv("API_KEY", os.getenv("CLOUDINARY_API_KEY", ""))
CLOUDINARY_API_SECRET = os.getenv("API_SECRET", os.getenv("CLOUDINARY_API_SECRET", ""))

# Habilitar Cloudinary solo si las credenciales están configuradas
USE_CLOUDINARY = bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)

# Información de la empresa
COMPANY_NAME = "Transportes Medellín Travel"
COMPANY_NIT = "900.123.456-7"
COMPANY_ADDRESS = "Calle 50 #45-30, Medellín, Antioquia"
COMPANY_PHONE = "(604) 123-4567"

# Tipos de documentos requeridos
DOCUMENT_TYPES = [
    "SOAT",
    "TECNOMECANICA", 
    "TARJETA_OPERACION",
    "POLIZA"
]

# Colores del sistema
COLORS = {
    "primary": "#C5A065",      # Dorado/Ocre
    "primary_hover": "#b08a4a",
    "danger": "#dc2626",
    "success": "#16a34a",
    "bg_dark": "#1a1a1a",
    "bg_light": "#f5f5f5",
}
