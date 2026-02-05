"""
Servicios del Sistema FUEC
"""
from .email_service import EmailService

__all__ = ["EmailService"]

# PDFGenerator se importa solo cuando se necesita para evitar
# cargar WeasyPrint innecesariamente
