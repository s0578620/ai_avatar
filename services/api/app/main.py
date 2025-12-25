import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from celery import Celery
from celery.result import AsyncResult
from fastapi.staticfiles import StaticFiles
from services.shared.rag_core import RAG
from .userdb.database import init_db
from .userdb.routes import router as userdb_router
from .media import router as media_router, MEDIA_ROOT
from .gamification import router as gamification_router

# --------------------
# Celery / RAG Setup
# --------------------
BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
DEFAULT_COLLECTION = os.getenv("DEFAULT_COLLECTION", "avatar_docs")

celery = Celery(__name__, broker=BROKER_URL, backend=RESULT_BACKEND)
rag = RAG()

app = FastAPI(title="Avatar RAG API", version="0.4.0")


# --------------------
# Startup & User-DB
# --------------------
@app.on_event("startup")
def startup_event():
    init_db()


app.include_router(userdb_router)
app.include_router(media_router, prefix="/api")
app.include_router(gamification_router, prefix="/api")
app.mount("/media-files", StaticFiles(directory=MEDIA_ROOT), name="media-files")

# --------------------
# Schemas
# --------------------
class IngestIn(BaseModel):
    text: str
    collection: str | None = None
    doc_id: str | None = None
    metadata: dict | None = None


class ChatIn(BaseModel):
    message: str
    session_id: str = "default"
    collection: str | None = None
    student_id: int | None = None

# --------------------
# Lesson Plan Schemas
# --------------------

class LessonStep(BaseModel):
    id: str
    phase: str
    title: str
    description: str
    start_minute: int
    end_minute: int
    media_tags: List[str] = Field(default_factory=list)
    media_ids: List[int] = Field(default_factory=list)


class LessonPlanIn(BaseModel):
    topic: str
    duration_minutes: int = Field(..., ge=5, le=180)
    grade_level: Optional[str] = None
    class_id: Optional[int] = None
    teacher_id: Optional[int] = None


class LessonPlanOut(BaseModel):
    topic: str
    duration_minutes: int
    grade_level: Optional[str]
    class_id: Optional[int] = None
    steps: List[LessonStep]


# --------------------
# Health-Endpoints
# --------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/qdrant")
def health_qdrant():
    try:
        collections = rag.client.get_collections()
        names = [c.name for c in collections.collections]
        return {"status": "ok", "collections": names}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Qdrant health check failed: {e}",
        )


@app.get("/health/gemini")
def health_gemini():
    try:
        answer = rag.generate("ping")
        return {
            "status": "ok",
            "sample_answer": (answer or "")[:80],
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Gemini health check failed: {e}",
        )


# --------------------
# Ingestion & Chat
# --------------------
@app.post("/ingest")
def ingest(payload: IngestIn):
    collection = payload.collection or DEFAULT_COLLECTION
    task = celery.send_task(
        "tasks.ingest_text",
        args=[
            payload.text,
            collection,
            payload.doc_id,
            payload.metadata or {},
        ],
    )
    return {"task_id": task.id, "collection": collection}


@app.post("/chat")
def chat(payload: ChatIn):
    collection = payload.collection or DEFAULT_COLLECTION

    task = celery.send_task(
        "tasks.chat_with_rag",
        args=[
            payload.session_id,
            payload.message,
            collection,
            payload.student_id,
        ],
    )
    return {"task_id": task.id, "collection": collection}

@app.post("/lesson-planner")
def lesson_planner(payload: LessonPlanIn):
    """
    Startet asynchron die Generierung eines Unterrichtsplans.
    Ergebnis wird über /tasks/{task_id} abgeholt.
    """
    task = celery.send_task(
        "tasks.generate_lesson_plan",
        args=[payload.model_dump()],
    )
    return {"task_id": task.id}

@app.get("/tasks/{task_id}")
def get_status(task_id: str):
    res: AsyncResult = celery.AsyncResult(task_id)
    data = {"task_id": task_id, "status": res.status}
    if res.successful():
        data["result"] = res.result
    elif res.failed():
        data["error"] = str(res.result)
    return data
