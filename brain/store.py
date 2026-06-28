"""
Base de conocimiento de la empresa.

Guarda las notas troceadas en una base de datos vectorial (ChromaDB) y usa
un modelo de embeddings local (multilingüe, funciona en CPU) para poder
buscar por significado, no solo por palabras exactas.
"""
import os
import time
import uuid
import threading
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

from . import config

# Un solo candado para serializar accesos (el bot de Telegram y la API
# corren en hilos distintos y comparten la misma base).
_lock = threading.Lock()

_model: Optional[SentenceTransformer] = None
_collection = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        client = chromadb.PersistentClient(path=os.path.join(config.DATA_DIR, "chroma"))
        _collection = client.get_or_create_collection(
            name="empresa", metadata={"hnsw:space": "cosine"}
        )
    return _collection


# El modelo e5 espera prefijos "passage:" (al guardar) y "query:" (al buscar).
def _embed_passages(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return model.encode([f"passage: {t}" for t in texts], normalize_embeddings=True).tolist()


def _embed_query(text: str) -> list[float]:
    model = _get_model()
    return model.encode(f"query: {text}", normalize_embeddings=True).tolist()


def _chunk(text: str, max_chars: int = 1200) -> list[str]:
    """Trocea texto largo respetando párrafos."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    chunks, current = [], ""
    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 > max_chars and current:
            chunks.append(current.strip())
            current = ""
        current += para + "\n\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


def add_note(text: str, source: str = "telegram") -> int:
    """Guarda una nota en la base de conocimiento. Devuelve nº de fragmentos."""
    text = (text or "").strip()
    if not text:
        return 0
    chunks = _chunk(text)
    ts = time.strftime("%Y-%m-%d %H:%M")
    with _lock:
        col = _get_collection()
        embeddings = _embed_passages(chunks)
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [{"source": source, "date": ts} for _ in chunks]
        col.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
    return len(chunks)


def search(query: str, k: int = config.TOP_K) -> list[dict]:
    """Devuelve los fragmentos más relevantes para una pregunta."""
    query = (query or "").strip()
    if not query:
        return []
    with _lock:
        col = _get_collection()
        if col.count() == 0:
            return []
        emb = _embed_query(query)
        res = col.query(query_embeddings=[emb], n_results=min(k, col.count()))
    out = []
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        out.append({"text": doc, "meta": meta or {}, "score": 1 - dist})
    return out


def count() -> int:
    with _lock:
        return _get_collection().count()
