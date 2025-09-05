from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import DATABASE_URL

# Declarative Base – ezt importálja a models.py
Base = declarative_base()

# Modul-szintű engine
_engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Session gyár
SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

def get_engine():
    return _engine

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

