# AI-Avatar

A Retrieval-Augmented Generation (RAG) based AI Avatar platform designed for educational use.
Teachers can manage classes, students, media, and knowledge sources, while students interact with a context-aware AI avatar.
Gamification and personalization (interests, levels, badges) are built in.

**Tech Stack:** FastAPI · Celery · Redis · Qdrant · PostgreSQL · n8n · Gemini API

---

## Architecture Overview

```
Client (Browser / App)
        |
     FastAPI
        |
  -------------------------
  |        |        |     |
Redis   Celery   Postgres Qdrant
  |                 |
n8n Workflows     Media Storage
        |
     Gemini API
```

---

## Requirements

- Docker Desktop with WSL2 backend (Windows) **or**
- Docker + Docker Compose (Linux / macOS)

---

## Environment Configuration

Create a `.env` file in the project root (if not present):

```env
# =========================
# General
# =========================
PYTHONUNBUFFERED=1
TZ=Europe/Berlin
API_PORT=8000

# =========================
# Celery / Redis
# =========================
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# =========================
# RAG Settings
# =========================
DEFAULT_COLLECTION=avatar_docs
TOP_K=4
MAX_HISTORY_MESSAGES=6

# =========================
# Gemini API (REQUIRED)
# =========================
# Never commit real keys!
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_CHAT_MODEL=gemini-2.5-flash
GEMINI_EMBED_MODEL=text-embedding-004

# =========================
# n8n
# =========================
N8N_HOST=localhost
N8N_PORT=5678
N8N_PROTOCOL=http

# =========================
# Database (PostgreSQL)
# =========================
DB_TYPE=postgresdb
DB_POSTGRESDB_HOST=db
DB_POSTGRESDB_PORT=5432
DB_POSTGRESDB_USER=n8n
DB_POSTGRESDB_PASSWORD=n8n
DB_POSTGRESDB_DATABASE=n8n

# SQLAlchemy URL for user database
USER_DB_URL=postgresql+psycopg2://n8n:n8n@db:5432/avatar_userdb

# =========================
# Media Storage
# =========================
MEDIA_ROOT=/data/media

# Optional: Base URL used by worker tasks
# USER_API_BASE=http://api:8000
```

---

## Start the Project

```bash
docker compose up -d --build
```

⏱ First startup may take **1–3 minutes**.

### Available UIs

- FastAPI Docs: http://localhost:8000/docs
- n8n: http://localhost:5678
- Qdrant Dashboard: http://localhost:6333/dashboard

---

## Import n8n Workflows

1. Open http://localhost:5678
2. Log in to n8n
3. Import and activate:
   - `n8n_workflows/Avatar_Data_Ingestion_native_testing_copy.json`
   - `n8n_workflows/Avatar_RAG_Chat_native_testing_copy.json`

---

## Health Checks

```bash
# Basic API health
curl http://localhost:8000/health

# Qdrant connection & collections
curl http://localhost:8000/health/qdrant

# Gemini backend
curl http://localhost:8000/health/gemini
```

---

## Asynchronous API Note

Most endpoints run **asynchronously** using Celery.

They return a `task_id`.  
Use `/tasks/{task_id}` to retrieve the final result.

---

## RAG API

### Ingest Text

```bash
curl -X POST "http://localhost:8000/ingest"   -H "Content-Type: application/json"   -d '{
    "text": "Paris is the capital of France.",
    "collection": "avatar_docs"
  }'
```

With metadata:

```bash
curl -X POST "http://localhost:8000/ingest"   -H "Content-Type: application/json"   -d '{
    "text": "Foxes live in forests and are very clever animals.",
    "collection": "avatar_docs",
    "doc_id": "fox_facts_01",
    "metadata": {
      "class_id": 1,
      "subject": "Science",
      "source": "Worksheet"
    }
  }'
```

Check task status:

```bash
curl http://localhost:8000/tasks/<task_id>
```

---

### RAG Chat

```bash
curl -X POST "http://localhost:8000/chat"   -H "Content-Type: application/json"   -d '{
    "message": "Tell me something interesting about foxes.",
    "session_id": "demo-session-1",
    "collection": "avatar_docs",
    "student_id": 2
  }'
```

---

## User & Class Management API

### Register Teacher

```bash
curl -X POST "http://localhost:8000/api/teachers/register"   -H "Content-Type: application/json"   -d '{
    "name": "Demo Teacher",
    "email": "demo@example.com",
    "password": "test123"
  }'
```

### Teacher Login

```bash
curl -X POST "http://localhost:8000/api/auth/login"   -H "Content-Type: application/json"   -d '{
    "email": "demo@example.com",
    "password": "test123"
  }'
```

### request Reset Password
```bash
curl -X POST "http://localhost:8000/api/auth/request-password-reset" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com"
  }'
```
Example Response(ONLY IN DEV-MODE!):
```json
{
  "status": "ok",
  "reset_token": "SOME_RESET_TOKEN"
}
```

### Set New Password
```bash
curl -X POST "http://localhost:8000/api/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "SOME_RESET_TOKEN",
    "new_password": "neuesPasswort123"
  }'
```

Example Response:
```json
{
  "status": "ok"
}
```
### Teacher Resert Password

```bash
curl -X POST "http://localhost:8000/api/auth/request-password-reset" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com"
  }'
```

B
---

### Create Class

```bash
curl -X POST "http://localhost:8000/api/classes"   -H "Content-Type: application/json"   -d '{
    "name": "Class 5A",
    "teacher_id": 1,
    "grade_level": "5",
    "subject": "Mathematics"
  }'
```

### List Classes

```bash
curl http://localhost:8000/api/classes
```

---

### Add Student

```bash
curl -X POST "http://localhost:8000/api/classes/1/students"   -H "Content-Type: application/json"   -d '{
    "name": "Max Mustermann",
    "class_id": 1,
    "username": "max1",
    "password": "secret123"
  }'
```

### Export Students as CSV

```bash
curl http://localhost:8000/api/classes/1/students/export -o students.csv
```

---

## Student Profile & Interests

```bash
curl -X POST "http://localhost:8000/api/user/interests"   -H "Content-Type: application/json"   -d '{
    "student_id": 1,
    "interest_text": "Likes animals and Minecraft"
  }'
```

```bash
curl http://localhost:8000/api/user/profile?student_id=1
```

---

## Media API

Teachers can upload files (images, PDFs) and link them to classes and tags.

### Supported Types

- Images: jpg, png, webp
- Documents: pdf
- Max file size: 10 MB

### Upload Media

```bash
curl -X POST "http://localhost:8000/api/media/"   -F "teacher_id=1"   -F "class_id=1"   -F "type=image"   -F 'tags=["animals","fox"]'   -F "file=@files_test/fox.webp"
```

### List Media

```bash
curl http://localhost:8000/api/media/
curl http://localhost:8000/api/media/?class_id=1
curl http://localhost:8000/api/media/?teacher_id=1
curl http://localhost:8000/api/media/?tags=animals,fox
```

### Delete Media

```bash
curl -X DELETE http://localhost:8000/api/media/1
```

---

## Gamification API

```bash
curl -X POST "http://localhost:8000/api/gamification/event"   -H "Content-Type: application/json"   -d '{
    "student_id": 1,
    "event_type": "ask_question"
  }'
```

---

## Running Tests Locally (Optional)

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r services/api/requirements.txt
pip install -r services/worker/requirements.txt
pip install pytest requests

# Unit tests
pytest -m "not integration"

# Integration tests (Docker stack required)
docker compose up -d
pytest -m integration
```

---