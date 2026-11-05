"""Genera una presentación editable a partir del índice del Observatorio."""
import argparse
from pathlib import Path
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches, Pt

from informe import cargar, resumir

AZUL = RGBColor.from_string("003B5C")
TURQUESA = RGBColor.from_string("007F83")


def nueva_presentacion():
    presentacion = Presentation()
    presentacion.slide_width = Inches(13.333)
    presentacion.slide_height = Inches(7.5)
    return presentacion


def texto(diapositiva, contenido, x, y, ancho, alto, tamano=20,
          color=AZUL, negrita=False):
    caja = diapositiva.shapes.add_textbox(
        Inches(x), Inches(y), Inches(ancho), Inches(alto)
    )
    caja.text_frame.word_wrap = True
    caja.text_frame.text = contenido
    for parrafo in caja.text_frame.paragraphs:
        for tramo in parrafo.runs:
            tramo.font.name = "Calibri"
            tramo.font.size = Pt(tamano)
            tramo.font.color.rgb = color
            tramo.font.bold = negrita
    return caja


def pagina(presentacion, titulo, etiqueta):
    diapositiva = presentacion.slides.add_slide(presentacion.slide_layouts[6])
    texto(diapositiva, etiqueta, 0.65, 0.4, 12, 0.4, 13, TURQUESA, True)
    texto(diapositiva, titulo, 0.65, 0.95, 12, 0.95, 33, AZUL, True)
    texto(diapositiva, f"Observatorio documental  ·  {len(presentacion.slides):02d}",
          0.65, 6.95, 12, 0.35, 11)
    return diapositiva


def grafico_estados(diapositiva, con_texto, pendientes):
    datos = CategoryChartData()
    datos.categories = ["Con texto", "Por revisar"]
    datos.add_series("Páginas", [con_texto, pendientes])
    grafico = diapositiva.shapes.add_chart(
        XL_CHART_TYPE.BAR_CLUSTERED,
        Inches(0.8), Inches(2.05), Inches(7.5), Inches(4.3), datos
    ).chart
    grafico.has_legend = False
    grafico.value_axis.minimum_scale = 0
    grafico.plots[0].has_data_labels = True
    relleno = grafico.series[0].format.fill
    relleno.solid()
    relleno.fore_color.rgb = TURQUESA
    return grafico


def cola_revision(documentos):
    return [(doc["archivo"], p["pagina"]) for doc in documentos
            for p in doc["paginas"] if p["estado"] == "sin_texto_extraido"]


def construir(documentos, periodo):
    kpi = resumir(documentos)
    prs = nueva_presentacion()
    portada = pagina(prs, "Informe de extracción PDF", "01  ·  RESUMEN")
    texto(portada, f"Periodo · {periodo}", 0.7, 2.0, 11.8, 0.7, 21)
    cobertura = kpi["cobertura"]
    valor = "No aplica" if cobertura is None else f"{cobertura:.1%}".replace(".", ",")
    for i, (numero, etiqueta) in enumerate([
        (kpi["archivos"], "Archivos"), (kpi["paginas"], "Páginas inspeccionadas"),
        (valor, "Cobertura de texto"), (kpi["pendientes"], "Páginas por revisar")
    ]):
        x = 0.7 + 3.1 * i
        texto(portada, str(numero), x, 3.2, 2.9, 0.9, 39, TURQUESA, True)
        texto(portada, etiqueta, x, 4.1, 2.9, 0.65, 16)
    texto(portada, f"Cifrados: {kpi['cifrados']}   ·   Errores: {kpi['errores']}",
          0.7, 5.65, 12, 0.5, 17)

    estados = pagina(prs, "Estado de las páginas inspeccionadas", "02  ·  COBERTURA")
    grafico_estados(estados, kpi["con_texto"], kpi["pendientes"])
    texto(estados, "La cobertura divide las páginas con texto entre las páginas inspeccionadas.",
          8.65, 2.65, 3.85, 1.65, 20)
    texto(estados, "Las páginas por revisar requieren diagnóstico visual u OCR.",
          8.65, 4.45, 3.85, 1.3, 18, TURQUESA)

    pendientes = cola_revision(documentos)
    for inicio in range(0, max(1, len(pendientes)), 8):
        parte = pendientes[inicio:inicio + 8]
        detalle = pagina(prs, "Cola de revisión documental", "03  ·  PROCEDENCIA")
        tabla = detalle.shapes.add_table(len(parte) + 1, 2, Inches(0.8), Inches(2.05),
                                         Inches(11.7), Inches(0.48 * (len(parte) + 1))).table
        tabla.columns[0].width = Inches(9.2)
        tabla.columns[1].width = Inches(2.5)
        for fila, valores in enumerate([("Archivo", "Página"), *parte]):
            for columna, valor in enumerate(valores):
                celda = tabla.cell(fila, columna)
                celda.text = str(valor)
                for parrafo in celda.text_frame.paragraphs:
                    parrafo.font.size = Pt(16)
        if not parte:
            texto(detalle, "Sin páginas pendientes en el lote.", 0.8, 3.0, 11, 0.6)
    return prs


def guardar(presentacion, salida):
    if salida.suffix.lower() != ".pptx":
        raise ValueError("La salida debe tener extensión .pptx")
    with salida.open("xb") as archivo:
        presentacion.save(archivo)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("indice", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--periodo", required=True)
    args = parser.parse_args()
    guardar(construir(cargar(args.indice), args.periodo), args.salida)


if __name__ == "__main__":
    main()
