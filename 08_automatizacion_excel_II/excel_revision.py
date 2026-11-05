"""Construye un libro de revisión a partir de la entrada del bloque 07."""
import argparse
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import FormulaRule
from openpyxl.formula.translate import Translator
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

CAMPOS = ("entrada_id", "ruta", "fecha", "bytes", "estado", "motivo")
ESTADOS = ("creado", "duplicado_lote", "revision", "conflicto_lote",
           "conflicto_destino", "error_operativo", "existente")


def leer_entrada(ruta):
    libro = load_workbook(ruta, read_only=True)
    try:
        filas = libro["Entrada"].iter_rows(values_only=True)
        if next(filas, None) != CAMPOS:
            raise ValueError("Cabecera incompatible con el bloque 07")
        datos = [fila for fila in filas if any(v is not None for v in fila)]
        if not datos:
            raise ValueError("La entrada debe contener registros")
        vistos = set()
        for identificador, ruta, fecha, tamano, estado, motivo in datos:
            if (not isinstance(identificador, str) or identificador in vistos
                    or type(tamano) is not int or tamano < 0 or estado not in ESTADOS):
                raise ValueError(f"Registro inválido o repetido: {identificador!r}")
            vistos.add(identificador)
        return datos
    finally:
        libro.close()


def crear_tabla(hoja, ultima):
    tabla = Table(displayName="Documentos", ref=f"A1:H{ultima}")
    tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    hoja.add_table(tabla)
    return tabla


def configurar_revision(hoja, ultima):
    rango = f"G2:G{ultima}"
    lista = DataValidation(type="list", formula1='"Pendiente,Revisado"',
                           allow_blank=False, showErrorMessage=True,
                           errorStyle="stop", errorTitle="Valor no admitido",
                           error="Selecciona Pendiente o Revisado.")
    hoja.add_data_validation(lista)
    lista.add(rango)
    regla = FormulaRule(formula=['$G2="Pendiente"'],
                       fill=PatternFill("solid", fgColor="FFFFE2AA"))
    hoja.conditional_formatting.add(f"A2:H{ultima}", regla)


def crear_resumen(libro, ultima):
    hoja = libro.create_sheet("Resumen", 0)
    hoja.append(("Estado original", "Entradas"))
    for fila, estado in enumerate(ESTADOS, start=2):
        hoja.append((estado, f'=COUNTIF(Revision!$E$2:$E${ultima},A{fila})'))
    hoja["A10"] = "Total de entradas"
    hoja["B10"] = "=SUM(B2:B8)"
    hoja["A11"] = "Pendientes de revisión"
    hoja["B11"] = f'=COUNTIF(Revision!$G$2:$G${ultima},"Pendiente")'
    grafico = BarChart()
    grafico.title = "Entradas por estado original"
    grafico.y_axis.title = "Entradas"
    grafico.add_data(Reference(hoja, min_col=2, min_row=1, max_row=8), titles_from_data=True)
    grafico.set_categories(Reference(hoja, min_col=1, min_row=2, max_row=8))
    grafico.legend = None
    hoja.add_chart(grafico, "D2")
    hoja.column_dimensions["A"].width = 31
    hoja.column_dimensions["B"].width = 14


def construir(datos):
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Revision"
    hoja.append((*CAMPOS, "revision_manual", "requiere_atencion"))
    for fila in datos:
        necesita = fila[4] in {"revision", "conflicto_lote", "conflicto_destino", "error_operativo"}
        hoja.append((*fila, "Pendiente" if necesita else "Revisado"))
        for celda in hoja[hoja.max_row][:7]:
            if isinstance(celda.value, str):
                celda.data_type = "s"
    ultima = hoja.max_row
    base = '=IF(G2="Pendiente",1,0)'
    for fila in range(2, ultima + 1):
        hoja[f"H{fila}"] = Translator(base, origin="H2").translate_formula(f"H{fila}")
    crear_tabla(hoja, ultima)
    configurar_revision(hoja, ultima)
    crear_resumen(libro, ultima)
    for col, ancho in zip("ABCDEFGH", (14, 50, 14, 10, 24, 32, 22, 22)):
        hoja.column_dimensions[col].width = ancho
    hoja.freeze_panes = "C2"
    for celda in libro["Resumen"][1]:
        celda.font = Font(bold=True, color="FF003B5C")
    libro.active = 0
    return libro


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entrada", type=Path)
    parser.add_argument("salida", type=Path)
    args = parser.parse_args()
    if args.salida.suffix.lower() != ".xlsx":
        parser.error("La salida debe terminar en .xlsx")
    libro = construir(leer_entrada(args.entrada))
    try:
        with args.salida.open("xb") as destino:
            libro.save(destino)
    finally:
        libro.close()


if __name__ == "__main__":
    main()
