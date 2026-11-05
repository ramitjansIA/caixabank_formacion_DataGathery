"""Renderizar en temporal y publicar solo el HTML, nunca una carpeta _files."""
from pathlib import Path
from tempfile import TemporaryDirectory
from html.parser import HTMLParser
import argparse
import re
import shutil
import subprocess

NOMBRE = "09_automatizacion_pdf"

class Recursos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.externos = []
        self.css = []
        self.en_estilo = False
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "style":
            self.en_estilo = True
        if "style" in d:
            self.css.append(d["style"])
        campos = {"script": "src", "img": "src", "source": "src",
                  "video": "src", "audio": "src", "iframe": "src", "link": "href"}
        campo = campos.get(tag)
        if campo and d.get(campo) and not d[campo].startswith(("data:", "#")):
            self.externos.append((tag, d[campo]))

    def handle_endtag(self, tag):
        if tag == "style":
            self.en_estilo = False
    def handle_data(self, data):
        if self.en_estilo:
            self.css.append(data)


def comprobar(html):
    p = Recursos()
    p.feed(html)
    if p.externos:
        raise ValueError("Dependencias externas: " + repr(p.externos))
    urls = re.findall(r'url\(\s*[\'\"]?([^\s)\'\"]+)', '\n'.join(p.css))
    externas = [u for u in urls if not u.startswith(("data:", "#"))]
    if externas:
        raise ValueError("CSS externo: " + repr(externas))
    if NOMBRE + "_files/" in html:
        raise ValueError("Referencia residual a _files")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--quarto", default=shutil.which("quarto"))
    a = p.parse_args()
    if not a.quarto:
        p.error("Instala Quarto o indica --quarto RUTA_AL_EJECUTABLE")
    raiz = Path(__file__).resolve().parent
    with TemporaryDirectory(prefix="quarto_pdf09_") as t:
        trabajo = Path(t)
        shutil.copy(raiz / (NOMBRE + ".qmd"), trabajo)
        shutil.copytree(raiz / "css", trabajo / "css")
        shutil.copytree(raiz / "recursos", trabajo / "recursos")
        subprocess.run([str(Path(a.quarto).resolve()), "render", NOMBRE + ".qmd"],
                       cwd=trabajo, check=True)
        resultado = trabajo / (NOMBRE + ".html")
        comprobar(resultado.read_text(encoding="utf-8"))
        shutil.copyfile(resultado, raiz / resultado.name)
    print("HTML autocontenido publicado:", raiz / (NOMBRE + ".html"))


if __name__ == "__main__":
    main()
