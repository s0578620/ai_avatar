import os
import uuid
from typing import List, Optional, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
import google.generativeai as genai

# --- Konfiguration aus Umgebungsvariablen ---
DEFAULT_PERSONA = (
    "You are an educational assistant for children between 8 and 13."
    "Explain things kindly and clearly, using simple language and concrete examples."
)

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_API_KEY)

CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
EMB_MODEL = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
TOP_K = int(os.getenv("TOP_K", "4"))


class RAG:
    def __init__(self):
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """
        Erzeugt für jeden Text einen Embedding-Vektor mit Gemini.
        EMB_MODEL = 'text-embedding-004' liefert 768-dimensionale Vektoren.
        """
        out: List[List[float]] = []
        for t in texts:
            if not t:
                out.append([0.0] * 768)
                continue

            res = genai.embed_content(
                model=EMB_MODEL,
                content=t,
                task_type="retrieval_document",
            )
            out.append(res["embedding"])
        return out

    # --------- Qdrant-Handling ---------

    def ensure_collection(self, name: str, size: int):
        collections = self.client.get_collections().collections
        names = [c.name for c in collections]
        if name not in names:
            self.client.create_collection(
                name=name,
                vectors_config=VectorParams(
                    size=size,
                    distance=Distance.COSINE,
                ),
            )

    def upsert_chunks(
        self,
        collection: str,
        chunks: List[str],
        metadata: dict | None = None,
    ) -> int:
        metadata = metadata or {}

        vecs = self._embed(chunks)
        if not vecs:
            return 0

        self.ensure_collection(collection, len(vecs[0]))

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=v,
                payload={"text": t, **metadata},
            )
            for t, v in zip(chunks, vecs)
        ]

        self.client.upsert(collection_name=collection, points=points)
        return len(points)

    def search(
            self,
            collection: str,
            query: str,
            filters: Optional[Dict[str, Any]] = None,
    ):
        q_vec = self._embed([query])[0]

        q_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                if value is None:
                    continue
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value),
                    )
                )
            if conditions:
                q_filter = Filter(must=conditions)

        res = self.client.search(
            collection_name=collection,
            query_vector=q_vec,
            limit=TOP_K,
            with_payload=True,
            query_filter=q_filter,
        )
        return [(r.score, r.payload) for r in res]

    # --------- Text-Splitting ---------

    def split_text(self, text: str):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=120,
        )
        return splitter.split_text(text)

    # --------- Generieren mit Gemini ---------

    def generate(self, prompt: str) -> str:
        """
        Ruft das Chatmodell von Gemini auf.
        """
        model = genai.GenerativeModel(CHAT_MODEL)
        resp = model.generate_content(prompt)

        return (resp.text or "").strip()

    # --------- Promptbau ---------

    def build_prompt(
            self,
            question: str,
            contexts: List[str],
            persona: str | None = None,
    ) -> str:
        # Wenn keine Persona mitgegeben wird, nimm die Standard-Persona
        persona_text = persona or DEFAULT_PERSONA

        if contexts:
            ctx_block = "\n\n".join(
                f"[CTX {i + 1}] {c}" for i, c in enumerate(contexts)
            )
        else:
            ctx_block = "[no context chunks found]"

        return f"""{persona_text}
    Use only the provided context to answer. If the answer is not in the context, say you don't know.

    [CONTEXT]
    {ctx_block}

    [QUESTION]
    {question}

    [ANSWER]"""
