"""
Bot de Telegram.

- Cualquier mensaje normal -> se guarda como nota en la base de conocimiento.
- /preguntar <texto>  (o un mensaje que acabe en "?") -> Claude responde.
- /buscar <texto>     -> muestra los fragmentos relevantes sin redactar respuesta.
- /estado             -> cuántas notas hay guardadas.

Solo responde a los IDs de Telegram autorizados (TELEGRAM_ALLOWED_IDS).
"""
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from . import config, store, rag


def _authorized(update: Update) -> bool:
    user = update.effective_user
    if not config.TELEGRAM_ALLOWED_IDS:
        return True  # sin lista = abierto (no recomendado)
    return bool(user and user.id in config.TELEGRAM_ALLOWED_IDS)


async def _deny(update: Update):
    await update.message.reply_text("⛔ No estás autorizado para usar este bot.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return await _deny(update)
    await update.message.reply_text(
        "🧠 Soy la inteligencia de tu empresa.\n\n"
        "• Mándame notas, estrategias o ideas y las guardo.\n"
        "• Para preguntarme: /preguntar <tu pregunta> (o acaba el mensaje con ?)\n"
        "• /buscar <texto> — ver de dónde sale la info\n"
        "• /estado — cuántas notas tengo guardadas"
    )


async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return await _deny(update)
    await update.message.reply_text(f"📚 Tengo {store.count()} fragmentos guardados.")


async def preguntar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return await _deny(update)
    question = " ".join(context.args).strip()
    if not question:
        return await update.message.reply_text("Escribe: /preguntar <tu pregunta>")
    await _responder(update, question)


async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return await _deny(update)
    query = " ".join(context.args).strip()
    if not query:
        return await update.message.reply_text("Escribe: /buscar <texto>")
    hits = store.search(query)
    if not hits:
        return await update.message.reply_text("No encontré nada relacionado.")
    lines = [f"• ({h['meta'].get('date','')}) {h['text'][:200]}…" for h in hits]
    await update.message.reply_text("🔎 Relacionado:\n\n" + "\n\n".join(lines))


async def texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensaje suelto: pregunta si acaba en '?', si no se guarda como nota."""
    if not _authorized(update):
        return await _deny(update)
    msg = (update.message.text or "").strip()
    if msg.endswith("?"):
        return await _responder(update, msg)
    n = store.add_note(msg, source="telegram")
    await update.message.reply_text(f"📝 Guardado ({n} fragmento/s).")


async def _responder(update: Update, question: str):
    await update.message.chat.send_action("typing")
    result = rag.ask(question)
    await update.message.reply_text(result["answer"])


def build_app() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", start))
    app.add_handler(CommandHandler("estado", estado))
    app.add_handler(CommandHandler("preguntar", preguntar))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto))
    return app
