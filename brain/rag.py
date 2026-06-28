"""
El "cerebro": coge la pregunta, busca lo relevante en la base de conocimiento
y le pide al modelo (Groq gratis, o Claude de pago) que responda basándose
SOLO en esa información.
"""
from . import config, store

SYSTEM_PROMPT = (
    "Eres la inteligencia privada de la empresa del usuario. Respondes en español, "
    "de forma clara y directa, basándote ÚNICAMENTE en las notas y estrategias que "
    "te paso como contexto. Si el contexto no contiene la respuesta, dilo claramente "
    "y no te inventes nada. Cuando sea útil, cita de qué nota sale la información."
)

# --- Clientes (se crean una sola vez, según el proveedor elegido) ---
_groq = None
_anthropic = None


def _ask_groq(system: str, user_msg: str) -> str:
    global _groq
    if _groq is None:
        from groq import Groq
        _groq = Groq(api_key=config.GROQ_API_KEY)
    resp = _groq.chat.completions.create(
        model=config.GROQ_MODEL,
        max_tokens=1500,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )
    return resp.choices[0].message.content


def _ask_anthropic(system: str, user_msg: str) -> str:
    global _anthropic
    if _anthropic is None:
        from anthropic import Anthropic
        _anthropic = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = _anthropic.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def _generate(system: str, user_msg: str) -> str:
    if config.LLM_PROVIDER == "anthropic":
        return _ask_anthropic(system, user_msg)
    return _ask_groq(system, user_msg)


def ask(question: str) -> dict:
    """Responde una pregunta usando el conocimiento guardado."""
    hits = store.search(question)
    if not hits:
        return {
            "answer": "Todavía no tengo nada guardado sobre eso. Envíame notas y estrategias primero.",
            "sources": [],
        }

    context_blocks = []
    for i, h in enumerate(hits, 1):
        meta = h["meta"]
        tag = f"[Nota {i} · {meta.get('date', '')} · {meta.get('source', '')}]"
        context_blocks.append(f"{tag}\n{h['text']}")
    context = "\n\n---\n\n".join(context_blocks)

    user_msg = (
        f"CONTEXTO (notas de la empresa):\n\n{context}\n\n"
        f"=========\n\nPREGUNTA: {question}"
    )

    answer = _generate(SYSTEM_PROMPT, user_msg)
    return {"answer": answer, "sources": hits}
