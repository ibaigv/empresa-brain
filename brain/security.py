"""
Verificación 2FA por correo para las acciones de ESCRITURA del bot.

Principio (ver HANDOFF-verificacion-2fa.md): la puerta es DETERMINISTA y vive en
código, no en el prompt del modelo. El modelo solo PROPONE una acción → aquí se
crea una "acción pendiente" y se manda un código al correo del dueño describiendo
QUÉ se va a hacer. La acción NO se ejecuta hasta que `verify()` recibe el código
correcto. Un código vale solo para SU acción (atado al payload), un único uso.
"""
import hashlib
import hmac
import os
import secrets
import smtplib
import ssl
import time
from datetime import datetime
from email.message import EmailMessage

from . import config

CODE_TTL = 300        # el código caduca a los 5 minutos
MAX_ATTEMPTS = 4      # intentos antes de cancelar la acción
ISSUE_WINDOW = 3600   # ventana de rate-limit de emisión (1 h)
ISSUE_MAX = 6         # máximo de códigos emitidos por chat en esa ventana

# Acción pendiente por chat (solo una a la vez; una nueva sustituye a la anterior).
_PENDING: dict = {}
_ISSUE_LOG: dict = {}


def _hash(code: str) -> str:
    """HMAC-SHA256 del código con el secreto del .env (nunca se guarda en claro)."""
    return hmac.new(config.OTP_SECRET.encode(), code.encode(), hashlib.sha256).hexdigest()


def _audit(line: str) -> None:
    """Registro de auditoría en el VPS (sin el código). Sobrevive a reinicios (volumen data/)."""
    try:
        path = os.path.join(config.DATA_DIR, "audit.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()}Z  {line}\n")
    except Exception:
        pass


def _send_email(desc: str, code: str) -> None:
    msg = EmailMessage()
    msg["From"] = config.SMTP_USER
    msg["To"] = config.OTP_EMAIL
    msg["Subject"] = "Código de verificación — acción del bot"
    msg.set_content(
        "El bot de tu empresa quiere realizar esta acción:\n\n"
        f"    {desc}\n\n"
        f"Código de verificación: {code}\n\n"
        "Caduca en 5 minutos y es de un solo uso. Pégalo en el bot para confirmar.\n"
        "Si NO has pedido tú esta acción, ignora este correo y NO compartas el código."
    )
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ctx, timeout=20) as s:
        s.login(config.SMTP_USER, config.SMTP_PASS)
        s.send_message(msg)


def _rate_ok(chat_id) -> bool:
    now = time.time()
    log = [t for t in _ISSUE_LOG.get(chat_id, []) if now - t < ISSUE_WINDOW]
    _ISSUE_LOG[chat_id] = log
    return len(log) < ISSUE_MAX


def looks_like_code(text: str) -> bool:
    t = (text or "").strip().replace(" ", "")
    return t.isdigit() and len(t) == 6


def has_pending(chat_id) -> bool:
    p = _PENDING.get(chat_id)
    return bool(p) and time.time() <= p["expires"]


def request(chat_id, action_type: str, payload: dict, desc: str) -> dict:
    """Crea la acción pendiente y manda el código por correo. NO ejecuta nada."""
    if not config.OTP_SECRET or not config.SMTP_PASS:
        return {"ok": False, "msg": "El 2FA no está configurado (faltan OTP_SECRET / SMTP en el .env)."}
    if not _rate_ok(chat_id):
        return {"ok": False, "msg": "Demasiados códigos pedidos en poco tiempo. Espera un rato."}
    code = f"{secrets.randbelow(1_000_000):06d}"
    _PENDING[chat_id] = {
        "id": secrets.token_hex(8),
        "type": action_type,
        "payload": payload,
        "code_hash": _hash(code),
        "expires": time.time() + CODE_TTL,
        "attempts": 0,
        "desc": desc,
    }
    _ISSUE_LOG.setdefault(chat_id, []).append(time.time())
    try:
        _send_email(desc, code)
    except Exception as e:
        _PENDING.pop(chat_id, None)
        return {"ok": False, "msg": f"No pude enviar el código por correo ({e})."}
    _audit(f"chat={chat_id} REQUEST {action_type} :: {desc}")
    return {"ok": True, "desc": desc}


def verify(chat_id, code: str):
    """Verifica el código. Devuelve ((tipo, payload), desc) si es válido, o (None, motivo)."""
    p = _PENDING.get(chat_id)
    if not p:
        return None, "No hay ninguna acción pendiente de confirmar."
    if time.time() > p["expires"]:
        _PENDING.pop(chat_id, None)
        _audit(f"chat={chat_id} EXPIRED {p['type']}")
        return None, "El código ha caducado. Pídeme otra vez la acción."
    p["attempts"] += 1
    if p["attempts"] > MAX_ATTEMPTS:
        _PENDING.pop(chat_id, None)
        _audit(f"chat={chat_id} BLOCKED {p['type']} (demasiados intentos)")
        return None, "Demasiados intentos. He cancelado la acción por seguridad."
    given = (code or "").strip().replace(" ", "")
    if not hmac.compare_digest(p["code_hash"], _hash(given)):
        left = MAX_ATTEMPTS - p["attempts"]
        return None, f"Código incorrecto. Te quedan {left} intentos."
    _PENDING.pop(chat_id, None)
    _audit(f"chat={chat_id} VERIFIED {p['type']} :: {p['desc']}")
    return (p["type"], p["payload"]), p["desc"]
