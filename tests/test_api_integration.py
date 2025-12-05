# tests/test_api_integration.py
import os
import time

import pytest
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")


@pytest.mark.integration
def test_full_rag_flow():
    collection = "test_collection_pytest"

    ingest_payload = {
        "text": "Paris ist die Hauptstadt von Frankreich.",
        "collection": collection,
        "doc_id": "doc1",
        "metadata": {"source": "pytest"},
    }
    r_ingest = requests.post(f"{API_URL}/ingest", json=ingest_payload)
    assert r_ingest.status_code == 200
    ingest_data = r_ingest.json()
    task_id = ingest_data["task_id"]
    assert task_id

    for _ in range(30):
        time.sleep(1)
        r_task = requests.get(f"{API_URL}/tasks/{task_id}")
        assert r_task.status_code == 200
        data = r_task.json()
        if data["status"] == "SUCCESS":
            break
    else:
        pytest.fail("Ingest task did not finish in time")

    chat_payload = {
        "message": "Was ist die Hauptstadt von Frankreich?",
        "session_id": "pytest-session",
        "collection": collection,
    }
    r_chat = requests.post(f"{API_URL}/chat", json=chat_payload)
    assert r_chat.status_code == 200
    chat_task_id = r_chat.json()["task_id"]
    assert chat_task_id

    for _ in range(30):
        time.sleep(1)
        r_task2 = requests.get(f"{API_URL}/tasks/{chat_task_id}")
        assert r_task2.status_code == 200
        data2 = r_task2.json()
        if data2["status"] == "SUCCESS":
            break
    else:
        pytest.fail("Chat task did not finish in time")

    # Ergebnis prüfen
    result = data2["result"]
    assert "answer" in result
    assert result["answer"]  # nicht leer
