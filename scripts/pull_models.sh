#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d ollama
until curl -sf http://localhost:11434/api/tags >/dev/null; do
  echo "Waiting for ollama..."; sleep 2; done
docker compose exec -T ollama ollama pull "${OLLAMA_CHAT_MODEL:-llama3}" || true
docker compose exec -T ollama ollama pull "${OLLAMA_EMBED_MODEL:-nomic-embed-text}" || true
echo "Models pulled."