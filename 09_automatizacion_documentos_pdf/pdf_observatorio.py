"""Inspecciona PDFs y exporta un índice por página en JSON."""
import argparse
import json
import re
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError


def inspeccionar(ruta):
    with Path(ruta).open("rb") as archivo:
        lector = PdfReader(archivo)
        if lector.is_encrypted:
            return {"archivo": Path(ruta).name, "estado": "cifrado", "paginas": []}
        paginas = []
        for numero, pagina in enumerate(lector.pages, 1):
            texto = (pagina.extract_text() or "").strip()
            ids = sorted(set(re.findall(r"\bDOC-[0-9]{3}\b", texto)))
            paginas.append({"pagina": numero, "caracteres": len(texto),
                            "estado": "texto_extraido" if texto else "sin_texto_extraido",
                            "ids": ids})
    return {"archivo": Path(ruta).name, "estado": "inspeccionado", "paginas": paginas}


def inventario(carpeta):
    resultados = []
    for ruta in sorted(Path(carpeta).glob("*.pdf")):
        try:
            resultados.append(inspeccionar(ruta))
        except (OSError, PdfReadError) as error:
            resultados.append({"archivo": ruta.name, "estado": "error_lectura",
                               "error": str(error), "paginas": []})
    return resultados


def seleccionar(entrada, salida, paginas):
    """Las páginas de la interfaz se numeran desde uno y conservan el orden pedido."""
    escritor = PdfWriter()
    with Path(entrada).open("rb") as archivo:
        lector = PdfReader(archivo)
        if lector.is_encrypted:
            raise ValueError("La selección requiere un documento accesible")
        if not paginas or any(not 1 <= n <= len(lector.pages) for n in paginas):
            raise ValueError("Selecciona páginas entre 1 y el total del PDF")
        for numero in paginas:
            escritor.add_page(lector.pages[numero - 1])
        with Path(salida).open("xb") as destino:
            escritor.write(destino)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("carpeta", type=Path)
    parser.add_argument("salida", type=Path)
    args = parser.parse_args()
    if not args.carpeta.is_dir():
        parser.error("La carpeta de entrada debe existir")
    resultados = inventario(args.carpeta)
    with args.salida.open("x", encoding="utf-8") as destino:
        json.dump(resultados, destino, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
