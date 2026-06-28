"""
El "cerebro" conversacional.

- Habla como un compañero de equipo: razona, opina y DEBATE, usando la
  memoria de la empresa (notas/estrategias/transcripciones) como contexto,
  no como una camisa de fuerza.
- También sabe valorar la transcripción de un vídeo (si aporta a la marca).
Funciona con Groq (gratis) o Anthropic (de pago), según config.LLM_PROVIDER.
"""
from . import config, store

SYSTEM_PROMPT = (
    "Eres un miembro más del equipo de la empresa del usuario (marca Celestial: flores de CBD, "
    "hash y extracciones; e-commerce). Hablas en español, con criterio propio, como un compañero "
    "de trabajo listo, directo y con iniciativa.\n"
    "Tienes acceso a la MEMORIA de la empresa (notas, estrategias y transcripciones que se han ido "
    "guardando): úsala cuando sea relevante y menciona de qué nota sale. Pero NO te limites a "
    "repetirla: razona, da tu opinión y DEBATE. Puedes estar de acuerdo o en desacuerdo, proponer "
    "ideas y hacer preguntas para afinar.\n"
    "Si no hay nada guardado sobre algo, responde igualmente con criterio y di qué información "
    "faltaría o convendría buscar. Sé concreto y orientado a hacer crecer el negocio; nada de "
    "respuestas vacías ni de 'no tengo información'."
)

ANALYST_PROMPT = (
    "Eres el analista de contenidos de la marca Celestial (CBD / e-commerce / marketing / finanzas). "
    "Te paso la transcripción de un vídeo que el usuario cree que PODRÍA ser útil para la marca. "
    "Valóralo con honestidad. Responde en español, claro y breve, con este formato exacto:\n\n"
    "🎬 Tema: <de qué va, 1 línea>\n"
    "💡 Útil para la marca: <Sí / No / Quizá>  ·  Valoración: <X/10>\n"
    "🛠️ Cómo aplicarlo: <2-4 viñetas accionables, o '—' si no aplica>\n"
    "🔎 ¿Falta info?: <qué convendría buscar o confirmar, o 'no'>\n\n"
    "Si es paja, genérico o no tiene que ver con el negocio, dilo claramente sin adornos."
)

_groq = None
_anthropic = None


def _chat(messages: list) -> str:
    """Lanza una conversación completa (lista de mensajes role/content) al modelo elegido."""
    if config.LLM_PROVIDER == "anthropic":
        global _anthropic
        if _anthropic is None:
            from anthropic import Anthropic
            _anthropic = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        resp = _anthropic.messages.create(
            model=config.ANTHROPIC_MODEL, max_tokens=1500, system=system, messages=convo
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    global _groq
    if _groq is None:
        from groq import Groq
        _groq = Groq(api_key=config.GROQ_API_KEY)
    resp = _groq.chat.completions.create(
        model=config.GROQ_MODEL, max_tokens=1500, messages=messages
    )
    return resp.choices[0].message.content


def _context_block(question: str):
    """Recupera de la memoria los fragmentos más relevantes para la pregunta."""
    hits = store.search(question)
    if not hits:
        return "", []
    blocks = []
    for i, h in enumerate(hits, 1):
        meta = h["meta"]
        tag = f"[Nota {i} · {meta.get('date', '')} · {meta.get('source', '')}]"
        blocks.append(f"{tag}\n{h['text']}")
    return "\n\n---\n\n".join(blocks), hits


def ask(question: str, history: list | None = None) -> dict:
    """Responde conversando: memoria como contexto + historial de la charla + criterio propio."""
    context, hits = _context_block(question)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({
            "role": "system",
            "content": "MEMORIA DE LA EMPRESA (contexto relevante, úsala si encaja):\n\n" + context,
        })
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})
    return {"answer": _chat(messages), "sources": hits}


def analyze_transcript(transcript: str) -> str:
    """Valora la transcripción de un vídeo: tema, utilidad para la marca, cómo aplicarlo y si falta info."""
    snippet = transcript[:6000]
    messages = [
        {"role": "system", "content": ANALYST_PROMPT},
        {"role": "user", "content": "TRANSCRIPCIÓN DEL VÍDEO:\n\n" + snippet},
    ]
    return _chat(messages)
