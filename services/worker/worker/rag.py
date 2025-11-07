import os, uuid, requests
from typing import List
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct
from langchain_text_splitters import RecursiveCharacterTextSplitter

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3")
EMB_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
TOP_K = int(os.getenv("TOP_K", "4"))

class RAG:
    def __init__(self):
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    def _embed(self, texts: List[str]):
        out = []
        for t in texts:
            r = requests.post(f"{OLLAMA_BASE}/api/embeddings", json={"model": EMB_MODEL, "prompt": t})
            r.raise_for_status()
            out.append(r.json()["embedding"])
        return out

    def ensure_collection(self, name: str, size: int):
        names = [c.name for c in self.client.get_collections().collections]
        if name not in names:
            self.client.create_collection(name, vectors_config=VectorParams(size=size, distance=Distance.COSINE))

    def upsert_chunks(self, collection: str, chunks: List[str], metadata: dict | None = None):
        metadata = metadata or {}
        vecs = self._embed(chunks)
        self.ensure_collection(collection, len(vecs[0]))
        points = [PointStruct(id=str(uuid.uuid4()), vector=v, payload={"text": t, **metadata}) for t, v in zip(chunks, vecs)]
        self.client.upsert(collection, points=points)
        return len(points)

    def search(self, collection: str, query: str):
        q = self._embed([query])[0]
        res = self.client.search(collection, query_vector=q, limit=TOP_K, with_payload=True)
        return [(r.score, r.payload) for r in res]

    def split_text(self, text: str):
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
        return splitter.split_text(text)

    def generate(self, prompt: str) -> str:
        r = requests.post(f"{OLLAMA_BASE}/api/generate", json={"model": CHAT_MODEL, "prompt": prompt, "stream": False})
        r.raise_for_status()
        return r.json().get("response", "")

    def build_prompt(self, question: str, contexts: List[str]) -> str:
        ctx = "\n\n".join([f"[CTX {i+1}] {c}" for i, c in enumerate(contexts)])
        return f"""You are a helpful assistant. Use only the provided context to answer.
If the answer is not in the context, say you don't know.

[CONTEXT]
{ctx}

[QUESTION]
{question}

[ANSWER]"""