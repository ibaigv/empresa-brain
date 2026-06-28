"""
Cliente del panel de administración del dashboard (celestialflowers).

Inicia sesión con la contraseña de admin y llama a los endpoints /api/admin/*.
De momento solo LECTURA (ventas, pedidos, productos, clientes); las acciones de
escritura/envío irán con verificación 2FA por correo (Fase 2).
"""
import requests

from . import config


class Dashboard:
    def __init__(self):
        self.base = config.DASHBOARD_URL.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "empresa-brain-bot"})
        self._logged = False

    def _login(self) -> bool:
        try:
            r = self.s.post(
                f"{self.base}/api/admin/login.php",
                json={"password": config.DASH_ADMIN_PASS},
                timeout=20,
            )
            self._logged = bool(r.ok and (r.json() or {}).get("ok"))
        except Exception:
            self._logged = False
        return self._logged

    def _req(self, method: str, path: str, **kw):
        if not self._logged and not self._login():
            return {"error": "No pude entrar al panel (revisa DASH_ADMIN_PASS / DASHBOARD_URL)."}
        url = f"{self.base}/api/admin/{path}"
        try:
            r = self.s.request(method, url, timeout=30, **kw)
            if r.status_code == 401:  # sesión caducada -> reintenta una vez
                if self._login():
                    r = self.s.request(method, url, timeout=30, **kw)
            try:
                return r.json()
            except Exception:
                return {"error": f"Respuesta no-JSON del panel ({r.status_code})."}
        except Exception as e:
            return {"error": f"No pude contactar el panel: {e}"}

    # ---- LECTURA ----
    def stats(self, month: str = ""):
        return self._req("GET", "stats.php" + (f"?month={month}" if month else ""))

    def orders(self):
        return self._req("GET", "orders.php")

    def products(self):
        return self._req("GET", "products.php")

    def customers(self):
        return self._req("GET", "customers.php")
