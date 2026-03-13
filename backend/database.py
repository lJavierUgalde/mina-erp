"""
database.py
Configuración de la conexión a PostgreSQL con SQLAlchemy.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ── Ajusta esta URL con tus credenciales de PostgreSQL ──────────────────────
DATABASE_URL = "postgresql+psycopg2://user:password@localhost:5432/mina_erp"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos ORM."""
    pass


# Dependencia de FastAPI para inyectar sesión de BD en los endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
