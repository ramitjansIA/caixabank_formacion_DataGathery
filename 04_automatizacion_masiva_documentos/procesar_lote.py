"""Lote docente de documentos sintéticos, Python 3.11+ y biblioteca estándar.

No instala tareas. Cada configuración apunta a su propio proyecto privado.
Códigos: 0 correcto; 10 incidencias; 20 configuración; 30 fallo operativo;
40 bloqueo ocupado. argparse utiliza 2 para argumentos incompatibles.
"""
from pathlib import Path, PureWindowsPath
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from string import Template
from tempfile import TemporaryDirectory
from collections import Counter
import argparse
import json
import logging
import os
import re
import sys
import uuid
import time

VERSION = "lotes-aula-1.0"
MAX_BYTES = 1024 * 1024
LOG = logging.getLogger("lote")


class ConfigError(ValueError):
    pass


class BloqueoOcupado(RuntimeError):
    pass


def json_estricto(texto):
    def pares_sin_duplicar(pares):
        resultado = {}
        for clave, valor in pares:
            if clave in resultado:
                raise ValueError("Clave JSON repetida")
            resultado[clave] = valor
        return resultado
    def constante_invalida(valor):
        raise ValueError("Constante JSON no admitida: " + valor)
    return json.loads(texto, object_pairs_hook=pares_sin_duplicar,
                      parse_constant=constante_invalida)


def leer_acotado(ruta):
    with Path(ruta).open("rb") as archivo:
        contenido = archivo.read(MAX_BYTES + 1)
    if len(contenido) > MAX_BYTES:
        raise ValueError("Archivo superior al límite de aula de 1 MiB")
    return contenido.decode("utf-8")


def ruta_interna(raiz, relativa):
    if not isinstance(relativa, str) or not relativa:
        raise ConfigError("Cada ruta configurada debe ser texto relativo")
    p = Path(relativa)
    if p.is_absolute() or PureWindowsPath(relativa).anchor or ".." in p.parts:
        raise ConfigError("No se admiten rutas absolutas ni ascensos")
    actual = raiz
    for parte in p.parts:
        actual = actual / parte
        if actual.is_symlink():
            raise ConfigError("No se admiten enlaces en rutas configuradas")
    resuelta = actual.resolve()
    if not resuelta.is_relative_to(raiz) or resuelta == raiz:
        raise ConfigError("La ruta debe quedar dentro del proyecto")
    return resuelta


def cargar_config(ruta_config):
    original = Path(ruta_config).absolute()
    if original.is_symlink():
        raise ConfigError("La configuración no puede ser un enlace")
    try:
        ruta = original.resolve(strict=True)
    except (FileNotFoundError, NotADirectoryError) as error:
        raise ConfigError("No existe la configuración indicada") from error
    try:
        datos = json_estricto(leer_acotado(ruta))
    except (ValueError, UnicodeError) as error:
        raise ConfigError("Configuración JSON incompatible") from error
    claves = {"version", "entrada", "salida", "informes", "estado", "plantilla"}
    if not isinstance(datos, dict) or set(datos) != claves or type(datos["version"]) is not int or datos["version"] != 1:
        raise ConfigError("Se requiere esquema de configuración versión 1")
    raiz = ruta.parent
    cfg = {k: ruta_interna(raiz, datos[k]) for k in claves - {"version"}}
    for k in ("entrada", "salida", "informes", "estado"):
        if not cfg[k].is_dir():
            raise ConfigError("Falta la carpeta configurada: " + k)
    carpetas = [cfg[k] for k in ("entrada", "salida", "informes", "estado")]
    for i, a in enumerate(carpetas):
        for b in carpetas[i + 1:]:
            if a.is_relative_to(b) or b.is_relative_to(a):
                raise ConfigError("Las carpetas de trabajo no deben solaparse")
    if not cfg["plantilla"].is_file():
        raise ConfigError("Falta el archivo de plantilla")
    cfg.update(raiz=raiz, config=ruta)
    return cfg


def cargar_plantilla(ruta):
    try:
        plantilla = Template(leer_acotado(ruta))
    except (ValueError, UnicodeError) as error:
        raise ConfigError("No se puede interpretar la plantilla") from error
    permitidos = {"id", "anio", "importe", "territorio", "version"}
    if not plantilla.is_valid() or set(plantilla.get_identifiers()) != permitidos:
        raise ConfigError("La plantilla debe usar exactamente los cinco campos acordados")
    return plantilla


