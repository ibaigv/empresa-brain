"""
Conector MCP para hablar con tu IA de empresa DESDE Claude.

Expone 3 herramientas a Claude:
  - guardar_nota(texto)      -> guarda una nota en la base de conocimiento
  - buscar(consulta)         -> devuelve fragmentos relevantes
  - preguntar(pregunta)      -> respuesta razonada con tus notas

Se conecta por HTTP a la API que corre en tu VPS.
Configura la URL y el token con variables de entorno:
  BRAIN_API_URL   (ej. http://TU_IP_VPS:8000)
  BRAIN_API_TOKEN (el mismo API_TOKEN del .env del servidor)
"""
import os
import json
import urllib.request

from mcp.server.fastmcp import FastMCP

API_URL = os.environ.get("BRAIN_API_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.environ.get("BRAIN_API_TOKEN", "")

mcp = FastMCP("empresa-brain")


def _post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{API_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_TOKEN}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


@mcp.tool()
def guardar_nota(texto: str) -> str:
    """Guarda una nota, estrategia o idea en la memoria de la empresa."""
    r = _post("/notes", {"text": texto, "source": "claude"})
    return f"Guardado ({r.get('fragmentos_guardados', 0)} fragmento/s)."


@mcp.tool()
def buscar(consulta: str) -> str:
    """Busca en la memoria de la empresa los fragmentos más relevantes."""
    r = _post("/search", {"question": consulta})
    hits = r.get("resultados", [])
    if not hits:
        return "No hay nada relacionado guardado todavía."
    return "\n\n".join(f"- ({h['meta'].get('date','')}) {h['text']}" for h in hits)


@mcp.tool()
def preguntar(pregunta: str) -> str:
    """Pregunta a la IA de la empresa; responde usando todo el conocimiento guardado."""
    r = _post("/ask", {"question": pregunta})
    return r.get("answer", "(sin respuesta)")


if __name__ == "__main__":
    mcp.run()
