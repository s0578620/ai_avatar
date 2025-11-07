import os
from fastapi import FastAPI
from pydantic import BaseModel
from celery import Celery
from celery.result import AsyncResult
from .rag import RAG

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
DEFAULT_COLLECTION = os.getenv("DEFAULT_COLLECTION", "avatar_docs")

celery = Celery(__name__, broker=BROKER_URL, backend=RESULT_BACKEND)
rag = RAG()

app = FastAPI(title="Avatar RAG API", version="0.3.0")

class IngestIn(BaseModel):
    text: str
    collection: str | None = None
    doc_id: str | None = None
    metadata: dict | None = None

class ChatIn(BaseModel):
    message: str
    session_id: str = "default"
    collection: str | None = None

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ingest")
def ingest(payload: IngestIn):
    collection = payload.collection or DEFAULT_COLLECTION
    task = celery.send_task("tasks.ingest_text", args=[payload.text, collection, payload.doc_id, payload.metadata or {}])
    return {"task_id": task.id, "collection": collection}

@app.post("/chat")
def chat(payload: ChatIn):
    collection = payload.collection or DEFAULT_COLLECTION
    task = celery.send_task("tasks.chat_with_rag", args=[payload.session_id, payload.message, collection])
    return {"task_id": task.id, "collection": collection}

@app.get("/tasks/{task_id}")
def get_status(task_id: str):
    res: AsyncResult = celery.AsyncResult(task_id)
    data = {"task_id": task_id, "status": res.status}
    if res.successful():
        data["result"] = res.result
    elif res.failed():
        data["error"] = str(res.result)
    return data