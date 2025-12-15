import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

USER_DB_URL = os.getenv(
    "USER_DB_URL",
    "postgresql+psycopg2://n8n:n8n@db:5432/avatar_userdb",
)

if not USER_DB_URL:
    raise RuntimeError("USER_DB_URL is not set in environment / .env")

engine = create_engine(USER_DB_URL, future=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def init_db():
    """Tabellen erstellen, falls sie noch nicht existieren."""
    from . import models
    Base.metadata.create_all(bind=engine)

def get_db():
    """FastAPI-Dependency für eine DB-Session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
