"""Motor docente de copias completas versionadas, Python 3.11+.

Solo opera sobre un proyecto sintético creado por crear-demo. No es una
solución 3-2-1, no cifra y no conserva ACL, enlaces ni carpetas vacías.
Códigos: 0 correcto, 10 integridad, 20 contrato, 30 operativo, 40 bloqueo.
"""
from pathlib import Path, PurePosixPath, PureWindowsPath
from contextlib import contextmanager
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import time
import uuid

VERSION = "copias-aula-1.0"
MAX_ARCHIVOS = 1000
MAX_ARCHIVO = 10 * 1024**2
MAX_TOTAL = 50 * 1024**2
BLOQUE = 64 * 1024
PATRON_COPIA = r"copia_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}"
LOG = logging.getLogger("copias")


class ContratoError(ValueError):
    pass


class IntegridadError(ValueError):
    pass


class BloqueoOcupado(RuntimeError):
    pass


def json_estricto(texto):
    def pares(p):
        d = {}
        for k, v in p:
            if k in d:
                raise ValueError("Clave JSON repetida")
            d[k] = v
        return d
    def no_constante(v):
        raise ValueError("Constante JSON no admitida: " + v)
    return json.loads(texto, object_pairs_hook=pares, parse_constant=no_constante)


def nombre_simple(nombre):
    if not isinstance(nombre, str) or not nombre or nombre in {".", ".."}:
        raise ContratoError("Nombre vacío o reservado")
    if nombre != nombre.strip() or nombre.endswith("."):
        raise ContratoError("Espacios extremos o punto final no admitidos")
    if any(c in '<>:"/\\|?*' or ord(c) < 32 for c in nombre):
        raise ContratoError("Nombre con separadores o caracteres no admitidos")
    reservados = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)}
    if nombre.split(".", 1)[0].upper() in reservados:
        raise ContratoError("Nombre reservado en Windows")
    return nombre


def ruta_relativa_segura(texto):
    if not isinstance(texto, str) or not texto or "\\" in texto:
        raise IntegridadError("Ruta relativa incompatible")
    p = PurePosixPath(texto)
    if not p.parts or p.is_absolute() or PureWindowsPath(texto).anchor or p.as_posix() != texto:
        raise IntegridadError("Ruta absoluta o no canónica")
    try:
        for parte in p.parts:
            nombre_simple(parte)
    except ContratoError as error:
        raise IntegridadError("Componente de ruta incompatible") from error
    return p


def cargar_proyecto(proyecto):
    original = Path(proyecto).absolute()
    if original.is_symlink():
        raise ContratoError("La raíz no puede ser un enlace")
    try:
        raiz = original.resolve(strict=True)
        marca = raiz / "proyecto_backup.json"
        if marca.is_symlink() or not marca.is_file() or marca.stat().st_size > 4096:
            raise ContratoError("No se reconoce el proyecto de aula")
        datos = json_estricto(marca.read_text(encoding="utf-8"))
    except (FileNotFoundError, NotADirectoryError, ValueError, UnicodeError) as error:
        raise ContratoError("Proyecto de aula ausente o incompatible") from error
    if not isinstance(datos, dict) or datos.get("tipo") != "demo_copias" or type(datos.get("schema")) is not int or datos["schema"] != 1:
        raise ContratoError("Marcador de proyecto incompatible")
    for nombre in ("origen", "copias", "restauraciones", "estado"):
        ruta = raiz / nombre
        if ruta.is_symlink() or not ruta.is_dir():
            raise ContratoError("Falta una carpeta real del proyecto: " + nombre)
    return raiz


def enumerar_archivos(carpeta):
    """Árbol privado y estable; rechaza enlaces y recursos no regulares."""
    carpeta = Path(carpeta)
    if carpeta.is_symlink() or not carpeta.is_dir():
        raise IntegridadError("Se requiere una carpeta real")
    archivos, pendientes = [], [carpeta]
    while pendientes:
        actual = pendientes.pop()
        for p in sorted(actual.iterdir(), key=lambda x: x.name):
            if p.is_symlink():
                raise IntegridadError("No se admiten enlaces")
            if p.is_dir():
                pendientes.append(p)
            elif p.is_file():
                archivos.append(p)
            else:
                raise IntegridadError("Recurso distinto de archivo regular")
            if len(archivos) > MAX_ARCHIVOS:
                raise IntegridadError("Demasiados archivos para el laboratorio")
    return sorted(archivos, key=lambda p: p.relative_to(carpeta).as_posix())


