"""
Modelo de Usuario - Admin y Conductor (con vehículo asociado)
"""
from datetime import datetime, date
from typing import Optional
from sqlmodel import SQLModel, Field
import pytz

from config import TIMEZONE


def get_bogota_now() -> datetime:
    """Obtener fecha/hora actual en zona horaria de Bogotá"""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz)


class User(SQLModel, table=True):
    """
    Modelo de usuario unificado para Admin y Conductor.
    
    Para conductores: incluye datos del vehículo asociado.
    """
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    access_code: str = Field(unique=True, index=True, max_length=20)
    role: str = Field(max_length=20)  # "admin" o "conductor"
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=get_bogota_now)
    
    # ========== DATOS PERSONALES DEL CONDUCTOR ==========
    full_name: str = Field(max_length=200)
    cedula: Optional[str] = Field(default=None, max_length=20)
    celular: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    
    # Fotos (rutas a archivos)
    foto_conductor: Optional[str] = Field(default=None, max_length=500)
    foto_vehiculo: Optional[str] = Field(default=None, max_length=500)
    foto_licencia: Optional[str] = Field(default=None, max_length=500)
    
    # ========== DATOS DE LA LICENCIA ==========
    licencia_fecha_expedicion: Optional[date] = Field(default=None)
    licencia_restricciones: Optional[str] = Field(default=None, max_length=200)
    licencia_categoria: Optional[str] = Field(default=None, max_length=20)  # A1, A2, B1, B2, B3, C1, C2, C3
    licencia_vigencia: Optional[date] = Field(default=None)
    licencia_servicio: Optional[str] = Field(default=None, max_length=20)  # "particular" o "publico"
    
    # ========== DATOS DEL VEHÍCULO ASOCIADO ==========
    vehiculo_placa: Optional[str] = Field(default=None, max_length=10, index=True)
    vehiculo_marca: Optional[str] = Field(default=None, max_length=50)
    vehiculo_modelo: Optional[str] = Field(default=None, max_length=50)
    vehiculo_color: Optional[str] = Field(default=None, max_length=30)
    
    # ========== VIGENCIAS DE DOCUMENTOS DEL VEHÍCULO ==========
    soat_vigencia: Optional[date] = Field(default=None)
    tecnomecanica_vigencia: Optional[date] = Field(default=None)
    poliza_vigencia: Optional[date] = Field(default=None)
    tarjeta_operacion_vigencia: Optional[date] = Field(default=None)
    
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
    
    @property
    def is_conductor(self) -> bool:
        return self.role == "conductor"
    
    @property
    def tiene_documentos_vencidos(self) -> bool:
        """Verificar si algún documento está vencido"""
        from .document import get_bogota_today
        today = get_bogota_today()
        
        fechas = [
            self.soat_vigencia,
            self.tecnomecanica_vigencia,
            self.poliza_vigencia,
            self.tarjeta_operacion_vigencia,
            self.licencia_vigencia
        ]
        
        for fecha in fechas:
            if fecha and fecha < today:
                return True
        return False
    
    @property
    def documentos_faltantes(self) -> list:
        """Lista de documentos sin fecha registrada"""
        faltantes = []
        if not self.soat_vigencia:
            faltantes.append("SOAT")
        if not self.tecnomecanica_vigencia:
            faltantes.append("Tecnomecánica")
        if not self.poliza_vigencia:
            faltantes.append("Póliza")
        if not self.tarjeta_operacion_vigencia:
            faltantes.append("Tarjeta de Operación")
        if not self.licencia_vigencia:
            faltantes.append("Licencia de Conducción")
        return faltantes


class UserCreate(SQLModel):
    """Schema para crear usuario"""
    full_name: str
    cedula: Optional[str] = None
    role: str = "conductor"


class UserUpdate(SQLModel):
    """Schema para actualizar usuario"""
    full_name: Optional[str] = None
    cedula: Optional[str] = None
    is_active: Optional[bool] = None
