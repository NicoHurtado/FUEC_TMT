"""
Configuración de la base de datos con SQLModel
Soporta PostgreSQL (producción) y SQLite (desarrollo)
"""
import os
from sqlmodel import SQLModel, create_engine, Session
from config import DATABASE_URL

# Detectar tipo de base de datos
is_sqlite = DATABASE_URL.startswith("sqlite")

# Configurar engine según el tipo de base de datos
if is_sqlite:
    # SQLite: requiere check_same_thread=False para FastAPI
    engine = create_engine(
        DATABASE_URL, 
        echo=False,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL: configurar pool de conexiones
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True  # Verificar conexión antes de usar
    )


def create_db_and_tables():
    """Crear todas las tablas en la base de datos"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency para obtener sesión de base de datos"""
    with Session(engine) as session:
        yield session
