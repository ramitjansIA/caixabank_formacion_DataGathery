"""Bloque 07: leer y crear Excel con openpyxl 3.1.5, Python 3.11+.
Solo datos de aula. Conserva los diez documentos y decisiones del bloque 06.
"""
from pathlib import Path
from datetime import date, datetime
from collections import Counter
import argparse
import json
import re
import sys
import uuid
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
import organizador as organizador

CABECERAS = ("entrada_id", "ruta", "fecha", "bytes", "estado", "motivo")
ESTADOS = ("creado", "existente", "duplicado_lote", "revision", "conflicto_lote",
           "conflicto_destino", "error_operativo")
NAVY, TEAL, CLARO = "003B5C", "00A3A3", "EEF6F8"


def escribir_celda(ws, fila, columna, valor):
    """El texto externo se guarda como texto, aunque empiece por =."""
    c = ws.cell(row=fila, column=columna, value=valor)
    if isinstance(valor, str):
        c.data_type = "s"
    return c


def filas_desde_informe(informe):
    filas = []
    for numero, fila in enumerate(informe["filas"], start=1):
        nombre = Path(fila["ruta"]).name
        try:
            fecha = date.fromisoformat(nombre[:10])
        except ValueError:
            fecha = None
        filas.append({"entrada_id": f"{numero:04d}", "ruta": fila["ruta"],
                      "fecha": fecha, "bytes": fila["bytes"],
                      "estado": fila["estado"], "motivo": fila["motivo"]})
    return filas


def crear_entrada(filas, ruta):
    wb = Workbook()
    ws = wb.active
    ws.title = "Entrada"
    ws.append(CABECERAS)
    for numero, fila in enumerate(filas, start=2):
        for columna, clave in enumerate(CABECERAS, start=1):
            c = escribir_celda(ws, numero, columna, fila[clave])
            if clave == "fecha":
                c.number_format = "dd/mm/yyyy"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:F{ws.max_row}"
    for letra, ancho in {"A":14,"B":62,"C":16,"D":12,"E":24,"F":40}.items():
        ws.column_dimensions[letra].width = ancho
    with Path(ruta).open("xb") as f:
        wb.save(f)
    wb.close()


def validar_fila(valores, numero):
    fila = dict(zip(CABECERAS, valores))
    identificador = fila["entrada_id"]
    if not isinstance(identificador, str) or not re.fullmatch(r"[0-9]{4}", identificador):
        raise ValueError(f"Fila {numero}: entrada_id debe ser texto de cuatro cifras")
    organizador.backup.ruta_relativa_segura(fila["ruta"])
    fecha = fila["fecha"]
    if isinstance(fecha, datetime):
        if fecha.time() != datetime.min.time():
            raise ValueError(f"Fila {numero}: fecha con hora inesperada")
        fecha = fecha.date()
    if fecha is not None and type(fecha) is not date:
        raise ValueError(f"Fila {numero}: fecha debe ser fecha real o celda vacía")
    if type(fila["bytes"]) is not int or fila["bytes"] < 0:
        raise ValueError(f"Fila {numero}: bytes debe ser entero no negativo")
    if fila["estado"] not in ESTADOS:
        raise ValueError(f"Fila {numero}: estado desconocido")
    if not isinstance(fila["motivo"], str) or not fila["motivo"]:
        raise ValueError(f"Fila {numero}: falta motivo")
    fila["fecha"] = fecha
    return fila


def leer_entradas(ruta):
    ruta = Path(ruta)
    if ruta.is_symlink() or not ruta.is_file() or ruta.stat().st_size > 5 * 1024**2:
        raise ValueError("Se requiere el XLSX regular de aula, de hasta 5 MiB")
    wb = load_workbook(ruta, data_only=False, read_only=True)
    try:
        if wb.sheetnames != ["Entrada"]:
            raise ValueError("Se esperaba solo la hoja Entrada")
        ws = wb["Entrada"]
        if ws.max_column != 6 or not 2 <= ws.max_row <= 201:
            raise ValueError("Se requieren seis columnas y entre 1 y 200 entradas")
        cabecera = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        if tuple(cabecera) != CABECERAS:
            raise ValueError("Cabeceras ausentes, duplicadas o desordenadas")
        filas, vistos = [], set()
        for numero, celdas in enumerate(ws.iter_rows(min_row=2), start=2):
            if all(c.value is None for c in celdas):
                continue
            if any(c.data_type in {"f", "e"} for c in celdas):
                raise ValueError(f"Fila {numero}: fórmula o error en datos de entrada")
            fila = validar_fila([c.value for c in celdas], numero)
            if fila["entrada_id"] in vistos:
                raise ValueError(f"Fila {numero}: entrada_id repetido")
            vistos.add(fila["entrada_id"])
            filas.append(fila)
        if not filas:
            raise ValueError("No hay entradas")
        return filas
    finally:
        wb.close()