def validar_documento(datos):
    requeridos = {"id", "anio", "importe", "territorio"}
    if not isinstance(datos, dict) or set(datos) != requeridos:
        raise ValueError("Campos incompatibles con el contrato del documento")
    if not isinstance(datos["id"], str) or re.fullmatch(r"DEMO-[0-9]{3}", datos["id"]) is None:
        raise ValueError("ID sintético no admitido")
    if type(datos["anio"]) is not int or datos["anio"] not in {2024, 2025}:
        raise ValueError("Año fuera del contrato de aula")
    importe = datos["importe"]
    if not isinstance(importe, str) or re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,2})?", importe) is None:
        raise ValueError("Formato de importe incompatible")
    importe = Decimal(importe)
    if not importe.is_finite() or importe <= 0:
        raise ValueError("Importe no positivo o no finito")
    territorio = datos["territorio"]
    if not isinstance(territorio, str) or not territorio.strip() or len(territorio) > 80 or any(ord(c) < 32 for c in territorio):
        raise ValueError("Territorio ficticio incompatible")
    return {**datos, "importe": format(importe.quantize(Decimal("0.01")), "f"),
            "territorio": territorio.strip(), "version": VERSION}


@contextmanager
def bloqueo_local(carpeta):
    """Archivo exclusivo, solo para procesos cooperantes de un proyecto local.

    No se recuperan bloqueos huérfanos automáticamente. No es un bloqueo
    distribuido ni una defensa ante modificaciones hostiles del directorio.
    """
    ruta = Path(carpeta) / "ejecucion.lock"
    token = uuid.uuid4().hex
    try:
        fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise BloqueoOcupado("Ya existe un bloqueo; revisar la otra ejecución") from error
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"token": token, "pid": os.getpid(),
                       "inicio_utc": datetime.now(timezone.utc).isoformat()}, f)
        yield
    finally:
        # No se elimina un bloqueo que ya no tenga nuestra identidad.
        if ruta.exists() and not ruta.is_symlink():
            try:
                propio = json_estricto(ruta.read_text(encoding="utf-8"))
                if propio.get("token") == token:
                    ruta.unlink()
            except (OSError, ValueError, AttributeError):
                LOG.error("No se pudo retirar el bloqueo; revisar manualmente")


def seleccionar(cfg):
    # Solo hijos JSON regulares. No se procesa recursivamente la salida.
    return sorted((p for p in cfg["entrada"].iterdir()
                   if not p.is_symlink() and p.is_file() and p.suffix.lower() == ".json"),
                  key=lambda p: p.name)


def evaluar_elemento(ruta, cfg, plantilla, vistos, simular):
    registro = {"entrada": ruta.name, "salida": None}
    try:
        datos = validar_documento(json_estricto(leer_acotado(ruta)))
    except (ValueError, UnicodeError) as error:
        return {**registro, "estado": "invalido", "motivo": str(error)}
    # Un fallo operativo de lectura/escritura se propaga al nivel de ejecución.
    nombre = "doc_" + datos["id"] + "_" + str(datos["anio"]) + ".md"
    registro["salida"] = nombre
    if nombre in vistos:
        return {**registro, "estado": "duplicado", "motivo": "Clave repetida en el lote"}
    vistos.add(nombre)
    destino = cfg["salida"] / nombre
    if destino.is_symlink():
        raise OSError("La salida no puede ser un enlace")
    contenido = plantilla.substitute(datos).encode("utf-8")
    if destino.exists():
        if not destino.is_file():
            raise OSError("Un destino de documento no es un archivo")
        if destino.stat().st_size == len(contenido) and destino.read_bytes() == contenido:
            return {**registro, "estado": "omitido", "motivo": "Mismo contenido de salida"}
        return {**registro, "estado": "conflicto", "motivo": "El destino tiene contenido distinto"}
    if simular:
        return {**registro, "estado": "previsto", "motivo": "Se crearía un documento nuevo"}
    try:
        with destino.open("xb") as f:
            f.write(contenido)
    except FileExistsError:
        return {**registro, "estado": "conflicto", "motivo": "El destino apareció durante la operación"}
    return {**registro, "estado": "creado", "motivo": "Creación exclusiva terminada"}


