"""API local con datos sintéticos y errores reproducibles."""
import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit

from api_auditoria import leer_operaciones


class Handler(BaseHTTPRequestHandler):
    def responder(self, codigo, datos, extras=None):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        for clave, valor in (extras or {}).items():
            self.send_header(clave, valor)
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/operaciones":
            parametros = parse_qs(url.query)
            try:
                pagina = int(parametros.get("page", ["1"])[0])
                limite = int(parametros.get("limit", ["2"])[0])
                if pagina < 1 or not 1 <= limite <= 10:
                    raise ValueError
            except ValueError:
                self.responder(400, {"error": "Paginación inválida"})
                return
            filas = leer_operaciones()
            inicio = (pagina - 1) * limite
            fin = inicio + limite
            self.responder(200, {"items": filas[inicio:fin],
                                "next_page": pagina + 1 if fin < len(filas) else None})
        elif url.path == "/privado":
            if self.headers.get("Authorization") != "Bearer token-aula":
                self.responder(401, {"error": "Token requerido"},
                               {"WWW-Authenticate": "Bearer"})
            else:
                self.responder(200, {"acceso": "autorizado"})
        elif url.path == "/limite":
            self.server.peticion_limite += 1
            if self.server.peticion_limite == 1:
                self.responder(429, {"error": "Límite simulado"}, {"Retry-After": "2"})
            else:
                self.responder(200, {"estado": "recuperado"})
        else:
            self.responder(404, {"error": "Ruta inexistente"})

    def log_message(self, format, *args):
        # Los ejemplos muestran sus propios resultados.
        pass


@contextmanager
def api_local():
    with HTTPServer(("127.0.0.1", 0), Handler) as servidor:
        servidor.peticion_limite = 0
        hilo = Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            yield f"http://127.0.0.1:{servidor.server_port}"
        finally:
            servidor.shutdown()
            hilo.join()
