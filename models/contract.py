"""
Modelo de Contrato de Arrendamiento de Vehículo
"""
from datetime import datetime, date, time
from typing import Optional
from sqlmodel import SQLModel, Field

from .user import get_bogota_now


class Contract(SQLModel, table=True):
    """
    Modelo de contrato de arrendamiento de vehículo con conductor.
    """
    __tablename__ = "contracts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    contract_number: str = Field(unique=True, index=True, max_length=20)
    conductor_id: int = Field(foreign_key="users.id", index=True)
    
    # Tipo de servicio: 'dia' o 'hora'
    tipo_servicio: str = Field(max_length=10)
    
    # Para servicio por día
    fecha_servicio: Optional[date] = Field(default=None)
    
    # Para servicio por hora
    hora_inicio: Optional[str] = Field(default=None, max_length=10)
    hora_fin: Optional[str] = Field(default=None, max_length=10)
    
    # Ciudad
    ciudad: str = Field(max_length=100)
    
    # Datos del arrendador
    nombre_arrendador: Optional[str] = Field(default=None, max_length=200)
    documento_arrendador: Optional[str] = Field(default=None, max_length=50)
    
    # Firma digital (base64)
    signature_base64: str
    
    # Archivo PDF generado
    pdf_path: str = Field(max_length=500)
    
    # URL del PDF en Cloudinary (para producción)
    pdf_url: Optional[str] = Field(default=None, max_length=500)
    
    created_at: datetime = Field(default_factory=get_bogota_now)


class ContractResponse(SQLModel):
    """Schema para respuesta de contrato"""
    id: int
    contract_number: str
    tipo_servicio: str
    ciudad: str
    created_at: datetime


def generate_contract_number(last_id: int) -> str:
    """Generar número de contrato único (formato: 001, 002, etc.)"""
    return f"{last_id + 1:03d}"
