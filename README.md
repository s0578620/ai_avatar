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
```bash
curl -X POST "http://localhost:8000/ingest"   -H "Content-Type: application/json"   -d '{
    "text": "Paris ist die Hauptstadt von Frankreich.",
    "collection": "avatar_docs"
  }'
```

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
curl -X POST "http://localhost:8000/chat"   -H "Content-Type: application/json"   -d '{
    "message": "Was ist die Hauptstadt von Frankreich?",
    "session_id": "demo-session-1",
    "collection": "avatar_docs"
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

Beispiel-Result:
```json
{
  "task_id": "e92067fe-1e5d-4d12-82ef-c69d64eba742",
  "status": "SUCCESS",
  "result": {
    "answer": "Paris ist die Hauptstadt von Frankreich.",
    "documents": [
      "Paris ist die Hauptstadt von Frankreich.",
      "",
      ""
    ],
    "scores": [0.9361528, 0.47156176, 0.47156176, 0.4188522]
  }
}
```

---

## Ingestion via Webhook
```bash
curl -X POST 'http://localhost:5678/webhook/4a9fca36-7902-4fb2-8a84-748351cf884a'   -H 'Content-Type: application/json'   -d '{
    "text": "Der Fuchs lebt oft im Wald. Er baut sich kleine Höhlen im Boden oder benutzt Höhlen, die andere Tiere verlassen haben. Der Fisch lebt im Wasser. Es gibt viele verschiedene Fischarten. Manche leben im Meer, andere in Seen oder Flüssen. Der Adler lebt in den Bergen und baut sein Nest weit oben, zum Beispiel auf hohen Felsen oder in sehr hohen Bäumen.",
    "collection": "avatar_docs"
  }'
```

## RAG Chat with Avatar Bot
```bash
curl -X POST 'http://localhost:5678/webhook/b675c023-0a40-4fab-8427-73a0f467cee6/chat'   -H 'Content-Type: application/json'   -d '{
    "sessionId": "demo-session-1",
    "action": "sendMessage",
    "chatInput": "Wo lebt der Fuchs?"
  }'
```

---

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
