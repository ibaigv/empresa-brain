"""
Transcripción de vídeos/audios.

Saca la pista de audio con ffmpeg y la transcribe con Whisper de Groq
(whisper-large-v3-turbo): rápido y prácticamente gratis. No necesita GPU.
"""
import os
import subprocess

from . import config

_groq = None


def _client():
    global _groq
    if _groq is None:
        from groq import Groq
        _groq = Groq(api_key=config.GROQ_API_KEY)
    return _groq


def extract_audio(src_path: str) -> str:
    """Convierte el vídeo/audio de entrada a un mp3 mono 16 kHz (ligero para Whisper)."""
    out = src_path + ".mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", out],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return out


def transcribe(src_path: str) -> str:
    """Devuelve el texto transcrito de un vídeo o audio."""
    audio = extract_audio(src_path)
    try:
        with open(audio, "rb") as f:
            res = _client().audio.transcriptions.create(
                file=(os.path.basename(audio), f.read()),
                model=config.GROQ_WHISPER_MODEL,
            )
        return (getattr(res, "text", "") or "").strip()
    finally:
        try:
            os.remove(audio)
        except OSError:
            pass
