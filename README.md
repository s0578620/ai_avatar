# AI-Avatar

RAG-basierter Avatar-Bot mit FastAPI, Celery, Qdrant, Redis, Postgres und n8n.

## Setup

Use WSL2 or Docker Desktop with WSL2 backend on Windows.

Erstelle im Projekt-Root eine `.env` (falls nicht vorhanden), z.B.:

```env
PYTHONUNBUFFERED=1
TZ=Europe/Berlin

API_PORT=8000

CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

DEFAULT_COLLECTION=avatar_docs
TOP_K=4
MAX_HISTORY_MESSAGES=6

GEMINI_API_KEY=DEIN_GEMINI_API_KEY
GEMINI_CHAT_MODEL=gemini-2.5-flash
GEMINI_EMBED_MODEL=text-embedding-004

N8N_HOST=localhost
N8N_PORT=5678
N8N_PROTOCOL=http

DB_TYPE=postgresdb
DB_POSTGRESDB_HOST=db
DB_POSTGRESDB_PORT=5432
DB_POSTGRESDB_USER=n8n
DB_POSTGRESDB_PASSWORD=n8n
DB_POSTGRESDB_DATABASE=n8n

# SQLAlchemy-URL für die User-DB (Teacher / Klassen / Schüler / Interessen)
USER_DB_URL=postgresql+psycopg2://n8n:n8n@db:5432/avatar_userdb

# Optional: von den Worker-Tasks verwendete Basis-URL für die User-API
# (Standard ist http://api:8000)
# USER_API_BASE=http://api:8000
```

## Start Project
```bash
docker compose up -d --build
```

UIs: FastAPI http://localhost:8000/docs, n8n http://localhost:5678, Qdrant http://localhost:6333/dashboard

## import Workflows to n8n
- ./n8n_workflows/Avatar_Data_Ingestion_native_testing_copy.json
- ./n8n_workflows/Avatar_RAG_Chat_native_testing_copy.json


## Healthcheck API
```bash
# Basis-Health
curl -s http://localhost:8000/health

# Qdrant-Verbindung & Collections
curl -s http://localhost:8000/health/qdrant

# Gemini-Backend
curl -s http://localhost:8000/health/gemini
```

---

## Direkte RAG API-Nutzung

### Ingestion via API
Minimal:
```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Paris ist die Hauptstadt von Frankreich.",
    "collection": "avatar_docs"
  }'
```
Mit doc_id + Metadaten:
```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Der Fuchs lebt im Wald und ist ein schlaues Tier.",
    "collection": "avatar_docs",
    "doc_id": "fox_facts_01",
    "metadata": {
      "class_id": 1,
      "subject": "Sachkunde",
      "source": "Arbeitsblatt"
    }
  }'
```

```bash
Beispiel-Antwort:
```json
{
  "task_id": "cc186c96-eafd-498b-b99d-7589cc96ac53",
  "collection": "avatar_docs"
}
```

Task-Status abfragen:
```bash
curl "http://localhost:8000/tasks/cc186c96-eafd-498b-b99d-7589cc96ac53"
```

### RAG Chat via API
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Kannst du mir etwas Spannendes über den Fuchs erklären?",
    "session_id": "demo-session-1",
    "collection": "avatar_docs",
    "student_id": 2
  }'
```

Beispiel-Antwort:
```json
{
  "task_id": "e92067fe-1e5d-4d12-82ef-c69d64eba742",
  "collection": "avatar_docs"
}
```

Ergebnis abholen:
```bash
curl "http://localhost:8000/tasks/e92067fe-1e5d-4d12-82ef-c69d64eba742"
```

---
## UserDb API (Teacher-Student)

### register Teacher
```bash
curl -X POST "http://localhost:8000/api/teachers/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Demo",
    "email": "demo@example.com",
    "password": "test123"
  }'
```
Beispiel-Antwort:
```json
{
  "name": "Demo",
  "email": "demo@example.com",
  "id": 1
}
```
### Teacher Login
```bash
---
## Ingestion via Webhook
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "test123"
  }'
```
Beispiel-Antwort:
```json
{
  "teacher_id": 1
}
```

### Klasse anlegen
```bash
curl -X POST "http://localhost:8000/api/classes" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Klasse 5A",
    "teacher_id": 1,
    "grade_level": "5",
    "subject": "Mathematik"
  }'
```
### Klassen auflisten

```bash
curl "http://localhost:8000/api/classes"
```

### Schüler in Klasse anlegen
```bash
curl -X POST "http://localhost:8000/api/classes/1/students" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Max Mustermann",
    "class_id": 1,
    "username": "max1",
    "password": "geheim123"
  }'
```
### Schülerliste als CSV exportieren
```bash
curl "http://localhost:8000/api/classes/1/students/export" \
  -o class_1_students.csv
```

### Interessen für Schüler speichern
```bash
curl -X POST "http://localhost:8000/api/user/interests" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": 1,
    "interest_text": "Mag Tiere und Minecraft"
  }'
```

### User Profile abrufen
```bash
curl "http://localhost:8000/api/user/profile?student_id=1"
```
## Media API (Datei-Upload für Lehrkräfte)
Die Media-API erlaubt es Lehrkräften, Dateien (z. B. Bilder) hochzuladen und mit Klassen / Tags zu verknüpfen.  
Die Dateien werden im Container unter `MEDIA_ROOT` gespeichert (Standard: `/data/media`)
### Beispiel: Bild-Upload
```bash
curl -X POST "http://localhost:8000/api/media/" \
  -F "teacher_id=1" \
  -F "class_id=1" \
  -F "type=image" \
  -F 'tags=["tiere","fuchs"]' \
  -F "file=@files_test/fuchs.webp"

Beispiel-Antwort:
```json
{
  "id": 1,
  "teacher_id": 1,
  "class_id": 1,
  "type": "image",
  "original_filename": "fuchs.webp",
  "path": "/data/media/009289b429814990b54f3dc3d058df63.webp",
  "thumbnail_path": null,
  "tags": ["tiere", "fuchs"],
  "created_at": "2025-12-16T09:50:42.073747"
}

```
### Media-Datei abrufen
Alle Media-Dateien auflisten:
```bash
curl "http://localhost:8000/api/media/"
```
Nach Klasse filtern:
```bash
curl "http://localhost:8000/api/media/?class_id=1"
```
Nach Lehrkraft filtern:
```bash
curl "http://localhost:8000/api/media/?teacher_id=1"
```
Nach Tags filtern:
```bash
curl "http://localhost:8000/api/media/?tags=tiere,fuchs"
```
Beispiel Antwort:
```json
[
  {
    "id": 1,
    "teacher_id": 1,
    "class_id": 1,
    "type": "image",
    "original_filename": "fuchs.webp",
    "path": "/data/media/009289b429814990b54f3dc3d058df63.webp",
    "thumbnail_path": null,
    "tags": ["tiere", "fuchs"],
    "created_at": "2025-12-16T09:50:42.073747"
  }
]
```
### Medien löschen
```bash
curl -X DELETE "http://localhost:8000/api/media/1"
``` 
Beispiel Antwort:
```json
[
 {
   "status": "deleted",
   "id": 1
 }
]
```
[
  {
    "id": 1,
    "teacher_id": 1,
    "class_id": 1,

## Tests lokal ausführen (optional)
```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
# .\.venv\Scripts\Activate.ps1

pip install -r services/api/requirements.txt
pip install -r services/worker/requirements.txt
pip install pytest requests

# Unit-Tests
pytest -m "not integration"

# Integrationstests (benötigt laufenden Docker-Stack)
docker compose up -d
pytest -m integration
```
