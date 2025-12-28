import os
import json
import logging
from typing import Optional, Dict, Any, List
import requests
from celery import Celery
from redis import Redis
from services.shared.rag_core import RAG

from pathlib import Path
from uuid import uuid4

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
MAX_HISTORY = int(os.getenv("MAX_HISTORY_MESSAGES", "6"))

USER_API_BASE = os.getenv("USER_API_BASE", "http://api:8000")

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "data/media"))
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

celery = Celery("worker", broker=BROKER_URL, backend=RESULT_BACKEND)
rag = RAG()

redis = Redis.from_url(BROKER_URL.replace("/0", "/1"))

logger = logging.getLogger(__name__)

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

def _fetch_user_profile(student_id: Optional[int]) -> Optional[dict]:
    """
    Holt das User-Profil für einen Schüler aus der API,
    wenn eine student_id übergeben wurde.
    """
    if not student_id:
        return None

    try:
        resp = requests.get(
            f"{USER_API_BASE}/api/user/profile",
            params={"student_id": student_id},
            timeout=3,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Could not fetch user profile for {student_id}: {e}")
        return None

def _build_profile_prefix(user_profile: Optional[dict]) -> str:
    """
    Baut einen System-/Profil-Text, der dem LLM Kontext
    über den Schüler gibt (Name, Klasse, Interessen).
    """
    if not user_profile:
        return ""

    student_name = user_profile.get("student_name") or "das Kind"
    class_name = user_profile.get("class_name") or ""
    interests = user_profile.get("interests") or []
    interests_text = ", ".join(interests) if interests else "keine speziellen Interessen hinterlegt"

    lines = [
        "SYSTEM: Du bist ein freundlicher Lern-Avatar für Kinder.",
        "Berücksichtige bei Beispielen und Erklärungen das Profil des Schülers, "
        "ohne vom fachlichen Inhalt abzulenken.",
        f"Schüler-Name: {student_name}",
        f"Klasse: {class_name}",
        f"Interessen: {interests_text}",
        "",
    ]
    return "\n".join(lines)

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
def chat_with_rag(
    self,
    session_id: str,
    message: str,
    collection: str,
    student_id: int | None = None,
) -> dict:
    """
    Führt Retrieval auf Qdrant durch, baut den Prompt mit History, Kontext
    UND optionalem User-Profil und generiert eine Antwort mit Gemini.
    """
    try:
        # 1. RAG-Retrieval
        hits = rag.search(collection, message)
        contexts = [h[1].get("text", "") for h in hits]

        # 2. Chat-History
        history_text = "\n".join(
            f"{h['role'].upper()}: {h['content']}"
            for h in _hist(session_id)[-MAX_HISTORY:]
        )

        # 3. User-Profil holen und als System-Kontext einbauen
        user_profile = _fetch_user_profile(student_id)
        profile_prefix = _build_profile_prefix(user_profile)

        # 4. Alles kombinieren
        parts = []
        if profile_prefix:
            parts.append(profile_prefix)
        if history_text:
            parts.append(history_text)

        combined_prefix = "\n".join(parts) if parts else ""
        user_line = f"USER: {message}"

        if combined_prefix:
            prompt_input = f"{combined_prefix}\n{user_line}"
        else:
            prompt_input = user_line

        # 5. Prompt für LLM bauen
        prompt = rag.build_prompt(prompt_input, contexts)
        answer = rag.generate(prompt)

        # 6. History aktualisieren
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

@celery.task(name="tasks.generate_lesson_plan")
def generate_lesson_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generiert einen Unterrichtsplan mit Gemini und verknüpft passende Media-IDs
    über die Media-API (/api/media).
    """
    rag = RAG()

    topic = payload["topic"]
    duration = payload["duration_minutes"]
    grade_level = payload.get("grade_level") or "unknown"

    # ---------- 1) Prompt für Gemini ----------
    prompt = f"""
    You are a helpful lesson planning assistant for German teachers.

    Create a lesson plan based on:
    - Topic: "{topic}"
    - Duration: {duration} minutes
    - Grade level: {grade_level}

    Return your answer as VALID JSON ONLY.
    - No Markdown
    - No backticks
    - No comments
    - No text before or after the JSON

    Use exactly this schema:

    {{
      "steps": [
        {{
          "id": "intro",
          "phase": "Einstieg",
          "title": "Short title",
          "description": "2-3 sentences in German, suitable for students.",
          "start_minute": 0,
          "end_minute": 10,
          "media_tags": ["tiere", "fuchs"]
        }}
      ]
    }}

    Rules:
    - Use 3–6 steps.
    - "phase" must be one of: "Einstieg", "Erarbeitung", "Sicherung", "Abschluss".
    - "media_tags" is a list of simple lowercase keywords.
        """.strip()

    raw = rag.generate(prompt)
    logger.info("Lesson planner raw output: %s", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Could not parse lesson planner JSON: %s; raw=%r", e, raw)
        # Fallback: Minimaler Plan
        data = {
            "steps": [
                {
                    "id": "main",
                    "phase": "Erarbeitung",
                    "title": f"Arbeit zum Thema {topic}",
                    "description": "Einfache Arbeitsphase, automatisch erzeugter Fallback.",
                    "start_minute": 0,
                    "end_minute": duration,
                    "media_tags": [],
                }
            ]
        }

    steps: List[Dict[str, Any]] = data.get("steps", [])

    api_base = os.getenv("USER_API_BASE", "http://api:8000")

    def fetch_media_ids_for_tags(tags: List[str]) -> List[int]:
        ids: List[int] = []

        for tag in tags:
            resp = None

            try:
                resp = requests.get(
                    f"{api_base}/api/media",
                    params={"tag": tag},
                    timeout=5,
                )
            except requests.RequestException as exc:
                logger.warning(
                    "fetch_media_ids_for_tags: request failed for tag %r: %s",
                    tag,
                    exc,
                )

            if resp is None:
                continue

            if resp.status_code != 200:
                logger.warning(
                    "fetch_media_ids_for_tags: non-200 (%s) for tag %r",
                    resp.status_code,
                    tag,
                )
                continue

            try:
                items = resp.json()
            except ValueError as exc:
                logger.warning(
                    "fetch_media_ids_for_tags: invalid JSON for tag %r: %s",
                    tag,
                    exc,
                )
                continue

            if not isinstance(items, list):
                logger.warning(
                    "fetch_media_ids_for_tags: unexpected JSON type %r for tag %r",
                    type(items),
                    tag,
                )
                continue

            for item in items:
                mid = item.get("id")
                if isinstance(mid, int) and mid not in ids:
                    ids.append(mid)

        return ids

    enriched_steps: List[Dict[str, Any]] = []

    for step in steps:
        tags = step.get("media_tags") or []
        media_ids = fetch_media_ids_for_tags(tags)
        step["media_ids"] = media_ids
        enriched_steps.append(step)

    return {
        "topic": topic,
        "duration_minutes": duration,
        "grade_level": grade_level,
        "class_id": payload.get("class_id"),
        "steps": enriched_steps,
    }

@celery.task(name="tasks.generate_pdf_from_json")
def generate_pdf_from_json(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nimmt ein einfaches Worksheet-JSON entgegen und erzeugt ein PDF.
    Speichert es in MEDIA_ROOT und liefert eine Download-URL zurück.
    Erwartetes Payload-Schema:
    {
      "title": "Arbeitsblatt: ...",
      "tasks": [
        {"question": "Frage 1"},
        {"question": "Frage 2"}
      ]
    }
    """
    title = payload.get("title", "Arbeitsblatt")
    tasks = payload.get("tasks") or []

    filename = f"worksheet_{uuid4().hex}.pdf"
    filepath = MEDIA_ROOT / filename

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(filepath), pagesize=A4)

    story = []
    # Header
    story.append(Paragraph(title, styles["Heading1"]))
    story.append(Spacer(1, 18))

    # Aufgaben
    for idx, task in enumerate(tasks, start=1):
        question = task.get("question") or task.get("text") or ""
        if not question:
            continue
        story.append(Paragraph(f"{idx}. {question}", styles["Normal"]))
        story.append(Spacer(1, 12))

    doc.build(story)

    return {
        "pdf_filename": filename,
        "pdf_url": f"/media-files/{filename}",
        "pdf_path": str(filepath),
    }
