import os
import uuid
from datetime import datetime
from pathlib import Path
from PIL import Image
import logging
from typing import Optional, List
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from .userdb.database import Base, get_db

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/data/media"))

try:
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
except PermissionError:
    from tempfile import gettempdir

    MEDIA_ROOT = Path(gettempdir()) / "media"
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
router = APIRouter(prefix="/media", tags=["media"])

logger = logging.getLogger(__name__)

THUMB_MAX_SIZE = (400, 400)

def create_image_thumbnail(src_path: Path) -> Path | None:
    try:
        thumb_name = f"{src_path.stem}_thumb.webp"
        thumb_path = src_path.with_name(thumb_name)

        with Image.open(src_path) as img:
            img.thumbnail(THUMB_MAX_SIZE)
            img.save(thumb_path, format="WEBP")

        return thumb_path
    except Exception as e:
        logger.warning("Could not create thumbnail for %s: %s", src_path, e)
        return None

# -----------------------
# SQLAlchemy Modell
# -----------------------
class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)

    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)

    type = Column(String(50), nullable=False, default="file")
    original_filename = Column(String(255), nullable=False)
    path = Column(String(255), nullable=False, unique=True)
    thumbnail_path = Column(String(255), nullable=True)

    # z.B. ["tiere", "fuchs"]
    tags = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# -----------------------
# Pydantic Schemas
# -----------------------
class MediaOut(BaseModel):
    id: int
    teacher_id: int
    class_id: Optional[int] = None
    type: str
    original_filename: str
    path: str
    thumbnail_path: Optional[str] = None
    tags: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# -----------------------
# Helper
# -----------------------
def _parse_tags(raw: Optional[str]) -> Optional[List[str]]:
    """
    Erwartet entweder:
      - JSON-Array als String, z.B. '["Word1","Word2"]'
      - oder Komma-String, z.B. "Word1, Word2"
    """
    if not raw:
        return None

    raw = raw.strip()
    if not raw:
        return None

    # 1) Versuche JSON-Array
    if raw.startswith("["):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = None

        if isinstance(value, list):
            cleaned = [str(v).strip() for v in value if str(v).strip()]
            return cleaned or None

    # 2) Fallback: Komma-getrennte Liste
    parts = [p.strip() for p in raw.split(",")]
    cleaned = [p.strip(' "\'[]') for p in parts]  # Quotes & [] weg
    cleaned = [p for p in cleaned if p]

    return cleaned or None
# -----------------------]
# Endpoints
# -----------------------
@router.post("/", response_model=MediaOut)
async def upload_media(
    teacher_id: int = Form(...),
    class_id: Optional[int] = Form(None),
    type: str = Form("file"),
    tags: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Datei-Upload für Lehrkräfte.
    - speichert Datei unter MEDIA_ROOT/<uuid>.<ext>
    - legt Media-Record in Postgres an
    """
    # 1) Datei speichern
    ext = Path(file.filename).suffix or ""
    file_id = uuid.uuid4().hex
    dest = MEDIA_ROOT / f"{file_id}{ext}"

    contents = await file.read()
    with dest.open("wb") as f:
        f.write(contents)

    # 2) Tags parsen
    tag_list = _parse_tags(tags)

    # 3) Thumbnail erzeugen (images)
    thumbnail_path: Optional[str] = None
    if type == "image":
        thumb = create_image_thumbnail(dest)
        if thumb is not None:
            thumbnail_path = str(thumb)

    # 4) DB-Objekt anlegen (id kommt auto-increment aus Postgres)
    media = Media(
        teacher_id=teacher_id,
        class_id=class_id,
        type=type,
        original_filename=file.filename,
        path=str(dest),
        thumbnail_path=thumbnail_path,
        tags=tag_list,
    )

    db.add(media)
    db.commit()
    db.refresh(media)

    return media


@router.get("/", response_model=List[MediaOut])
def list_media(
    class_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    tag: Optional[str] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Liste von Medien, filterbar nach:
    - class_id
    - teacher_id
    - tag (ein Tag, muss im tags-Array enthalten sein)
    """
    query = db.query(Media)

    if class_id is not None:
        query = query.filter(Media.class_id == class_id)
    if teacher_id is not None:
        query = query.filter(Media.teacher_id == teacher_id)
    if tag:
        query = query.filter(Media.tags.contains([tag]))
    if type:
        query = query.filter(Media.type == type)
    items = query.order_by(Media.created_at.desc()).all()
    return items

@router.delete("/{media_id}")
def delete_media(
    media_id: int,
    db: Session = Depends(get_db),
):
    """
    Media-Eintrag + Datei löschen.
    """
    media: Media | None = db.get(Media, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    # Datei löschen
    for p in [media.path, media.thumbnail_path]:
        if p:
            try:
                p_path = Path(p)
                if p_path.exists():
                    p_path.unlink()
            except OSError:
                pass

    db.delete(media)
    db.commit()
    return {"status": "deleted", "id": media_id}
