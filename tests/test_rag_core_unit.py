# tests/test_rag_core_unit.py
import os

# Dummy-Key, damit der Import von rag_core nicht crasht
os.environ.setdefault("GEMINI_API_KEY", "dummy")

from services.shared.rag_core import RAG


def test_split_text_basic():
    rag = RAG()
    text = "Hallo Welt. " * 200  # lang genug, damit gesplittet wird

    chunks = rag.split_text(text)

    assert isinstance(chunks, list)
    assert len(chunks) > 1           # sollte in mehrere Stücke geteilt werden
    assert all(isinstance(c, str) for c in chunks)
    # Sicherheit: keine extrem großen Chunks
    assert all(len(c) <= 900 for c in chunks)


def test_build_prompt_default_persona():
    rag = RAG()
    question = "Was ist die Hauptstadt von Frankreich?"
    contexts = ["Paris ist die Hauptstadt von Frankreich."]

    prompt = rag.build_prompt(question, contexts)

    assert "You are an educational assistant for children between 8 and 13." in prompt
    assert "[CTX 1]" in prompt
    assert contexts[0] in prompt
    assert "[QUESTION]" in prompt
    assert question in prompt


def test_build_prompt_custom_persona():
    rag = RAG()
    question = "Erkläre den Satz des Pythagoras."
    contexts = ["Im rechtwinkligen Dreieck gilt a² + b² = c²."]
    persona = "You are a friendly math tutor."

    prompt = rag.build_prompt(question, contexts, persona=persona)

    assert persona in prompt
    assert "educational assistant for children between 8 and 13" not in prompt
