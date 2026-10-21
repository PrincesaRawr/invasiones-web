"""Página pública del daño de las Invasiones.

No lee la pantalla: el Analizador de Invasiones del PC le envía los resúmenes ya
calculados a /api/subir cada pocos segundos, y aquí solo se guardan (en memoria) y
se enseñan a quien entre en la página.
"""
import hashlib
import hmac
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CARPETA = os.path.dirname(os.path.abspath(__file__))
RUTA_WEB = os.path.join(CARPETA, "web", "index.html")
# SHA-256 de la clave que usa el PC para subir datos (la clave en sí no está en el repo)
HUELLA_CLAVE = "7345e702b6d87cd5243afaac893bec94884fea20f913a165fc025099e7cf030b"
MAXIMO_SUBIDA = 5 * 1024 * 1024

cerrojo = threading.Lock()
estado = {"invasiones": [], "resumenes": {}, "ultima": None, "recibido": None}


def vacio():
    return {"invasiones": [], "invasion": None, "en_directo": False, "segundos_desde_lectura": None,
            "jugadores": [], "tipos": [], "tramos": [], "ultimos": []}


def datos_para(invasion):
    with cerrojo:
        resumenes = estado["resumenes"]
        if invasion not in resumenes:
            invasion = estado["ultima"]
        if invasion not in resumenes:
            salida = vacio()
        else:
            salida = dict(resumenes[invasion])
            salida["en_directo"] = invasion == estado["ultima"] and salida.get("en_directo", False)
            # lo que llevaba el PC sin ver la invasión + lo que ha pasado desde que lo envió
            if salida.get("segundos_desde_lectura") is not None and estado["recibido"]:
                salida["segundos_desde_lectura"] += round(time.time() - estado["recibido"])
        salida["invasiones"] = estado["invasiones"]
        if estado["recibido"] is None or time.time() - estado["recibido"] > 30:
            salida["pc_desconectado"] = True
        return salida


def guardar(paquete):
    with cerrojo:
        estado["invasiones"] = paquete.get("invasiones", estado["invasiones"])
        for invasion, resumen in paquete.get("resumenes", {}).items():
            estado["resumenes"][invasion] = resumen
        # las invasiones que el PC ya no tiene (borradas al empezar una nueva) se borran aquí también
        vigentes = {i["id"] for i in estado["invasiones"]}
        estado["resumenes"] = {k: v for k, v in estado["resumenes"].items() if k in vigentes}
        if estado["invasiones"]:
            estado["ultima"] = estado["invasiones"][0]["id"]
        estado["recibido"] = time.time()
        return {"conocidas": list(estado["resumenes"])}


class Manejador(BaseHTTPRequestHandler):
    def responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/datos":
            invasion = parse_qs(url.query).get("invasion", [None])[0]
            self.responder(200, json.dumps(datos_para(invasion), ensure_ascii=False).encode("utf-8"))
        elif url.path in ("/", "/index.html"):
            with open(RUTA_WEB, "rb") as f:
                self.responder(200, f.read(), "text/html; charset=utf-8")
        elif url.path == "/health":
            self.responder(200, b'{"ok": true}')
        else:
            self.responder(404, b'{"error": "no existe"}')

    def do_POST(self):
        if urlparse(self.path).path != "/api/subir":
            self.responder(404, b'{"error": "no existe"}')
            return
        clave = self.headers.get("X-Clave", "")
        if not hmac.compare_digest(hashlib.sha256(clave.encode()).hexdigest(), HUELLA_CLAVE):
            self.responder(403, b'{"error": "clave incorrecta"}')
            return
        largo = int(self.headers.get("Content-Length") or 0)
        if largo <= 0 or largo > MAXIMO_SUBIDA:
            self.responder(413, b'{"error": "demasiado grande"}')
            return
        try:
            paquete = json.loads(self.rfile.read(largo))
        except ValueError:
            self.responder(400, b'{"error": "json malo"}')
            return
        self.responder(200, json.dumps(guardar(paquete)).encode("utf-8"))

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 10000))
    print(f"Escuchando en el puerto {puerto}")
    ThreadingHTTPServer(("0.0.0.0", puerto), Manejador).serve_forever()
