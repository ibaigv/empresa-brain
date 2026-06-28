"""
Bot de Telegram: compañero de equipo de la marca.

- Cualquier mensaje de texto -> conversa y DEBATE contigo (con memoria de la
  charla + la memoria de la empresa como contexto).
- Mándale un VÍDEO (o reenvíale un reel) -> lo transcribe, lo valora para la
  marca y lo guarda en la memoria.
- /guardar <texto>  -> guarda una nota/estrategia.
- /buscar <texto>   -> muestra de dónde sale la info.
- /estado           -> cuánto conocimiento hay guardado.
- /reset            -> empieza la conversación de cero.

Solo responde a los IDs autorizados (TELEGRAM_ALLOWED_IDS).
"""
import asyncio
import os
import tempfile
from collections import defaultdict, deque

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from . import config, store, rag, media

# Historial de conversación por chat (para poder debatir con contexto).
HISTORY = defaultdict(lambda: deque(maxlen=config.HISTORY_TURNS * 2))


def _authorized(update: Update) -> bool:
    user = update.effective_user
    if not config.TELEGRAM_ALLOWED_IDS:
        return True
    return bool(user and user.id in config.TELEGRAM_ALLOWED_IDS)


async def _deny(update: Update):
    await update.message.reply_text("⛔ No estás autorizado para usar este bot.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return await _deny(update)
    await update.message.reply_text(
        "🧠 Soy tu compañero de equipo de Celestial. Háblame normal: te doy mi opinión, "
        "debatimos y tiro de lo que vamos guardando.\n\n"
        "• Mándame un *vídeo* (o reenvíame un reel) y lo transcribo, lo analizo y te digo "
        "si es útil para la marca.\n"
        "• /guardar <texto> — guardo una nota o estrategia en la memoria.\n"
        "• /buscar <texto> — te enseño de dónde sale la info.\n"
        "• /estado — cuánto conocimiento tengo guardado.\n"
        "• /reset — empezar la conversación de cero.",
        parse_mode="Markdown",
    )


async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return await _deny(update)
    n = await asyncio.to_thread(store.count)
    await update.message.reply_text(f"📚 Tengo {n} fragmentos de conocimiento guardados.")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return await _deny(update)
    HISTORY[update.effective_chat.id].clear()
    await update.message.reply_text("🧹 Conversación reiniciada. Empezamos de cero.")


async def guardar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return await _deny(update)
    text = " ".join(context.args).strip()
    if not text:
        return await update.message.reply_text("Escribe: /guardar <lo que quieras que recuerde>")
    n = await asyncio.to_thread(store.add_note, text, "telegram")
    await update.message.reply_text(f"📝 Guardado en la memoria ({n} fragmento/s).")


async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return await _deny(update)
    query = " ".join(context.args).strip()
    if not query:
        return await update.message.reply_text("Escribe: /buscar <texto>")
    hits = await asyncio.to_thread(store.search, query)
    if not hits:
        return await update.message.reply_text("No encontré nada relacionado.")
    lines = [f"• ({h['meta'].get('date', '')}) {h['text'][:200]}…" for h in hits]
    await update.message.reply_text("🔎 Relacionado:\n\n" + "\n\n".join(lines))


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Conversación libre: opina, debate y usa la memoria como contexto."""
    if not _authorized(update):
        return await _deny(update)
    msg = (update.message.text or "").strip()
    if not msg:
        return
    cid = update.effective_chat.id
    hist = list(HISTORY[cid])
    await update.message.chat.send_action("typing")
    result = await asyncio.to_thread(rag.ask, msg, hist)
    answer = result["answer"]
    HISTORY[cid].append({"role": "user", "content": msg})
    HISTORY[cid].append({"role": "assistant", "content": answer})
    await update.message.reply_text(answer)


async def on_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vídeo / audio / reel reenviado -> transcribe, valora y guarda."""
    if not _authorized(update):
        return await _deny(update)
    m = update.message
    obj = m.video or m.video_note or m.audio or m.voice or m.document
    if obj is None:
        return
    size = getattr(obj, "file_size", 0) or 0
    if size > 19 * 1024 * 1024:
        return await m.reply_text(
            "⚠️ Pesa más de 20 MB y Telegram no me deja descargarlo. Mándame uno más corto."
        )
    await m.reply_text("🎬 Recibido. Descargando y transcribiendo…")
    await m.chat.send_action("typing")
    tmp = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
    tmp.close()
    try:
        tf = await obj.get_file()
        await tf.download_to_drive(tmp.name)
        transcript = await asyncio.to_thread(media.transcribe, tmp.name)
        if not transcript:
            return await m.reply_text("No pude sacar audio ni transcripción de ese archivo.")
        verdict = await asyncio.to_thread(rag.analyze_transcript, transcript)
        note = f"[Vídeo analizado]\n{verdict}\n\n— Transcripción —\n{transcript}"
        await asyncio.to_thread(store.add_note, note, "video")
        await m.reply_text(verdict + "\n\n✅ Guardado en la memoria (te lo encontraré cuando preguntes).")
    except Exception as e:
        await m.reply_text(f"Se me ha torcido procesando el vídeo: {e}")
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def build_app() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "ayuda"], start))
    app.add_handler(CommandHandler("estado", estado))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("guardar", guardar))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(MessageHandler(
        filters.VIDEO | filters.VIDEO_NOTE | filters.AUDIO | filters.VOICE | filters.Document.ALL,
        on_media,
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    return app
