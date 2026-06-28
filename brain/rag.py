"""
El "cerebro" conversacional.

- Habla como un compañero de equipo: razona, opina y DEBATE, usando la
  memoria de la empresa (notas/estrategias/transcripciones) como contexto,
  no como una camisa de fuerza.
- También sabe valorar la transcripción de un vídeo (si aporta a la marca).
Funciona con Groq (gratis) o Anthropic (de pago), según config.LLM_PROVIDER.
"""
import json

from . import config, store, web

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
    "respuestas vacías ni de 'no tengo información'.\n"
    "Además tienes HERRAMIENTAS para consultar datos REALES de la tienda en vivo (ventas, "
    "pedidos, productos/stock): úsalas cuando pregunten por esos datos y responde con cifras "
    "reales, nunca inventadas."
)

# --- Herramientas de consulta (solo lectura) al panel del dashboard ---
TOOLS = [
    {"type": "function", "function": {
        "name": "ventas_stats",
        "description": "Estadísticas reales de la tienda: nº de pedidos, ingresos, pedidos por estado y ventas por mes. Úsalo para 'cómo van las ventas', 'cuánto he facturado', 'cuántos pedidos llevo'.",
        "parameters": {"type": "object", "properties": {
            "month": {"type": "string", "description": "Mes en formato YYYY-MM (opcional; vacío = global)"}
        }},
    }},
    {"type": "function", "function": {
        "name": "pedidos_recientes",
        "description": "Lista de los pedidos recientes (referencia, cliente, total, estado). Úsalo para 'qué pedidos hay', 'últimos pedidos', 'pedidos pendientes'.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "productos",
        "description": "Lista de productos de la tienda (nombre, precio, stock). Úsalo para 'qué productos tengo', 'stock', 'qué hay en la tienda'.",
        "parameters": {"type": "object", "properties": {}},
    }},
]

_dash = None


def _dashboard():
    global _dash
    if _dash is None:
        _dash = web.Dashboard()
    return _dash


def _dispatch_tool(name: str, args: dict):
    d = _dashboard()
    if name == "ventas_stats":
        return d.stats(args.get("month", ""))
    if name == "pedidos_recientes":
        return d.orders()
    if name == "productos":
        return d.products()
    return {"error": f"herramienta desconocida: {name}"}

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


def _chat_with_tools(messages: list) -> str:
    """Conversa con herramientas (Groq). Si el modelo pide consultar la tienda,
    ejecuta la consulta real y vuelve a pedirle la respuesta final con esos datos."""
    global _groq
    if _groq is None:
        from groq import Groq
        _groq = Groq(api_key=config.GROQ_API_KEY)
    resp = _groq.chat.completions.create(
        model=config.GROQ_MODEL, max_tokens=1500, messages=messages,
        tools=TOOLS, tool_choice="auto",
    )
    msg = resp.choices[0].message
    if not msg.tool_calls:
        return msg.content
    messages.append({
        "role": "assistant", "content": msg.content or "",
        "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ],
    })
    for tc in msg.tool_calls:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except Exception:
            args = {}
        result = _dispatch_tool(tc.function.name, args)
        messages.append({
            "role": "tool", "tool_call_id": tc.id,
            "content": json.dumps(result, ensure_ascii=False)[:8000],
        })
    resp = _groq.chat.completions.create(
        model=config.GROQ_MODEL, max_tokens=1500, messages=messages,
    )
    return resp.choices[0].message.content


def ask(question: str, history: list | None = None) -> dict:
    """Responde conversando: memoria como contexto + historial + datos reales de la tienda."""
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
    if config.LLM_PROVIDER == "anthropic":
        answer = _chat(messages)
    else:
        answer = _chat_with_tools(messages)
    return {"answer": answer, "sources": hits}


def analyze_transcript(transcript: str) -> str:
    """Valora la transcripción de un vídeo: tema, utilidad para la marca, cómo aplicarlo y si falta info."""
    snippet = transcript[:6000]
    messages = [
        {"role": "system", "content": ANALYST_PROMPT},
        {"role": "user", "content": "TRANSCRIPCIÓN DEL VÍDEO:\n\n" + snippet},
    ]
    return _chat(messages)
