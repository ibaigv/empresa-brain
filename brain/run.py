"""
Arranque único: lanza la API HTTP (para Claude/MCP) y el bot de Telegram juntos.

- La API corre en un hilo de fondo con uvicorn.
- El bot de Telegram corre en el hilo principal (long polling, no necesita
  dominio ni certificado SSL).
"""
import threading

import uvicorn

from . import config
from .bot import build_app
from .server import app as api_app


def _run_api():
    uvicorn.run(api_app, host="0.0.0.0", port=8000, log_level="info")


def main():
    if config.LLM_PROVIDER == "anthropic" and not config.ANTHROPIC_API_KEY:
        raise SystemExit("Falta ANTHROPIC_API_KEY en el .env (LLM_PROVIDER=anthropic)")
    if config.LLM_PROVIDER == "groq" and not config.GROQ_API_KEY:
        raise SystemExit("Falta GROQ_API_KEY en el .env (LLM_PROVIDER=groq)")
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en el .env")

    # API en segundo plano
    threading.Thread(target=_run_api, daemon=True).start()

    # Bot de Telegram en primer plano (bloquea)
    print("🧠 Empresa Brain en marcha. Bot de Telegram escuchando…")
    build_app().run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