def ejecutar_lote(ruta_config, simular=True):
    """No destruye entradas. Simulación sin salidas, informes ni bloqueo."""
    if type(simular) is not bool:
        raise TypeError("simular debe ser booleano")
    inicio = datetime.now(timezone.utc).isoformat()
    reloj = time.perf_counter()
    cfg = cargar_config(ruta_config)
    plantilla = cargar_plantilla(cfg["plantilla"])
    def recorrer():
        vistos = set()
        seleccion = seleccionar(cfg)
        elementos = [evaluar_elemento(p, cfg, plantilla, vistos, simular) for p in seleccion]
        conteo = dict(Counter(f["estado"] for f in elementos))
        codigo = 10 if any(conteo.get(k, 0) for k in ("invalido", "duplicado", "conflicto")) else 0
        return {"version": VERSION, "simulacion": simular,
                "inicio_utc": inicio,
                "fin_utc": datetime.now(timezone.utc).isoformat(),
                "duracion_s": time.perf_counter() - reloj,
                "seleccionados": len(seleccion), "conteo": conteo,
                "elementos": elementos, "codigo": codigo, "informe": None}
    LOG.info("Inicio version=%s python=%s cwd=%s pid=%s", VERSION, sys.executable, Path.cwd(), os.getpid())
    if simular:
        return recorrer()
    with bloqueo_local(cfg["estado"]):
        resultado = recorrer()
        nombre = "ejecucion_" + uuid.uuid4().hex + ".json"
        ruta_informe = cfg["informes"] / nombre
        resultado["informe"] = str(ruta_informe)
        with ruta_informe.open("x", encoding="utf-8", newline="\n") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        resultado["informe"] = str(ruta_informe)
        return resultado


def crear_demo(destino):
    raiz = Path(destino).absolute()
    raiz.mkdir(parents=True, exist_ok=False)
    for nombre in ("entrada", "salida", "informes", "estado", "plantillas"):
        (raiz / nombre).mkdir()
    config = {"version": 1, "entrada": "entrada", "salida": "salida",
              "informes": "informes", "estado": "estado", "plantilla": "plantillas/documento.txt"}
    (raiz / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    plantilla = "# Informe de aula ${id}\n\nAño: ${anio}\nImporte: ${importe} EUR\nTerritorio ficticio: ${territorio}\nMotor: ${version}\n\nDatos sintéticos. Sin conclusiones tributarias reales.\n"
    (raiz / config["plantilla"]).write_text(plantilla, encoding="utf-8", newline="\n")
    for numero, identificador, importe in [(1, "DEMO-001", "1200000.00"),
                                           (2, "DEMO-002", "800000.00"),
                                           (5, "DEMO-005", "650000.00")]:
        dato = {"id": identificador, "anio": 2025, "importe": importe,
                "territorio": "Territorio DEMO"}
        (raiz / "entrada" / (f"{numero:02d}_valido.json")).write_text(
            json.dumps(dato, ensure_ascii=False), encoding="utf-8")
    (raiz / "entrada/03_json_invalido.json").write_text('{"id":', encoding="utf-8")
    (raiz / "entrada/04_campo_falta.json").write_text('{"id":"DEMO-004"}', encoding="utf-8")
    (raiz / "entrada/LEEME.txt").write_text("Este archivo no forma parte del lote JSON.\n", encoding="utf-8")
    return raiz / "config.json"


def main(argv=None):
    for canal in (sys.stdout, sys.stderr):
        if hasattr(canal, "reconfigure"):
            canal.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--config", type=Path)
    modo.add_argument("--crear-demo", type=Path)
    parser.add_argument("--simular", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.crear_demo is not None:
            if args.simular:
                raise ConfigError("--simular se utiliza con --config")
            print(json.dumps({"config": str(crear_demo(args.crear_demo))}, ensure_ascii=False))
            return 0
        resultado = ejecutar_lote(args.config, simular=args.simular)
        print(json.dumps(resultado, ensure_ascii=False))
        return resultado["codigo"]
    except BloqueoOcupado as error:
        LOG.error("Bloqueo ocupado: %s", error)
        return 40
    except ConfigError as error:
        LOG.error("Configuración o dependencia de ruta: %s", error)
        return 20
    except OSError:
        LOG.exception("Fallo operativo: revisar posible resultado parcial")
        return 30
    except Exception:
        LOG.exception("Fallo inesperado: no se presenta el lote como correcto")
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
