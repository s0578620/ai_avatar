import os
import json
from celery import Celery
from redis import Redis
from services.shared.rag_core import RAG

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
MAX_HISTORY = int(os.getenv("MAX_HISTORY_MESSAGES", "6"))

celery = Celery("worker", broker=BROKER_URL, backend=RESULT_BACKEND)
rag = RAG()

redis = Redis.from_url(BROKER_URL.replace("/0", "/1"))


def _hkey(sid: str) -> str:
    return f"chat:{sid}"


def _hist(sid: str):
    return [
        json.loads(x)
        for x in redis.lrange(_hkey(sid), 0, MAX_HISTORY * 2)
    ][::-1]


def _append(sid: str, role: str, content: str):
    redis.rpush(_hkey(sid), json.dumps({"role": role, "content": content}))
    redis.ltrim(_hkey(sid), -MAX_HISTORY * 2, -1)


@celery.task(name="tasks.ingest_text", bind=True)
def ingest_text(
    self,
    text: str,
    collection: str,
    doc_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """
    Nimmt Text entgegen, splittet ihn in Chunks und schreibt sie in Qdrant.
    """
    try:
        meta = metadata or {}
        if "doc_id" not in meta:
            meta["doc_id"] = doc_id or "unknown"

        chunks = rag.split_text(text)
        count = rag.upsert_chunks(collection, chunks, meta)

        return {"chunks": count, "collection": collection}
    except Exception as e:
        raise RuntimeError(
            f"Ingest failed for collection '{collection}' (doc_id='{doc_id}'): {e}"
        ) from e


@celery.task(name="tasks.chat_with_rag", bind=True)
def chat_with_rag(self, session_id: str, message: str, collection: str) -> dict:
    """
    Führt Retrieval auf Qdrant durch, baut den Prompt mit History und Kontext
    und generiert eine Antwort mit Gemini.
    """
    try:
        hits = rag.search(collection, message)
        contexts = [h[1].get("text", "") for h in hits]

        prefix = "\n".join(
            f"{h['role'].upper()}: {h['content']}"
            for h in _hist(session_id)[-MAX_HISTORY:]
        )

        prompt = rag.build_prompt(f"{prefix}\nUSER: {message}", contexts)
        answer = rag.generate(prompt)

        _append(session_id, "user", message)
        _append(session_id, "assistant", answer)

        return {
            "answer": answer,
            "documents": contexts[:3],
            "scores": [float(s) for s, _ in hits],
        }
    except Exception as e:
        raise RuntimeError(
            f"Chat failed for session '{session_id}' in collection '{collection}': {e}"
        ) from e
