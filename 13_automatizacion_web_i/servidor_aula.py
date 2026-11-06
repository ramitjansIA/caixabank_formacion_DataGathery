"""Portal de aula en loopback. Ejecuta este archivo para inspeccionarlo en un navegador."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit
import json

PLANTILLA = Path(__file__).with_name("laboratorio").joinpath("avisos.html")
AVISOS = [
    {"id": "AV-101", "fecha": "2026-10-12", "titulo": "Actualización de criterios de control"},
    {"id": "AV-102", "fecha": "2026-10-15", "titulo": "Calendario de revisión documental"},
]
CABECERA = "<thead><tr><th>ID</th><th>Fecha</th><th>Título</th></tr></thead>"
ESTATICO = "<table>" + CABECERA + "<tbody>" + "".join(
    f"<tr><td>{a['id']}</td><td>{a['fecha']}</td><td>{a['titulo']}</td></tr>" for a in AVISOS
) + "</tbody></table>"
DINAMICO = """<button id="cargar">Cargar avisos</button>
<p id="estado" role="status">Esperando interacción</p>
<table>""" + CABECERA + """<tbody id="filas"></tbody></table>
<script>
document.querySelector('#cargar').addEventListener('click', async event => {
  event.currentTarget.disabled = true;
  const estado = document.querySelector('#estado');
  estado.textContent = 'Cargando…';
  try {
    const respuesta = await fetch('/datos.json');
    if (!respuesta.ok) throw new Error('HTTP ' + respuesta.status);
    const datos = await respuesta.json();
    const cuerpo = document.querySelector('#filas');
    for (const aviso of datos.items) {
      const fila = cuerpo.insertRow();
      for (const campo of ['id', 'fecha', 'titulo']) {
        fila.insertCell().textContent = aviso[campo];
      }
    }
    estado.textContent = 'Carga completa';
  } catch (error) {
    estado.textContent = 'Error de carga';
  }
});
</script>"""

class Portal(BaseHTTPRequestHandler):
    def do_GET(self):
        ruta = urlsplit(self.path).path
        contenido = {
            "/": ESTATICO,
            "/estatico": ESTATICO,
            "/dinamico": DINAMICO,
            "/vacio": '<p data-estado="vacio">No hay avisos para este filtro.</p>',
            "/mantenimiento": '<p data-estado="incidencia">Portal en mantenimiento.</p>',
        }
        if ruta in contenido:
            cuerpo = PLANTILLA.read_text(encoding="utf-8").replace("<!--CONTENIDO-->", contenido[ruta])
            self.enviar(200, "text/html", cuerpo)
        elif ruta == "/datos.json":
            self.enviar(200, "application/json", json.dumps({"items": AVISOS}, ensure_ascii=False))
        elif ruta == "/robots.txt":
            self.enviar(200, "text/plain", "User-agent: *\nDisallow: /interno/\n")
        elif ruta.startswith("/interno/"):
            self.enviar(403, "text/plain", "Acceso denegado")
        else:
            self.enviar(404, "text/plain", "Ruta inexistente")

    def enviar(self, codigo, tipo, texto):
        cuerpo = texto.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, format, *args):
        pass


@contextmanager
def portal():
    with HTTPServer(("127.0.0.1", 0), Portal) as servidor:
        hilo = Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            yield f"http://127.0.0.1:{servidor.server_port}"
        finally:
            servidor.shutdown()
            hilo.join()


if __name__ == "__main__":
    with HTTPServer(("127.0.0.1", 8765), Portal) as servidor:
        print("Abre http://127.0.0.1:8765/estatico · Ctrl+C para salir", flush=True)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            pass