def escribir_documentos(wb, filas):
    ws = wb.create_sheet("Documentos")
    ws.merge_cells("A1:F1")
    ws["A1"] = "Observatorio · seguimiento de documentos"
    ws["A1"].font = Font(size=18, bold=True, color=NAVY)
    ws.merge_cells("A2:F2")
    ws["A2"] = "Datos ficticios. Una fila por entrada física; no por salida única."
    for columna, titulo in enumerate(CABECERAS, start=1):
        escribir_celda(ws, 4, columna, titulo)
    for numero, fila in enumerate(filas, start=5):
        for columna, clave in enumerate(CABECERAS, start=1):
            escribir_celda(ws, numero, columna, fila[clave])
    return ws


def dar_formato(ws):
    for c in ws[4]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(vertical="center")
    ws.row_dimensions[4].height = 28
    for fila in ws.iter_rows(min_row=5, max_row=ws.max_row):
        for c in fila:
            c.alignment = Alignment(vertical="top", wrap_text=True)
            if c.row % 2:
                c.fill = PatternFill("solid", fgColor=CLARO)
        fila[0].number_format = "@"
        fila[2].number_format = "dd/mm/yyyy"
        fila[3].number_format = "#,##0"
        ws.row_dimensions[fila[0].row].height = 46
    for letra, ancho in {"A":14,"B":58,"C":16,"D":12,"E":24,"F":43}.items():
        ws.column_dimensions[letra].width = ancho
    ws.freeze_panes = "C5"
    ws.auto_filter.ref = f"A4:F{ws.max_row}"
    ws.sheet_view.showGridLines = False


def escribir_resumen(ws, filas):
    conteo = Counter(f["estado"] for f in filas)
    ws.title = "Resumen"
    ws.merge_cells("A1:C1")
    ws["A1"] = "Observatorio · control de entradas"
    ws["A1"].font = Font(size=18, bold=True, color=NAVY)
    ws.merge_cells("A2:C2")
    ws["A2"] = "Instantánea del informe; recuentos calculados en Python."
    ws.append([])
    for col, valor in enumerate(("Estado", "Entradas", "Lectura"), start=1):
        escribir_celda(ws, 4, col, valor)
    lecturas = ("Publicación completada", "Ya archivada e idéntica",
                "Repetición del mismo destino y bytes", "Requiere revisión de nombre",
                "Varias entradas distintas compiten", "Salida previa diferente",
                "Fallo durante publicación")
    for fila, (estado, lectura) in enumerate(zip(ESTADOS, lecturas), start=5):
        ws.cell(fila, 1, estado)
        ws.cell(fila, 2, conteo[estado])
        ws.cell(fila, 3, lectura)
    ws["A13"], ws["B13"] = "TOTAL ENTRADAS", len(filas)
    pendientes = sum(conteo[e] for e in ("revision", "conflicto_lote", "conflicto_destino"))
    ws["A14"], ws["B14"] = "REVISIÓN DOCUMENTAL", pendientes
    for c in ws[4]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=NAVY)
    for numero in (13, 14):
        for c in ws[numero]:
            c.font = Font(bold=True, color=NAVY)
            c.fill = PatternFill("solid", fgColor="DDF1F1")
    for fila in ws.iter_rows(min_row=5, max_row=14):
        fila[1].number_format = "#,##0"
    for letra, ancho in {"A":30,"B":16,"C":48}.items():
        ws.column_dimensions[letra].width = ancho
    ws.freeze_panes = "B5"
    ws.sheet_view.showGridLines = False


def crear_libro(filas):
    wb = Workbook()
    escribir_resumen(wb.active, filas)
    documentos = escribir_documentos(wb, filas)
    dar_formato(documentos)
    wb.active = 0
    return wb


