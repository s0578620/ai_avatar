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
    """
    Tabellen erstellen und optional einen Dev-Admin-Account anlegen.
    """
    from . import models
    from ..media import Media
    from .security import hash_password

    Base.metadata.create_all(bind=engine)

    dev_email = os.getenv("DEV_ADMIN_EMAIL")
    dev_password = os.getenv("DEV_ADMIN_PASSWORD")

    if dev_email and dev_password:
        db = SessionLocal()
        try:
            existing = (
                db.query(models.Teacher)
                .filter(models.Teacher.email == dev_email)
                .first()
            )
            if not existing:
                dev = models.Teacher(
                    name="Dev Admin",
                    email=dev_email,
                    password_hash=hash_password(dev_password),
                    role="dev",
                )
                db.add(dev)
                db.commit()
        finally:
            db.close()

def get_db():
    """FastAPI-Dependency für eine DB-Session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
