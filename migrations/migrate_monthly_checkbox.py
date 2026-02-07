"""
Migración: Cambiar Póliza y Administración de fecha a checkbox mensual
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import engine

def run_migration():
    """
    Ejecuta la migración para agregar los nuevos campos de checkbox mensual
    y eliminar los campos de fecha antiguos.
    """
    with engine.connect() as conn:
        # 1. Agregar nuevas columnas
        print("Agregando nuevas columnas...")
        
        new_columns = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS poliza_activa BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS poliza_mes INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS poliza_año INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_activa BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_mes INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_año INTEGER",
        ]
        
        for sql in new_columns:
            try:
                conn.execute(text(sql))
                print(f"  ✓ Ejecutado: {sql[:50]}...")
            except Exception as e:
                print(f"  ⚠ Error (puede que ya exista): {e}")
        
        # 2. Eliminar columnas antiguas (opcional, comentar si quieres mantenerlas)
        print("\nEliminando columnas antiguas...")
        
        old_columns = [
            "ALTER TABLE users DROP COLUMN IF EXISTS poliza_vigencia",
            "ALTER TABLE users DROP COLUMN IF EXISTS tarjeta_operacion_vigencia",
        ]
        
        for sql in old_columns:
            try:
                conn.execute(text(sql))
                print(f"  ✓ Ejecutado: {sql[:50]}...")
            except Exception as e:
                print(f"  ⚠ Error: {e}")
        
        conn.commit()
        print("\n✅ Migración completada!")

if __name__ == "__main__":
    print("=" * 50)
    print("MIGRACIÓN: Checkbox Mensual para Póliza y Admin")
    print("=" * 50)
    run_migration()