def hash_archivo(ruta):
    digest, cantidad = hashlib.sha256(), 0
    with Path(ruta).open("rb") as f:
        while bloque := f.read(BLOQUE):
            cantidad += len(bloque)
            if cantidad > MAX_ARCHIVO:
                raise IntegridadError("Archivo superior al límite de aula")
            digest.update(bloque)
    return cantidad, digest.hexdigest()


def inventariar(carpeta):
    carpeta = Path(carpeta)
    filas, nombres, total = [], set(), 0
    for p in enumerar_archivos(carpeta):
        relativa = p.relative_to(carpeta).as_posix()
        ruta_relativa_segura(relativa)
        clave = relativa.casefold()
        if clave in nombres or any(clave.startswith(v + "/") or v.startswith(clave + "/") for v in nombres):
            raise IntegridadError("Colisión de nombres o carpetas al ignorar mayúsculas")
        nombres.add(clave)
        n, sha = hash_archivo(p)
        total += n
        if total > MAX_TOTAL:
            raise IntegridadError("Tamaño total superior al límite de aula")
        filas.append({"ruta": relativa, "bytes": n, "sha256": sha})
    return filas


def validar_manifiesto(datos):
    claves = {"schema", "id", "creada_utc", "tipo", "motor", "archivos", "bytes_totales"}
    if not isinstance(datos, dict) or set(datos) != claves or type(datos["schema"]) is not int or datos["schema"] != 1:
        raise IntegridadError("Esquema de manifiesto incompatible")
    if not isinstance(datos["id"], str) or re.fullmatch(PATRON_COPIA, datos["id"]) is None:
        raise IntegridadError("Identidad de copia incompatible")
    if datos["tipo"] != "completa" or datos["motor"] != VERSION:
        raise IntegridadError("Tipo o versión no compatibles con este motor")
    try:
        fecha = datetime.fromisoformat(datos["creada_utc"])
        if fecha.utcoffset() != timezone.utc.utcoffset(fecha):
            raise ValueError("Se requiere UTC")
    except (TypeError, ValueError, AttributeError) as error:
        raise IntegridadError("Fecha UTC incompatible") from error
    if not isinstance(datos["archivos"], list) or len(datos["archivos"]) > MAX_ARCHIVOS:
        raise IntegridadError("Lista de archivos incompatible")
    vistos, total = set(), 0
    for fila in datos["archivos"]:
        if not isinstance(fila, dict) or set(fila) != {"ruta", "bytes", "sha256"}:
            raise IntegridadError("Entrada de manifiesto incompatible")
        p = ruta_relativa_segura(fila["ruta"])
        clave = p.as_posix().casefold()
        if clave in vistos or any(clave.startswith(v + "/") or v.startswith(clave + "/") for v in vistos):
            raise IntegridadError("Ruta duplicada o incompatible con otra")
        vistos.add(clave)
        if type(fila["bytes"]) is not int or not 0 <= fila["bytes"] <= MAX_ARCHIVO:
            raise IntegridadError("Tamaño de archivo incompatible")
        if not isinstance(fila["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", fila["sha256"]) is None:
            raise IntegridadError("Huella incompatible")
        total += fila["bytes"]
    if total > MAX_TOTAL or type(datos["bytes_totales"]) is not int or total != datos["bytes_totales"]:
        raise IntegridadError("El total del manifiesto no reconcilia")
    return datos


def verificar_directorio(carpeta):
    carpeta = Path(carpeta)
    if carpeta.is_symlink() or not carpeta.is_dir():
        raise IntegridadError("Copia no disponible como carpeta real")
    if {p.name for p in carpeta.iterdir()} != {"manifiesto.json", "contenido"}:
        raise IntegridadError("Estructura de copia inesperada")
    archivo = carpeta / "manifiesto.json"
    if archivo.is_symlink() or not archivo.is_file() or archivo.stat().st_size > 2 * 1024**2:
        raise IntegridadError("Manifiesto ausente o demasiado grande")
    try:
        datos = validar_manifiesto(json_estricto(archivo.read_text(encoding="utf-8")))
    except (ValueError, UnicodeError) as error:
        raise IntegridadError("Manifiesto inválido: " + str(error)) from error
    actual = inventariar(carpeta / "contenido")
    if sorted(actual, key=lambda f: f["ruta"]) != sorted(datos["archivos"], key=lambda f: f["ruta"]):
        raise IntegridadError("Rutas, tamaños o huellas no coinciden")
    return datos


def localizar_copia(raiz, nombre):
    if not isinstance(nombre, str) or re.fullmatch(PATRON_COPIA, nombre) is None:
        raise ContratoError("Nombre de copia publicada incompatible")
    ruta = raiz / "copias" / nombre
    datos = verificar_directorio(ruta)
    if datos["id"] != nombre:
        raise IntegridadError("La identidad del manifiesto no coincide con la carpeta")
    return ruta, datos


@contextmanager
def bloqueo(raiz):
    archivo = raiz / "estado" / "copias.lock"
    token = uuid.uuid4().hex
    try:
        fd = os.open(archivo, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise BloqueoOcupado("Ya existe una ejecución o un bloqueo pendiente de revisión") from error
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"token": token, "pid": os.getpid()}, f)
        yield
    finally:
        if archivo.exists() and not archivo.is_symlink():
            try:
                if json_estricto(archivo.read_text()).get("token") == token:
                    archivo.unlink()
            except (OSError, ValueError, AttributeError):
                LOG.error("Revisar bloqueo: no se pudo retirar con su identidad")


