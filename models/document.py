"""
Utilidades de fecha para el sistema FUEC
"""
from datetime import datetime, date
import pytz

from config import TIMEZONE


def get_bogota_today() -> date:
    """Obtener fecha actual en zona horaria de Bogotá"""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).date()


def get_bogota_now() -> datetime:
    """Obtener fecha/hora actual en zona horaria de Bogotá"""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz)
