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

    # ---- ESCRITURA (solo se llaman tras verificar el OTP) ----
    def create_product(self, name: str, price: float, in_stock: bool = True, variations: list | None = None):
        product = {"name": name, "price": price, "in_stock": in_stock}
        if variations:
            product["variations"] = [
                {"label": str(v.get("label", "")), "price": float(v.get("price", 0))}
                for v in variations
            ]
        return self._req("POST", "products.php", json={"action": "save", "product": product})

    def add_expense(self, date: str, concept: str, amount: float, vat: float = 0.0,
                    supplier: str = "", category: str = ""):
        return self._req("POST", "expenses.php", json={
            "action": "save", "date": date, "concept": concept, "supplier": supplier,
            "category": category, "amount": amount, "vat": vat,
        })

    def send_campaign(self, subject: str, html: str, audience: str = "all"):
        """Manda la campaña a TODOS por lotes hasta done=true. Devuelve total enviados."""
        sent, total, offset, guard = 0, 0, 0, 0
        while True:
            r = self._req("POST", "campaign.php", json={
                "subject": subject, "html": html, "audience": audience, "offset": offset, "limit": 25,
            })
            if not isinstance(r, dict) or r.get("error"):
                return r if isinstance(r, dict) else {"error": "respuesta inválida"}
            sent += int(r.get("sent", 0))
            total = int(r.get("total", 0))
            offset = int(r.get("next", offset))
            guard += 1
            if r.get("done") or guard > 400:
                break
        return {"ok": True, "sent": sent, "total": total}
