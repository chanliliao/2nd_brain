"""
Embedding utilities for the second-brain RAG pipeline.

Uses fastembed with the sentence-transformers/all-MiniLM-L6-v2 model (384-dim, ONNX).
The model is downloaded and cached to ~/.cache/fastembed/ on first use.
"""

from fastembed import TextEmbedding

_embedder: TextEmbedding | None = None


def get_embedder() -> TextEmbedding:
    """Return the singleton TextEmbedding instance, initializing on first call."""
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
    return _embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Returns list of 384-dim float vectors."""
    return list(get_embedder().embed(texts))


def embed_one(text: str) -> list[float]:
    """Embed a single text. Returns a 384-dim float vector."""
    return embed_texts([text])[0]
