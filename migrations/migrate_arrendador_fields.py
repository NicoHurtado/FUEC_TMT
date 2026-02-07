"""
Migration: Add nombre_arrendador and documento_arrendador columns to contracts table
Uses SQLAlchemy/SQLModel - supports both SQLite and PostgreSQL
"""
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import engine

def run_migration():
    """Add landlord fields to contracts table (preserves existing data)"""
    
    with engine.connect() as conn:
        # Check existing columns
        try:
            # Try PostgreSQL way first
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'contracts'
            """))
            columns = [row[0] for row in result.fetchall()]
        except Exception:
            # Fallback for SQLite
            result = conn.execute(text("PRAGMA table_info(contracts)"))
            columns = [row[1] for row in result.fetchall()]
        
        print(f"Columnas existentes: {columns}")
        
        # Add nombre_arrendador if not exists
        if "nombre_arrendador" not in columns:
            print("Añadiendo columna nombre_arrendador...")
            conn.execute(text("ALTER TABLE contracts ADD COLUMN nombre_arrendador VARCHAR(200)"))
            conn.commit()
            print("✓ nombre_arrendador añadida")
        else:
            print("✓ nombre_arrendador ya existe")
        
        # Add documento_arrendador if not exists
        if "documento_arrendador" not in columns:
            print("Añadiendo columna documento_arrendador...")
            conn.execute(text("ALTER TABLE contracts ADD COLUMN documento_arrendador VARCHAR(50)"))
            conn.commit()
            print("✓ documento_arrendador añadida")
        else:
            print("✓ documento_arrendador ya existe")
    
    print("\n✅ Migración completada exitosamente (datos existentes preservados)")

if __name__ == "__main__":
    run_migration()

