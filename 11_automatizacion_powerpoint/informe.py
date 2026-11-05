"""Genera un informe HTML local a partir del índice PDF del bloque 09."""
import argparse
import json
import re
from collections import Counter
from html import escape
from pathlib import Path
from string import Template

ESTADOS_ARCHIVO = {"inspeccionado", "cifrado", "error_lectura"}


def validar(documentos):
    if not isinstance(documentos, list):
        raise ValueError("El índice debe ser una lista de documentos")
    archivos = set()
    for documento in documentos:
        if not isinstance(documento, dict):
            raise ValueError("Cada documento debe ser un objeto")
        nombre = documento.get("archivo")
        estado = documento.get("estado")
        paginas = documento.get("paginas")
        if not isinstance(nombre, str) or not nombre.strip() or nombre in archivos:
            raise ValueError(f"Nombre vacío, inválido o repetido: {nombre!r}")
        archivos.add(nombre)
        if not isinstance(estado, str) or estado not in ESTADOS_ARCHIVO:
            raise ValueError(f"{nombre}: estado de archivo inválido")
        if not isinstance(paginas, list) or (estado != "inspeccionado" and paginas):
            raise ValueError(f"{nombre}: páginas incompatibles con el estado")
        for numero, pagina in enumerate(paginas, 1):
            if (not isinstance(pagina, dict) or type(pagina.get("pagina")) is not int
                    or pagina["pagina"] != numero):
                raise ValueError(f"{nombre}: páginas fuera de orden")
            caracteres = pagina.get("caracteres")
            ids = pagina.get("ids")
            if type(caracteres) is not int or caracteres < 0:
                raise ValueError(f"{nombre}, página {numero}: caracteres inválidos")
            esperado = "texto_extraido" if caracteres else "sin_texto_extraido"
            if pagina.get("estado") != esperado:
                raise ValueError(f"{nombre}, página {numero}: estado incoherente")
            if (not isinstance(ids, list) or (ids and not caracteres)
                    or any(not isinstance(i, str) or not re.fullmatch(r"DOC-[0-9]{3}", i) for i in ids)
                    or len(set(ids)) != len(ids)):
                raise ValueError(f"{nombre}, página {numero}: referencias inválidas")
    return documentos


def cargar(ruta):
    return validar(json.loads(Path(ruta).read_text(encoding="utf-8")))


def resumir(documentos):
    archivos = Counter(d["estado"] for d in documentos)
    paginas = [p for d in documentos for p in d["paginas"]]
    estados = Counter(p["estado"] for p in paginas)
    referencias = {i for p in paginas for i in p["ids"]}
    total = len(paginas)
    con_texto = estados["texto_extraido"]
    return {
        "archivos": len(documentos),
        "inspeccionados": archivos["inspeccionado"],
        "cifrados": archivos["cifrado"],
        "errores": archivos["error_lectura"],
        "paginas": total,
        "con_texto": con_texto,
        "pendientes": estados["sin_texto_extraido"],
        "referencias_distintas": len(referencias),
        "cobertura": con_texto / total if total else None,
    }


def filas_html(documentos):
    filas = []
    for d in sorted(documentos, key=lambda item: item["archivo"]):
        registros = [(p["pagina"], p["estado"], ", ".join(p["ids"]) or "—")
                     for p in d["paginas"]]
        if not registros:
            registros = [("—", d["estado"], "—")]
        for numero, estado, ids in registros:
            valores = [d["archivo"], numero, estado.replace("_", " "), ids]
            celdas = "".join(f"<td>{escape(str(v))}</td>" for v in valores)
            filas.append(f"<tr>{celdas}</tr>")
    return "\n".join(filas) or '<tr><td colspan="4">Sin registros</td></tr>'


def renderizar(documentos, periodo):
    datos = resumir(documentos)
    cobertura = datos["cobertura"]
    porcentaje = f"{cobertura:.1%}".replace(".", ",") if cobertura is not None else "No aplica"
    plantilla = Template(Path(__file__).with_name("plantilla.html").read_text(encoding="utf-8"))
    return plantilla.substitute({**datos, "periodo": escape(periodo),
                                "porcentaje": porcentaje, "filas": filas_html(documentos)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("indice", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--periodo", required=True)
    args = parser.parse_args()
    resultado = renderizar(cargar(args.indice), args.periodo)
    with args.salida.open("x", encoding="utf-8") as archivo:
        archivo.write(resultado)


if __name__ == "__main__":
    main()