def verificar_libro(ruta, filas):
    wb = load_workbook(ruta, data_only=False)
    try:
        if wb.sheetnames != ["Resumen", "Documentos"]:
            raise ValueError("Hojas inesperadas")
        ws = wb["Documentos"]
        if ws.max_row != len(filas) + 4 or ws.max_column != 6:
            raise ValueError("Dimensiones de salida incompatibles")
        if tuple(c.value for c in ws[4]) != CABECERAS:
            raise ValueError("Cabecera de salida distinta")
        for numero, esperada in enumerate(filas, start=5):
            actual = validar_fila([c.value for c in ws[numero]], numero)
            if actual != esperada or any(c.data_type == "f" for c in ws[numero]):
                raise ValueError("Datos exportados diferentes")
        conteo = Counter(f["estado"] for f in filas)
        for numero, estado in enumerate(ESTADOS, start=5):
            if wb["Resumen"].cell(numero, 2).value != conteo[estado]:
                raise ValueError("Resumen no reconciliado")
        if wb["Resumen"]["B13"].value != len(filas):
            raise ValueError("Total no reconciliado")
        if ws.freeze_panes != "C5" or ws.auto_filter.ref != f"A4:F{ws.max_row}":
            raise ValueError("Configuración de navegación diferente")
    finally:
        wb.close()


def guardar_nuevo(wb, destino, filas):
    destino = Path(destino)
    if destino.exists() or destino.is_symlink():
        raise FileExistsError("No se sobrescribe una entrega existente")
    parcial = destino.parent / (".parcial_" + uuid.uuid4().hex + ".xlsx")
    try:
        wb.save(parcial)
        verificar_libro(parcial, filas)
        if destino.exists() or destino.is_symlink():
            raise FileExistsError("El destino apareció durante la operación")
        parcial.rename(destino)
    finally:
        wb.close()
    return destino


def preparar_demo(destino):
    raiz = organizador.crear_demo(destino)
    informe = organizador.ejecutar(raiz, aplicar=True)
    (raiz / "entrada_excel").mkdir()
    (raiz / "salida_excel").mkdir()
    filas = filas_desde_informe(informe)
    crear_entrada(filas, raiz / "entrada_excel" / "seguimiento_entrada.xlsx")
    return raiz


def generar(proyecto, aplicar=False, nombre="control_documental.xlsx"):
    if type(aplicar) is not bool:
        raise ValueError("aplicar debe ser booleano")
    raiz = organizador.cargar_proyecto(proyecto)
    organizador.backup.nombre_simple(nombre)
    if Path(nombre).suffix != ".xlsx":
        raise ValueError("Se requiere extensión .xlsx")
    for carpeta in ("entrada_excel", "salida_excel"):
        p = raiz / carpeta
        if p.is_symlink() or not p.is_dir():
            raise ValueError("Falta una carpeta Excel real de la demo")
    entrada = raiz / "entrada_excel" / "seguimiento_entrada.xlsx"
    filas = leer_entradas(entrada)
    destino = raiz / "salida_excel" / nombre
    resultado = {"filas": len(filas), "conteo": dict(Counter(f["estado"] for f in filas)),
                 "aplicado": aplicar, "salida": str(destino)}
    if aplicar:
        guardar_nuevo(crear_libro(filas), destino, filas)
        resultado["verificado"] = True
    return resultado


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="accion", required=True)
    demo = sub.add_parser("preparar-demo")
    demo.add_argument("destino", type=Path)
    gen = sub.add_parser("generar")
    gen.add_argument("--proyecto", required=True, type=Path)
    gen.add_argument("--nombre", default="control_documental.xlsx")
    gen.add_argument("--aplicar", action="store_true")
    a = p.parse_args(argv)
    try:
        r = {"proyecto": str(preparar_demo(a.destino))} if a.accion == "preparar-demo" else generar(a.proyecto, a.aplicar, a.nombre)
        print(json.dumps(r, ensure_ascii=False))
        return 0
    except (ValueError, FileExistsError) as e:
        print(str(e), file=sys.stderr)
        return 20
    except Exception as e:
        print(f"Fallo operativo: {type(e).__name__}: {e}", file=sys.stderr)
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
