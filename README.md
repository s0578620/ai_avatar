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

## RAG Chat with Avatar Bot
```bash

curl -X POST 'http://localhost:5678/webhook/2bac3271-1376-4bbe-be9f-f1dd8da805c7/chat' \
  -H 'Content-Type: application/json' \
  -d '{
    "sessionId": "demo-session-1",
    "action": "sendMessage",
    "chatInput": "Wo lebt der Fuchs?"
  }'
```

## Rag Chat with Avatar Bot (continue conversation)
```bash

curl -X POST 'http://localhost:5678/webhook/2bac3271-1376-4bbe-be9f-f1dd8da805c7/chat' \
  -H 'Content-Type: application/json' \
  -d '{
    "sessionId": "demo-session-1",
    "action": "sendMessage",
    "chatInput": "Wo lebt der Adler?"
  }'
```



