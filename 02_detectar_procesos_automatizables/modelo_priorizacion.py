"""Modelo docente: criterios ilustrativos, no una norma ni autorización de ejecución."""
from math import isfinite, isclose
from statistics import mean, median
from copy import deepcopy
from collections import Counter
from pprint import pprint

FACTORES = ("volumen", "estabilidad", "estructura", "calidad", "impacto", "facilidad")
PESOS = {"volumen": .20, "estabilidad": .20, "estructura": .15,
         "calidad": .15, "impacto": .20, "facilidad": .10}
VERSION_MODELO = "priorizacion-aula-1.0"


def es_numero(valor):
    return type(valor) in (int, float) and isfinite(valor)


def validar_pesos(pesos):
    if not isinstance(pesos, dict) or set(pesos) != set(FACTORES):
        raise ValueError("Los pesos deben contener exactamente los seis factores")
    if any(not es_numero(x) or x < 0 for x in pesos.values()):
        raise ValueError("Los pesos deben ser finitos y no negativos")
    if not isclose(sum(pesos.values()), 1.0, abs_tol=1e-9):
        raise ValueError("Los pesos deben sumar uno")


def validar_ficha(f):
    if not isinstance(f, dict):
        raise ValueError("La ficha debe ser un diccionario")
    requeridos = {"id", "nombre", "unidad", "volumen_anual", "min_manual", "min_operacion",
                  "min_revision", "p_excepcion", "min_excepcion", "horas_impl",
                  "horas_mant", "factores", "riesgo", "autorizacion", "responsable"}
    if not requeridos.issubset(f):
        raise ValueError("Faltan campos obligatorios en la ficha")
    if any(not isinstance(f[k], str) or not f[k].strip() for k in ("id", "nombre", "unidad")):
        raise ValueError("ID, nombre y unidad deben ser textos no vacíos")
    if type(f["volumen_anual"]) is not int or f["volumen_anual"] < 0:
        raise ValueError("El volumen anual debe ser un entero no negativo")
    tiempos = ("min_manual", "min_operacion", "min_revision", "min_excepcion",
               "horas_impl", "horas_mant")
    if any(not es_numero(f[k]) or f[k] < 0 for k in tiempos):
        raise ValueError("Los tiempos deben ser finitos y no negativos")
    if not es_numero(f["p_excepcion"]) or not 0 <= f["p_excepcion"] <= 1:
        raise ValueError("La proporción de excepciones debe estar entre cero y uno")
    if not isinstance(f["factores"], dict) or set(f["factores"]) != set(FACTORES):
        raise ValueError("La ficha debe declarar los seis factores")
    for valor in list(f["factores"].values()) + [f["riesgo"]]:
        if valor is not None and (type(valor) is not int or not 1 <= valor <= 5):
            raise ValueError("Las valoraciones deben ser enteros 1–5 o None")
    if f["autorizacion"] is not None and type(f["autorizacion"]) is not bool:
        raise ValueError("Autorización debe ser True, False o None")
    if f["responsable"] is not None and (
        not isinstance(f["responsable"], str) or not f["responsable"].strip()
    ):
        raise ValueError("Responsable debe ser texto no vacío o None")


def calcular_metricas(f):
    validar_ficha(f)
    minutos_futuros = f["min_operacion"] + f["min_revision"] + f["p_excepcion"] * f["min_excepcion"]
    manual = f["volumen_anual"] * f["min_manual"] / 60
    futuro = f["volumen_anual"] * minutos_futuros / 60
    ahorro_bruto = manual - futuro
    ahorro_recurrente = ahorro_bruto - f["horas_mant"]
    primer_anio = ahorro_recurrente - f["horas_impl"]
    retorno_meses = (12 * f["horas_impl"] / ahorro_recurrente
                     if ahorro_recurrente > 0 else None)
    return {"min_futuros": minutos_futuros, "horas_manual": manual,
            "horas_futuras": futuro, "horas_liberadas_brutas": ahorro_bruto,
            "horas_netas_recurrentes": ahorro_recurrente,
            "horas_netas_primer_anio": primer_anio,
            "retorno_meses": retorno_meses}


def puntuar(factores, pesos):
    validar_pesos(pesos)
    if not isinstance(factores, dict) or set(factores) != set(FACTORES):
        raise ValueError("Se requieren exactamente los seis factores")
    for valor in factores.values():
        if valor is not None and (type(valor) is not int or not 1 <= valor <= 5):
            raise ValueError("Los factores son enteros 1–5 o None")
    if any(v is None for v in factores.values()):
        return None  # Desconocido no equivale a cero.
    return 100 * sum(pesos[k] * (factores[k] - 1) / 4 for k in FACTORES)


def evaluar(f, pesos=None):
    if pesos is None:
        pesos = PESOS
    metricas = calcular_metricas(f)
    score = puntuar(f["factores"], pesos)
    if f["autorizacion"] is False:
        estado, motivo = "bloqueado", "Falta autorización: no se ejecuta el proceso"
    elif any(f[k] is None for k in ("autorizacion", "responsable", "riesgo")) or score is None:
        estado, motivo = "pendiente", "Faltan evidencias o una persona responsable"
    elif f["riesgo"] >= 4:
        estado, motivo = "redisenar", "Riesgo alto: revisar alcance y controles"
    elif score >= 70 and metricas["horas_netas_primer_anio"] > 0:
        estado, motivo = "candidato_piloto", "Supera los criterios docentes; requiere validar un piloto"
    else:
        estado, motivo = "analizar", "Revisar valor, alcance o supuestos antes de priorizar"
    return {"id": f["id"], "nombre": f["nombre"], "puntuacion": score,
            "estado": estado, "motivo": motivo, "metricas": metricas,
            "version_modelo": VERSION_MODELO}


def evaluar_cartera(fichas, pesos=None):
    if not isinstance(fichas, list):
        raise ValueError("La cartera debe ser una lista")
    ids = set()
    for f in fichas:
        validar_ficha(f)
        if f["id"] in ids:
            raise ValueError("ID repetido en la cartera")
        ids.add(f["id"])
    if pesos is None:
        pesos = PESOS
    validar_pesos(pesos)
    return [evaluar(f, pesos) for f in fichas]


def ordenar_candidatos(resultados):
    candidatos = [r for r in resultados if r["estado"] == "candidato_piloto"]
    # Un empate usa ID para estabilidad técnica, no como preferencia de negocio.
    return sorted(candidatos, key=lambda r: (-r["puntuacion"], r["id"]))


def simular_excepciones(f, proporciones):
    filas = []
    for proporcion in proporciones:
        escenario = deepcopy(f)
        escenario["p_excepcion"] = proporcion
        filas.append({"p_excepcion": proporcion,
                      **calcular_metricas(escenario)})
    return filas
