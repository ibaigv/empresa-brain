"""
API HTTP de la base de conocimiento.

La usa el conector MCP para que puedas hablar con tu IA de empresa
directamente desde Claude. Protegida con un token (API_TOKEN).
"""
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import config, store, rag

app = FastAPI(title="Empresa Brain")


def _auth(authorization: str | None):
    expected = f"Bearer {config.API_TOKEN}"
    if not config.API_TOKEN or authorization != expected:
        raise HTTPException(status_code=401, detail="No autorizado")


class NoteIn(BaseModel):
    text: str
    source: str = "claude"


class AskIn(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"ok": True, "notas": store.count()}


@app.post("/notes")
def add_note(body: NoteIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    n = store.add_note(body.text, source=body.source)
    return {"ok": True, "fragmentos_guardados": n}


@app.post("/search")
def search(body: AskIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    return {"resultados": store.search(body.question)}


@app.post("/ask")
def ask(body: AskIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    return rag.ask(body.question)
