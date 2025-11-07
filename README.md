# AI-Avatar

## Setup


Use WSL2 or Docker Desktop with WSL2 backend on Windows.

## Setup
```bash

docker compose up -d --build

./scripts/pull_models.sh
```
UIs: FastAPI http://localhost:8000/docs, n8n http://localhost:5678, Qdrant http://localhost:6333/dashboard

## import Workflows to n8n
- ./n8n_workflows/Avatar_Data_Ingestion.json
- ./n8n_workflows/Avatar_ RAG_Chatbot.json



## Healthcheck API
```bash

curl -s http://localhost:8000/health
```

## Ingest Sample Document
```bash

curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text":"Das ist ein Qdrant Smoke-Test Dokument.","collection":"avatar_docs"}'
```

## Chat with Avatar RAG Bot
```bash

curl -s -X POST http://localhost:5678/webhook/avatar/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Worum geht es im Testdokument?","session_id":"demo","collection":"avatar_docs"}'
```

## Chat with Avatar RAG Bot (Testing)
```bash

curl -s -X POST http://localhost:5678/webhook-test/avatar/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Worum geht es im Testdokument?","session_id":"demo","collection":"avatar_docs"}'

```

# TODO:
- session_id handling verbessern (at the moment u need to use different session_ids for different questions to avoid context mixing)

# PLAYGROUND
## For longer documents (multiple questions)
USE WSL:
```
python3 - <<'PY' | curl -s -X POST http://localhost:8000/ingest -H 'Content-Type: application/json' -d @-
import json,sys,io
text = io.open('docs/doc.txt','r',encoding='utf-8').read()
print(json.dumps({"text": text, "collection": "animals"}))
PY

```
## Questions
## 
```bash

curl -s -X POST http://localhost:5678/webhook/avatar/chat   -H 'Content-Type: application/json'   -d '{"message":"wo lebt der fuchs?","session_id":"new","collection":"avatar_docs"}'
```
## 
```bash

curl -s -X POST http://localhost:5678/webhook/avatar/chat   -H 'Content-Type: application/json'   -d '{"message":"wo lebt der fisch?","session_id":"new1","collection":"avatar_docs"}'
```
