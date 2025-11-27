# AI-Avatar

## Setup


Use WSL2 or Docker Desktop with WSL2 backend on Windows.

## Setup
```bash

docker compose up -d --build

```
UIs: FastAPI http://localhost:8000/docs, n8n http://localhost:5678, Qdrant http://localhost:6333/dashboard

## import Workflows to n8n
- ./n8n_workflows/Avatar_Data_Ingestion_native_testing.json
- q



## Healthcheck API
```bash

curl -s http://localhost:8000/health
```
## Ingestion via Webhook
```bash

curl -X POST 'http://localhost:5678/webhook/4a9fca36-7902-4fb2-8a84-748351cf884a' \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Der Fuchs lebt oft im Wald. Er baut sich kleine Höhlen im Boden oder benutzt Höhlen, die andere Tiere verlassen haben. Der Fisch lebt im Wasser. Es gibt viele verschiedene Fischarten. Manche leben im Meer, andere in Seen oder Flüssen. Der Adler lebt in den Bergen und baut sein Nest weit oben, zum Beispiel auf hohen Felsen oder in sehr hohen Bäumen.",
    "collection": "avatar_docs"
  }'
```


## RAG Chat with Avatar Bot
```bash

curl -X POST 'http://localhost:5678/webhook/b675c023-0a40-4fab-8427-73a0f467cee6/chat' \
  -H 'Content-Type: application/json' \
  -d '{
    "sessionId": "demo-session-1",
    "action": "sendMessage",
    "chatInput": "Wo lebt der Fuchs?"
  }'
```

## Rag Chat with Avatar Bot (continue conversation)
```bash

curl -X POST 'http://localhost:5678/webhook/b675c023-0a40-4fab-8427-73a0f467cee6/chat' \
  -H 'Content-Type: application/json' \
  -d '{
    "sessionId": "demo-session-1",
    "action": "sendMessage",
    "chatInput": "Wo lebt der Adler?"
  }'
```



