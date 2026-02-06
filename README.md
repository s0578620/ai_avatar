[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3110/)   
# AI-Avatar

A Retrieval-Augmented Generation (RAG) based AI Avatar platform designed for educational use.

- **Teachers** manage classes, students, media, and knowledge sources.
- **Students** interact with a context-aware AI avatar.
- **Gamification & personalization** (interests, levels, badges) are built in.

**Tech Stack:** FastAPI · Celery · Redis · Qdrant · PostgreSQL · n8n · Gemini API

---

## Table of contents

- [Architecture](#architecture)
- [Requirements](#requirements)
- [Environment configuration](#environment-configuration)
- [Import n8n workflows](#import-n8n-workflows)
- [Health checks](#health-checks)
- [Async task model](#async-task-model)
- [API examples](#api-examples)
  - [Worksheet generator](#worksheet-generator)
  - [RAG: ingest](#rag-ingest)
  - [RAG: chat](#rag-chat)
  - [Mini-Auth & RBAC (Demo)](#mini-auth--rbac-demo)
  - [Teachers & auth](#teachers--auth)
  - [Classes & students](#classes--students)
  - [Student profile & interests](#student-profile--interests)
  - [Media](#media)
  - [Gamification](#gamification)
  - [Lesson planner](#lesson-planner)

---

## Architecture

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

## Requirements

- Docker Desktop with WSL2 backend (Windows) **or**
- Docker + Docker Compose (Linux / macOS)

---

**UIs**
- FastAPI Docs: http://localhost:8000/docs
- n8n: http://localhost:5678
- Qdrant Dashboard: http://localhost:6333/dashboard

---

## Environment configuration

Create a `.env` file in the project root

### `.env.example`

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
# IMPORTANT: make sure the database exists, see Troubleshooting.
USER_DB_URL=postgresql+psycopg2://n8n:n8n@db:5432/avatar_userdb

# Optional: Base URL used by worker tasks
USER_API_BASE=http://api:8000

# =========================
# Media Storage
# =========================
MEDIA_ROOT=/data/media

# =========================
# Dev Admin (Bootstrap User)
# =========================
# Wird beim Start automatisch als Teacher mit role="dev" angelegt,
# wenn noch kein User mit dieser E-Mail existiert.
# Dieser Account kann sich über POST /api/auth/dev-login anmelden.
DEV_ADMIN_EMAIL=dev@example.com
DEV_ADMIN_PASSWORD=dev123
```

---
## Start the Project

```bash
docker compose up -d --build
```

⏱ First startup may take **1–3 minutes**.

## Import n8n workflows

1. Open http://localhost:5678
2. Log in to n8n
3. Import and activate:
   - `n8n_workflows/Avatar_Data_Ingestion_native_testing_copy.json`
   - `n8n_workflows/Avatar_RAG_Chat_native_testing_copy.json`

---

## Health checks

```bash
# Basic API health
curl http://localhost:8000/health

# Qdrant connection & collections
curl http://localhost:8000/health/qdrant

# Gemini backend
curl http://localhost:8000/health/gemini
```

---

## Async task model

Most endpoints run **asynchronously** using Celery.
They return a `task_id`.

```bash
curl http://localhost:8000/tasks/<task_id>
```

---

## API examples

### Worksheet generator

#### Only Tasks (JSON, no PDF)

```bash
curl -X POST "http://localhost:8000/worksheet/content" \
  -H "Content-Type: application/json" \
  --data-binary @- << 'EOF'
{
  "topic": "Füchse im Wald",
  "learning_goal": "Leseverständnis zu Sachtexten üben",
  "grade_level": "5",
  "interests": ["Tiere"],
  "num_tasks": 4
}
EOF
```

**Example response (/tasks/<task_id>):**
```json
{
  "title": "Arbeitsblatt: ...",
  "topic": "...",
  "learning_goal": "...",
  "grade_level": "5",
  "student_id": null,
  "interests": ["Tiere"],
  "tasks": [
    {"question": "...", "solution": "..."}
  ]
}
```

**Generate PDF from Worksheet JSON**

```bash
curl -X POST "http://localhost:8000/worksheet/pdf" \
  -H "Content-Type: application/json" \
  --data-binary @- << 'EOF'
{
  "title": "Arbeitsblatt: Füchse im Wald",
  "tasks": [
    { "question": "Frage 1" },
    { "question": "Frage 2" }
  ]
}
EOF
```
**Example response (/tasks/<task_id>):**
```json
{
  "pdf_url": "/media-files/worksheet_....pdf"
}
```

### RAG: ingest

#### Ingest text

```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Paris is the capital of France.",
    "collection": "avatar_docs"
  }'
```

#### Ingest with metadata

```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
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

---

### RAG: chat

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me something interesting about foxes.",
    "session_id": "demo-session-1",
    "collection": "avatar_docs",
    "student_id": 2
  }'
```

---
### Mini-Auth & RBAC (Demo)

### Mini-Auth & RBAC (Demo)

- There are three roles:
  - **Dev/Admin (`role="dev"`)** – can register new teachers and perform admin actions.
  - **Teacher (`role="teacher"`)** – manages classes, students, media.
  - **Student (`role="student"`)** – only uses the avatar.
- Password hashing: PBKDF2-SHA256 (`passlib`).
- There are **no** JWTs/sessions – the frontend only remembers `teacher_id`, `dev_id` or `student_id`.
- Authentication endpoints:
  - Dev/Admin login: `POST /api/auth/dev-login` → returns `{ "dev_id": ..., "role": "dev" }`
  - Teacher login: `POST /api/auth/login` → returns `{ "teacher_id": ..., "role": "teacher" }`
  - Student login: `POST /api/auth/student-login` → returns `{ "student_id": ..., "class_id": ..., "role": "student" }`
- Current RBAC rules (simplified):
  - Only a dev/admin may call `POST /api/teachers/register`  
    → via `?creator_id=<dev_teacher_id>`.
  - Only teachers may create classes and students.
  - The student list for a class (`GET /api/classes/{class_id}/students`) is only visible
    if `teacher_id` is the homeroom teacher of that class.
  - A student may only be deleted if the calling `teacher_id`
    is the homeroom teacher of that student's class (`DELETE /api/user/student/{student_id}`).
- The model is deliberately simple and intended only for demo/school prototypes.

### Teachers & auth

#### Register teacher

```bash
curl -X POST "http://localhost:8000/api/teachers/register?creator_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Demo Teacher",
    "email": "demo@example.com",
    "password": "test123"
  }'
```
### Dev/Admin login

Der Dev-Admin-Account wird beim Start über die Umgebungsvariablen  
`DEV_ADMIN_EMAIL` und `DEV_ADMIN_PASSWORD` angelegt (falls noch nicht vorhanden).

```bash
curl -X POST "http://localhost:8000/api/auth/dev-login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dev@example.com",
    "password": "dev123"
  }'
```

Example response:
```json
{
  "dev_id": 1,
  "role": "dev"
}
```
#### Teacher login

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "test123"
  }'
```
Example response:
```json
{
  "teacher_id": 1,
  "role": "teacher"
}
```

#### Request password reset (teacher)

```bash
curl -X POST "http://localhost:8000/api/auth/request-password-reset" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com"
  }'
```

**Example response (DEV only):**
```json
{
  "status": "ok",
  "reset_token": "SOME_RESET_TOKEN"
}
```

#### Set new password (teacher)

```bash
curl -X POST "http://localhost:8000/api/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "SOME_RESET_TOKEN",
    "new_password": "neuesPasswort123"
  }'
```

#### Student login

```bash
curl -X POST "http://localhost:8000/api/auth/student-login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "max1",
    "password": "geheim123"
  }'
```

Example response:
```json
{
  "student_id": 1,
  "class_id": 1,
  "role": "student"
}
```

---

### Classes & students

#### Create class

```bash
curl -X POST "http://localhost:8000/api/classes" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Class 5A",
    "teacher_id": 1,
    "grade_level": "5",
    "subject": "Mathematics"
  }'
```

#### List classes

```bash
curl http://localhost:8000/api/classes
```

#### Add student

```bash
curl -X POST "http://localhost:8000/api/classes/1/students" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Max Mustermann",
    "class_id": 1,
    "username": "max1",
    "password": "secret123"
  }'
```

#### Delete student
Only teachers may delete students – and only if they are the class teacher of that student’s class.
```bash
curl -X DELETE "http://localhost:8000/api/user/student/42?teacher_id=1"
```
student_id – path parameter (here: 42)
teacher_id – query parameter; must match class.teacher_id of the student's class
If the teacher does not own the class, the API responds with 403 Not allowed to delete this student.

#### Export students as CSV

```bash
curl http://localhost:8000/api/classes/1/students/export -o students.csv
```

---

### Student profile & interests

```bash
curl -X POST "http://localhost:8000/api/user/interests" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": 1,
    "interest_text": "Likes animals and Minecraft"
  }'
```

```bash
curl "http://localhost:8000/api/user/profile?student_id=1"
```

---

### Media

Teachers can upload files (images, PDFs) and link them to classes and tags.

**Supported types**
- Images: jpg, png, webp
- Documents: pdf
- Max file size: 10 MB

#### Upload media

```bash
curl -X POST "http://localhost:8000/api/media/" \
  -F "teacher_id=1" \
  -F "class_id=1" \
  -F "type=image" \
  -F 'tags=["animals","fox"]' \
  -F "file=@files_test/fox.webp"
```

#### List media

```bash
curl "http://localhost:8000/api/media/"
curl "http://localhost:8000/api/media/?class_id=1"
curl "http://localhost:8000/api/media/?teacher_id=1"
curl "http://localhost:8000/api/media/?tag=fox"
curl "http://localhost:8000/api/media/?tag=fox&type=image"
```

#### Delete media

```bash
curl -X DELETE "http://localhost:8000/api/media/1"
```

#### Access media file

```text
http://localhost:8000/media-files/<filename>
```

---

### Gamification

```bash
curl -X POST "http://localhost:8000/api/gamification/event" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": 1,
    "event_type": "ask_question"
  }'
```

---

### Lesson planner

#### Request lesson plan

```bash
curl -X POST "http://localhost:8000/lesson-planner" \
  -H "Content-Type: application/json" \
  --data-binary @- << 'EOF'
{
  "topic": "Füchse im Wald",
  "duration_minutes": 45,
  "grade_level": "5",
  "class_id": 1
}
EOF
```

Response:
```json
{
  "task_id": "..."
}
```

Check result:
```bash
curl http://localhost:8000/tasks/<task_id>
```

---

## Project structure

- `services/api/` – FastAPI app (HTTP endpoints, DB models, routes)
- `services/worker/` – Celery worker (ingest/chat/lesson-plan/worksheet/pdf tasks)
- `services/shared/` – shared RAG logic (`rag_core.py`)
- `n8n_workflows/` – n8n workflows exports
- `data/media/` – persistent media volume (mounted into API + worker)

---

## Tests (optional)

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
