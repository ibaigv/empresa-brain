# 🧠 Empresa Brain — la inteligencia privada de tu empresa

Una IA a la que le envías notas, estrategias e ideas, y que luego responde
preguntas usando todo ese conocimiento. Privada: tus notas viven en **tu VPS**.

- **Desde Telegram** → le mandas notas y le preguntas como a un contacto.
- **Desde Claude** → un conector MCP para consultar y guardar sin salir de Claude.
- **El razonamiento** lo pone **Groq (gratis, Llama 3.3 70B)** por defecto, o
  **Claude por API** si lo prefieres. Las notas y la búsqueda (embeddings)
  corren en local en tu VPS, sin GPU. Con Groq, **todo el sistema es 0 €**.

## Cómo funciona

```
Tus notas ─► se trocean y se convierten en vectores ─► ChromaDB (en tu VPS)
                                                              │
Pregunta ──► busca lo relevante ──► Claude API redacta la respuesta ──► tú
```

## Piezas

| Archivo | Qué hace |
|---|---|
| `brain/store.py` | Base de conocimiento (ChromaDB + embeddings locales multilingües) |
| `brain/rag.py` | Busca contexto y pide la respuesta a Claude |
| `brain/server.py` | API HTTP protegida con token (la usa el MCP) |
| `brain/bot.py` | Bot de Telegram |
| `brain/run.py` | Arranca API + bot juntos |
| `mcp_connector/` | Conector MCP para usarlo desde Claude |
| `docker-compose.yml` | Despliegue en el VPS con un comando |

## Lo que necesitas (3 cosas, todas gratis)

1. **Clave de Groq** (gratis) — https://console.groq.com/keys
2. **Token del bot de Telegram** — escribe a `@BotFather`, `/newbot`
3. **Tu ID de Telegram** — escribe a `@userinfobot`

Ponlos en un archivo `.env` (copia de `.env.example`).

👉 Para desplegar en el VPS de Hostinger, sigue **[DEPLOY.md](DEPLOY.md)**.
