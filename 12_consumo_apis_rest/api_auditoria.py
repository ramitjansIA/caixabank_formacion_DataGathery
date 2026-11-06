"""Cliente REST y contraste de divisas para el laboratorio del Observatorio."""
import argparse
import csv
import hashlib
import io
import json
import time
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

BCE = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
DATOS = Path(__file__).resolve().parent / "datos"
CENTIMO = Decimal("0.01")
REINTENTABLES = {429, 502, 503, 504}


class SinRedirecciones(HTTPRedirectHandler):
    """Una nueva URL requiere una decisión explícita del cliente."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def url_bce(inicio, fin):
    if date.fromisoformat(inicio) > date.fromisoformat(fin):
        raise ValueError("La fecha de inicio debe preceder al fin")
    parametros = {"startPeriod": inicio, "endPeriod": fin, "format": "csvdata"}
    return BCE + "?" + urlencode(parametros)


def get(url, *, accept="application/json", token=None, timeout=8,
        intentos=3, esperar=time.sleep):
    """Devuelve cuerpo y metadatos. Limita reintentos a lecturas GET."""
    if intentos < 1 or timeout <= 0:
        raise ValueError("Configura al menos un intento y un timeout positivo")
    headers = {"Accept": accept, "User-Agent": "Observatorio-Aula/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    solicitud = Request(url, headers=headers, method="GET")
    cliente = build_opener(SinRedirecciones())
    for intento in range(1, intentos + 1):
        espera = min(2 ** (intento - 1), 8)
        try:
            with cliente.open(solicitud, timeout=timeout) as respuesta:
                cuerpo = respuesta.read(5_000_001)
                if len(cuerpo) > 5_000_000:
                    raise ValueError("Respuesta superior al límite de aula")
                return cuerpo, {
                    "url": respuesta.geturl(),
                    "estado_http": respuesta.status,
                    "content_type": respuesta.headers.get("Content-Type", ""),
                    "intentos": intento,
                    "recuperado_utc": datetime.now(timezone.utc).isoformat(),
                }
        except HTTPError as error:
            codigo = error.code
            retry_after = error.headers.get("Retry-After", "").strip()
            error.close()
            if codigo not in REINTENTABLES or intento == intentos:
                raise
            if retry_after:
                # El laboratorio admite segundos. Para fechas HTTP, escalar a revisión.
                if not retry_after.isascii() or not retry_after.isdecimal():
                    raise
                if len(retry_after) > 2 or int(retry_after) > 30:
                    raise
                espera = max(espera, int(retry_after))
        except (URLError, TimeoutError):
            if intento == intentos:
                raise
        esperar(espera)


def leer_json(cuerpo, metadatos):
    tipo = metadatos["content_type"].split(";", 1)[0].strip().lower()
    if tipo != "application/json" and not tipo.endswith("+json"):
        raise ValueError(f"Respuesta inesperada: {tipo}")
    return json.loads(cuerpo)


def paginar(base, *, max_paginas=10, limite=2):
    """Contrato del simulador: next_page es entero o null."""
    pagina, vistos, ids = 1, set(), set()
    registros = []
    while pagina is not None:
        if type(pagina) is not int or pagina <= 0 or pagina in vistos:
            raise ValueError("Cursor de página inválido o repetido")
        if len(vistos) >= max_paginas:
            raise ValueError("Se alcanzó el límite de páginas")
        vistos.add(pagina)
        cuerpo, meta = get(f"{base}/operaciones?{urlencode({'page': pagina, 'limit': limite})}")
        lote = leer_json(cuerpo, meta)
        if not isinstance(lote, dict) or not isinstance(lote.get("items"), list) or "next_page" not in lote:
            raise ValueError("Contrato de paginación inválido")
        for fila in lote["items"]:
            identificador = fila.get("id") if isinstance(fila, dict) else None
            if not isinstance(identificador, str) or not identificador or identificador in ids:
                raise ValueError("Identificador inválido o duplicado")
            ids.add(identificador)
            registros.append(fila)
        pagina = lote["next_page"]
    return registros


def leer_cotizaciones(cuerpo):
    """Valida el subconjunto de columnas SDMX utilizado en el ejercicio."""
    lector = csv.DictReader(io.StringIO(cuerpo.decode("utf-8-sig"), newline=""))
    dimensiones = dict(FREQ="D", CURRENCY="USD", CURRENCY_DENOM="EUR",
                       EXR_TYPE="SP00", EXR_SUFFIX="A")
    requeridas = set(dimensiones) | {"TIME_PERIOD", "OBS_VALUE"}
    if not requeridas.issubset(lector.fieldnames or []):
        raise ValueError("Columnas de cotización incompletas")
    tipos = {}
    for fila in lector:
        if any(fila[k] != valor for k, valor in dimensiones.items()):
            raise ValueError("Serie distinta de D.USD.EUR.SP00.A")
        dia = date.fromisoformat(fila["TIME_PERIOD"]).isoformat()
        valor = Decimal(fila["OBS_VALUE"])
        if not valor.is_finite() or valor <= 0 or dia in tipos:
            raise ValueError("Tipo inválido o fecha duplicada")
        tipos[dia] = valor
    return tipos


def conciliar(operaciones, cotizaciones, tolerancia=Decimal("0.01")):
    if not tolerancia.is_finite() or tolerancia < 0:
        raise ValueError("Tolerancia inválida")
    resultado = []
    for op in operaciones:
        dia = date.fromisoformat(op["fecha"]).isoformat()
        usd = Decimal(op["importe_usd"])
        registrado = Decimal(op["eur_registrado"])
        if not usd.is_finite() or not registrado.is_finite():
            raise ValueError(f"Importes no finitos en {op['id']}")
        tipo = cotizaciones.get(dia)
        esperado = diferencia = None
        if tipo is None:
            estado = "sin_referencia"
        else:
            esperado = (usd / tipo).quantize(CENTIMO, rounding=ROUND_HALF_UP)
            diferencia = registrado - esperado
            estado = "dentro_tolerancia" if abs(diferencia) <= tolerancia else "revisar"
        resultado.append({
            "id": op["id"], "fecha": dia, "estado": estado,
            "usd_por_eur": str(tipo) if tipo is not None else None,
            "eur_esperado": str(esperado) if esperado is not None else None,
            "diferencia_eur": str(diferencia) if diferencia is not None else None,
        })
    return resultado


def leer_operaciones():
    with (DATOS / "operaciones.csv").open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("salida", type=Path, help="Directorio nuevo de evidencias")
    parser.add_argument("--en-vivo", action="store_true", help="Consultar el BCE por HTTPS")
    args = parser.parse_args()
    if args.en_vivo:
        cuerpo, meta = get(url_bce("2024-01-02", "2024-01-06"), accept="text/csv")
        tipo = meta["content_type"].split(";", 1)[0].strip().lower()
        if tipo not in {"text/csv", "application/vnd.sdmx.data+csv"}:
            raise ValueError(f"Se esperaba un CSV, se recibió {tipo}")
        meta["origen"] = "BCE en vivo"
    else:
        cuerpo = (DATOS / "bce_simulado.csv").read_bytes()
        meta = {"origen": "Cotizaciones sintéticas de aula"}
    resultado = conciliar(leer_operaciones(), leer_cotizaciones(cuerpo))
    meta["sha256_csv"] = hashlib.sha256(cuerpo).hexdigest()
    meta["tolerancia_eur"] = "0.01"
    meta["criterio_fecha"] = "Fecha exacta de la operación"
    args.salida.mkdir(exist_ok=False)
    (args.salida / "respuesta.csv").write_bytes(cuerpo)
    with (args.salida / "control.json").open("w", encoding="utf-8") as archivo:
        json.dump({"fuente": meta, "resultados": resultado}, archivo,
                  ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
