# 🚀 Desplegar en el VPS de Hostinger

Guía paso a paso. Cuando me des acceso SSH, yo ejecuto todo esto por ti.

## 0. Requisitos previos (tú)

Consigue las 3 cosas y tenlas a mano (todas gratis):

- `GROQ_API_KEY` — https://console.groq.com/keys (inicia sesión → Create API Key)
- `TELEGRAM_BOT_TOKEN` — escribe a `@BotFather` en Telegram → `/newbot`
- Tu `TELEGRAM_ID` — escribe a `@userinfobot` (te da un número)

## 1. Conectar al VPS

```bash
ssh root@TU_IP_VPS
```

## 2. Instalar Docker (si no está)

```bash
curl -fsSL https://get.docker.com | sh
```

## 3. Subir el proyecto

Opción A — con git (si lo subes a un repo):
```bash
git clone TU_REPO empresa-brain && cd empresa-brain
```

Opción B — copiarlo por SCP desde tu PC:
```bash
scp -r ./empresa-brain root@TU_IP_VPS:/root/
```

## 4. Crear el .env

```bash
cd empresa-brain
cp .env.example .env
nano .env   # rellena las 3 claves + invéntate un API_TOKEN largo
```

## 5. Arrancar

```bash
docker compose up -d --build
```

Comprueba que va:
```bash
docker compose logs -f          # deberías ver "Bot de Telegram escuchando…"
curl localhost:8000/health      # {"ok":true,"notas":0}
```

## 6. Probar desde Telegram

Abre tu bot en Telegram, escribe `/start`, mándale una nota de prueba y luego
una pregunta acabada en `?`.

## 7. (Opcional) Conector MCP desde Claude

> ⚠️ Seguridad: el puerto 8000 queda accesible desde fuera. Para producción
> conviene abrirlo solo a tu IP en el firewall, o ponerle un dominio con HTTPS
> (nginx + certbot). Para empezar y probar, vale tal cual con el `API_TOKEN`.

En tu PC, instala el conector:
```bash
cd mcp_connector
pip install -r requirements.txt
```

Añádelo a la config de MCP de Claude (Claude Desktop / Claude Code),
en `mcpServers`:

```json
{
  "mcpServers": {
    "empresa-brain": {
      "command": "python",
      "args": ["RUTA/A/empresa-brain/mcp_connector/empresa_brain_mcp.py"],
      "env": {
        "BRAIN_API_URL": "http://TU_IP_VPS:8000",
        "BRAIN_API_TOKEN": "el-mismo-API_TOKEN-del-.env"
      }
    }
  }
}
```

Reinicia Claude y ya podrás decir cosas como *"guarda esta estrategia…"* o
*"¿qué teníamos sobre el plan de precios?"* directamente en Claude.

## Mantenimiento

```bash
docker compose restart      # reiniciar
docker compose down         # parar
docker compose up -d --build  # actualizar tras cambios
```

La base de conocimiento se guarda en `./data` (haz copias de seguridad de esa carpeta).
