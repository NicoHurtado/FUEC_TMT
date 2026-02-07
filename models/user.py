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
    
    soat_vigencia: Optional[date] = Field(default=None)
    tecnomecanica_vigencia: Optional[date] = Field(default=None)
    
    # Póliza - Renovación mensual
    poliza_activa: bool = Field(default=False)
    poliza_mes: Optional[int] = Field(default=None)  # Mes en que se marcó (1-12)
    poliza_año: Optional[int] = Field(default=None)  # Año en que se marcó
    
    # Administración - Renovación mensual
    admin_activa: bool = Field(default=False)
    admin_mes: Optional[int] = Field(default=None)
    admin_año: Optional[int] = Field(default=None)
    
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
        
        # Verificar documentos con fecha
        fechas = [
            self.soat_vigencia,
            self.tecnomecanica_vigencia,
            self.licencia_vigencia
        ]
        
        for fecha in fechas:
            if fecha and fecha < today:
                return True
        
        # Verificar documentos mensuales (solo después del día 5)
        if today.day > 5:
            poliza_estado = self.get_estado_documento_mensual('poliza')
            admin_estado = self.get_estado_documento_mensual('admin')
            if poliza_estado == 'vencido' or admin_estado == 'vencido':
                return True
        
        return False
    
    def get_estado_documento_mensual(self, tipo: str) -> str:
        """
        Obtiene el estado de un documento mensual.
        Retorna: 'ok', 'gracia', 'pendiente', 'vencido'
        """
        from .document import get_bogota_today
        today = get_bogota_today()
        mes_actual = today.month
        año_actual = today.year
        dia = today.day
        
        if tipo == 'poliza':
            activa = self.poliza_activa
            mes = self.poliza_mes
            año = self.poliza_año
        else:  # admin
            activa = self.admin_activa
            mes = self.admin_mes
            año = self.admin_año
        
        # Si está marcado para el mes actual
        if activa and mes == mes_actual and año == año_actual:
            return 'ok'
        
        # Si estamos en período de gracia (días 1-5)
        if dia <= 5:
            return 'gracia'
        
        # Después del día 5 sin pagar
        return 'vencido'
    
    @property
    def poliza_vigente(self) -> bool:
        """Verifica si la póliza está vigente para el mes actual"""
        return self.get_estado_documento_mensual('poliza') == 'ok'
    
    @property
    def admin_vigente(self) -> bool:
        """Verifica si la administración está vigente para el mes actual"""
        return self.get_estado_documento_mensual('admin') == 'ok'
    
    @property
    def documentos_faltantes(self) -> list:
        """Lista de documentos sin registrar o vencidos"""
        faltantes = []
        if not self.soat_vigencia:
            faltantes.append("SOAT")
        if not self.tecnomecanica_vigencia:
            faltantes.append("Tecnomecánica")
        
        # Para documentos mensuales, verificar si están pendientes
        poliza_estado = self.get_estado_documento_mensual('poliza')
        if poliza_estado in ('pendiente', 'vencido'):
            faltantes.append("Póliza")
        
        admin_estado = self.get_estado_documento_mensual('admin')
        if admin_estado in ('pendiente', 'vencido'):
            faltantes.append("Administración")
        
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
