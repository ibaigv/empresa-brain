"""Configuración central. Lee las variables del archivo .env"""
import os
from dotenv import load_dotenv

load_dotenv()

# Proveedor del "cerebro" que redacta las respuestas: "groq" (gratis) o "anthropic" (Claude, de pago)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

# --- Groq (gratis) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# Modelo potente y gratuito de Groq. Alternativas: llama-3.1-8b-instant (más rápido),
# openai/gpt-oss-120b, deepseek-r1-distill-llama-70b
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# --- Anthropic (Claude, de pago, opcional) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
# Lista de IDs de Telegram autorizados (separados por coma)
TELEGRAM_ALLOWED_IDS = {
    int(x) for x in os.getenv("TELEGRAM_ALLOWED_IDS", "").replace(" ", "").split(",") if x
}

API_TOKEN = os.getenv("API_TOKEN", "")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
DATA_DIR = os.getenv("DATA_DIR", "./data")

# Cuántos fragmentos de conocimiento se le pasan al modelo por pregunta
TOP_K = int(os.getenv("TOP_K", "6"))

# Modelo de transcripción de vídeos/audios (Whisper de Groq: gratis y rápido)
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

# Cuántos turnos (ida + vuelta) de conversación recuerda el bot para poder debatir
HISTORY_TURNS = int(os.getenv("HISTORY_TURNS", "8"))