def copiar_contraste(origen, destino, esperado):
    """Crea exclusivamente; fuente quiescente y árbol privado como supuestos."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    digest, n = hashlib.sha256(), 0
    with origen.open("rb") as fuente, destino.open("xb") as salida:
        while bloque := fuente.read(BLOQUE):
            n += len(bloque)
            if n > MAX_ARCHIVO:
                raise IntegridadError("Archivo cambió o supera el límite")
            digest.update(bloque)
            salida.write(bloque)
    if n != esperado["bytes"] or digest.hexdigest() != esperado["sha256"]:
        raise IntegridadError("Contenido cambió entre inventario y copia")


def crear_copia(proyecto, aplicar=False):
    raiz = cargar_proyecto(proyecto)
    if type(aplicar) is not bool:
        raise ContratoError("aplicar debe ser booleano")
    def preparar():
        filas = inventariar(raiz / "origen")
        if not filas:
            raise ContratoError("No se publica una copia vacía en esta práctica")
        return filas
    if not aplicar:
        filas = preparar()
        return {"accion": "crear", "aplicado": False, "n_archivos": len(filas),
                "bytes_totales": sum(f["bytes"] for f in filas)}
    with bloqueo(raiz):
        filas = preparar()
        instante = datetime.now(timezone.utc)
        identificador = "copia_" + instante.strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
        parcial = raiz / "copias" / (".parcial_" + uuid.uuid4().hex)
        parcial.mkdir(mode=0o700)
        (parcial / "contenido").mkdir()
        for fila in filas:
            partes = PurePosixPath(fila["ruta"]).parts
            copiar_contraste((raiz / "origen").joinpath(*partes),
                            (parcial / "contenido").joinpath(*partes), fila)
        manifiesto = {"schema": 1, "id": identificador,
                      "creada_utc": instante.isoformat(), "tipo": "completa",
                      "motor": VERSION, "archivos": filas,
                      "bytes_totales": sum(f["bytes"] for f in filas)}
        with (parcial / "manifiesto.json").open("x", encoding="utf-8", newline="\n") as f:
            json.dump(manifiesto, f, ensure_ascii=False, indent=2)
        verificar_directorio(parcial)
        final = raiz / "copias" / identificador
        if final.exists():
            raise FileExistsError(final)
        parcial.rename(final)
        return {"accion": "crear", "aplicado": True, "copia": identificador,
                "n_archivos": len(filas), "bytes_totales": manifiesto["bytes_totales"],
                "verificada": True}


def verificar_copia(proyecto, nombre):
    raiz = cargar_proyecto(proyecto)
    _, datos = localizar_copia(raiz, nombre)
    return {"accion": "verificar", "copia": nombre, "verificada": True,
            "n_archivos": len(datos["archivos"]), "bytes_totales": datos["bytes_totales"]}


def restaurar_copia(proyecto, nombre, destino, aplicar=False):
    raiz = cargar_proyecto(proyecto)
    nombre_simple(destino)
    if type(aplicar) is not bool:
        raise ContratoError("aplicar debe ser booleano")
    carpeta_destino = raiz / "restauraciones" / destino
    if carpeta_destino.exists() or carpeta_destino.is_symlink():
        raise ContratoError("El destino de restauración debe ser nuevo")
    if not aplicar:
        _, datos = localizar_copia(raiz, nombre)
        return {"accion": "restaurar", "aplicado": False, "destino": destino,
                "n_archivos": len(datos["archivos"])}
    with bloqueo(raiz):
        copia, datos = localizar_copia(raiz, nombre)
        etapa = raiz / "restauraciones" / (".parcial_" + uuid.uuid4().hex)
        etapa.mkdir(mode=0o700)
        inicio = time.perf_counter()
        for fila in datos["archivos"]:
            partes = PurePosixPath(fila["ruta"]).parts
            copiar_contraste((copia / "contenido").joinpath(*partes), etapa.joinpath(*partes), fila)
        actual = inventariar(etapa)
        if actual != sorted(datos["archivos"], key=lambda f: f["ruta"]):
            raise IntegridadError("La restauración no coincide")
        if carpeta_destino.exists() or carpeta_destino.is_symlink():
            raise ContratoError("El destino apareció durante la operación")
        etapa.rename(carpeta_destino)
        return {"accion": "restaurar", "aplicado": True, "destino": destino,
                "n_archivos": len(actual), "bytes_totales": sum(f["bytes"] for f in actual),
                "contenido_verificado": True, "duracion_transferencia_y_contraste_s": time.perf_counter() - inicio}


def retener_copias(proyecto, conservar=2, aplicar=False):
    raiz = cargar_proyecto(proyecto)
    if type(conservar) is not int or conservar < 1:
        raise ContratoError("Se debe conservar al menos una copia")
    if type(aplicar) is not bool:
        raise ContratoError("aplicar debe ser booleano")
    def planificar():
        candidatas = []
        for p in (raiz / "copias").iterdir():
            if re.fullmatch(PATRON_COPIA, p.name):
                _, datos = localizar_copia(raiz, p.name)
                candidatas.append((datetime.fromisoformat(datos["creada_utc"]), p.name))
        candidatas.sort(reverse=True)
        return {"accion": "retencion", "conservar": [n for _, n in candidatas[:conservar]],
                "retirar": [n for _, n in candidatas[conservar:]], "aplicado": aplicar,
                "criterio": "fecha UTC declarada; integridad comprobada antes de retirar"}
    if not aplicar:
        return planificar()
    with bloqueo(raiz):
        plan = planificar()
        for nombre in plan["retirar"]:
            ruta, _ = localizar_copia(raiz, nombre)
            shutil.rmtree(ruta)  # Solo una generación reconocida y contrastada de este laboratorio.
        return plan


def crear_demo(destino):
    raiz = Path(destino).absolute()
    raiz.mkdir(parents=True, exist_ok=False, mode=0o700)
    for carpeta in ("origen", "copias", "restauraciones", "estado"):
        (raiz / carpeta).mkdir()
    marca = {"tipo": "demo_copias", "schema": 1, "id": uuid.uuid4().hex}
    (raiz / "proyecto_backup.json").write_text(json.dumps(marca), encoding="utf-8")
    textos = {"datos/listado_2025.csv": "id;importe\nDEMO-001;1200000\n",
              "contexto/territorios.json": '{"territorio":"DEMO","poblacion":1000}\n',
              "informes/resumen.md": "# Informe ficticio\n\nSolo datos de aula.\n",
              "config/parametros.json": '{"anio":2025,"moneda":"EUR"}\n',
              "vacio.txt": ""}
    for relativa, texto in textos.items():
        p = raiz / "origen" / relativa
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("x", encoding="utf-8", newline="\n") as f:
            f.write(texto)
    (raiz / "origen" / "pendiente").mkdir()
    return raiz


def main(argv=None):
    for canal in (sys.stdout, sys.stderr):
        if hasattr(canal, "reconfigure"):
            canal.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="accion", required=True)
    demo = sub.add_parser("crear-demo"); demo.add_argument("destino", type=Path)
    for accion in ("crear", "verificar", "restaurar", "retencion"):
        p = sub.add_parser(accion); p.add_argument("--proyecto", required=True, type=Path)
        if accion in {"verificar", "restaurar"}:
            p.add_argument("--copia", required=True)
        if accion == "restaurar":
            p.add_argument("--destino", required=True)
        if accion == "retencion":
            p.add_argument("--conservar", type=int, default=2)
        if accion != "verificar":
            p.add_argument("--aplicar", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.accion == "crear-demo":
            resultado = {"proyecto": str(crear_demo(args.destino))}
        elif args.accion == "crear":
            resultado = crear_copia(args.proyecto, args.aplicar)
        elif args.accion == "verificar":
            resultado = verificar_copia(args.proyecto, args.copia)
        elif args.accion == "restaurar":
            resultado = restaurar_copia(args.proyecto, args.copia, args.destino, args.aplicar)
        else:
            resultado = retener_copias(args.proyecto, args.conservar, args.aplicar)
        print(json.dumps(resultado, ensure_ascii=False))
        return 0
    except BloqueoOcupado as error:
        LOG.error("Bloqueo: %s", error); return 40
    except ContratoError as error:
        LOG.error("Contrato: %s", error); return 20
    except IntegridadError as error:
        LOG.error("Integridad: %s", error); return 10
    except OSError:
        LOG.exception("Fallo operativo; revisar parciales"); return 30
    except Exception:
        LOG.exception("Fallo inesperado"); return 30


if __name__ == "__main__":
    raise SystemExit(main())
