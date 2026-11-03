"""Organizador del observatorio, Python 3.11+. Solo proyectos sintéticos privados.
Conserva origen, clasifica por reglas y no sobrescribe destinos.
Reutiliza copias_seguridad.py del bloque 05, incluido al lado.
"""
from pathlib import Path, PurePosixPath
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import argparse
import json
import logging
import re
import sys
import uuid
import copias_seguridad as backup

REGLAS = {
    "schema": 1,
    "tipos": {
        "datos": {"sufijo": ".csv", "carpeta": "datos"},
        "informe": {"sufijo": ".md", "carpeta": "informes"},
        "contexto": {"sufijo": ".json", "carpeta": "contexto"},
        "acta": {"sufijo": ".txt", "carpeta": "actas"},
    },
}
PATRON = (
    r"(?P<fecha>\d{4}-\d{2}-\d{2})_(?P<tipo>[a-z]+)_"
    r"(?P<id>DOC-\d{3})(?P<sufijo>\.[a-z]+)"
)
LOG = logging.getLogger("organizador")


def crear_demo(destino):
    """Etapa 01. Crear únicamente una raíz nueva con datos ficticios."""
    raiz = Path(destino).absolute()
    raiz.mkdir(parents=True, exist_ok=False, mode=0o700)
    for nombre in ("origen", "archivo", "informes", "copias", "restauraciones", "estado"):
        (raiz / nombre).mkdir()
    marca = {"tipo": "demo_copias", "schema": 1, "id": uuid.uuid4().hex}
    (raiz / "proyecto_backup.json").write_text(json.dumps(marca), encoding="utf-8")
    (raiz / "organizador.json").write_text(
        '{"schema":1,"tipo":"observatorio_aula"}', encoding="utf-8"
    )
    (raiz / "reglas.json").write_text(json.dumps(REGLAS, indent=2), encoding="utf-8")
    textos = {
        "equipo_a/2026-10-01_datos_DOC-001.csv": "id;importe\nDEMO-001;1200000\n",
        "equipo_b/2026-10-01_datos_DOC-001.csv": "id;importe\nDEMO-001;1200000\n",
        "2026-10-02_informe_DOC-002.md": "# Informe ficticio\nSolo datos de aula.\n",
        "2026-10-03_contexto_DOC-003.json": '{"territorio":"DEMO"}\n',
        "2026-10-04_acta_DOC-004.txt": "Acta ficticia del observatorio.\n",
        "sin_fecha.txt": "Pendiente de identificar.\n",
        "2026-02-30_informe_DOC-005.md": "Fecha imposible.\n",
        "2026-10-06_informe_DOC-006.txt": "Tipo y extension incompatibles.\n",
        "area_a/2026-10-07_informe_DOC-007.md": "Version A\n",
        "area_b/2026-10-07_informe_DOC-007.md": "Version B\n",
    }
    for relativa, texto in textos.items():
        p = raiz / "origen" / relativa
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("x", encoding="utf-8", newline="\n") as f:
            f.write(texto)
    return raiz


def leer_json(ruta):
    """Etapa 02. Lectura acotada de un archivo real, sin enlaces."""
    if ruta.is_symlink() or not ruta.is_file():
        raise backup.ContratoError("Se requiere un JSON regular")
    with ruta.open("rb") as f:
        datos = f.read(65537)
    if len(datos) > 65536:
        raise backup.ContratoError("JSON de control demasiado grande")
    try:
        return backup.json_estricto(datos.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise backup.ContratoError("JSON de control inválido") from error


def cargar_proyecto(proyecto):
    raiz = backup.cargar_proyecto(proyecto)
    if leer_json(raiz / "organizador.json") != {"schema": 1, "tipo": "observatorio_aula"}:
        raise backup.ContratoError("No se reconoce el organizador de aula")
    for nombre in ("archivo", "informes"):
        p = raiz / nombre
        if p.is_symlink() or not p.is_dir():
            raise backup.ContratoError("Falta una carpeta real: " + nombre)
    return raiz


def cargar_reglas(raiz):
    reglas = leer_json(raiz / "reglas.json")
    if not isinstance(reglas, dict) or set(reglas) != {"schema", "tipos"}:
        raise backup.ContratoError("Campos de reglas incompatibles")
    if type(reglas["schema"]) is not int or reglas["schema"] != 1:
        raise backup.ContratoError("Versión de reglas incompatible")
    tipos = reglas["tipos"]
    if not isinstance(tipos, dict) or not 1 <= len(tipos) <= 20:
        raise backup.ContratoError("Se requieren entre 1 y 20 tipos")
    for tipo, regla in tipos.items():
        if not re.fullmatch(r"[a-z]+", tipo) or not isinstance(regla, dict):
            raise backup.ContratoError("Tipo o regla incompatible")
        if set(regla) != {"sufijo", "carpeta"}:
            raise backup.ContratoError("Campos de una regla incompatibles")
        sufijo = regla["sufijo"]
        if not isinstance(sufijo, str) or not re.fullmatch(r"\.[a-z]+", sufijo):
            raise backup.ContratoError("Sufijo incompatible")
        backup.nombre_simple(regla["carpeta"])
    return reglas


def clasificar(relativa, reglas):
    """Etapa 03. Una decisión explícita, sin adivinar el contenido."""
    nombre = backup.ruta_relativa_segura(relativa).name
    m = re.fullmatch(PATRON, nombre, flags=re.ASCII)
    if m is None:
        return {"motivo": "nombre_fuera_de_contrato"}
    try:
        fecha = date.fromisoformat(m["fecha"])
    except ValueError:
        return {"motivo": "fecha_invalida"}
    regla = reglas["tipos"].get(m["tipo"])
    if regla is None:
        return {"motivo": "tipo_sin_regla"}
    if m["sufijo"] != regla["sufijo"]:
        return {"motivo": "sufijo_incompatible"}
    destino = PurePosixPath(
        regla["carpeta"], str(fecha.year), f"{fecha.month:02d}", nombre
    )
    backup.ruta_relativa_segura(destino.as_posix())
    return {"destino": destino.as_posix(), "motivo": "regla_de_nombre"}


def resolver_destino(raiz, relativa):
    """Etapa 04. Ningún componente existente del destino puede ser enlace."""
    partes = backup.ruta_relativa_segura(relativa).parts
    actual = raiz / "archivo"
    for i, parte in enumerate(partes):
        actual = actual / parte
        if actual.parent.exists() and any(
            p.name.casefold() == parte.casefold() and p.name != parte
            for p in actual.parent.iterdir()
        ):
            raise backup.ContratoError("Colisión de mayúsculas en destino")
        if actual.is_symlink():
            raise backup.ContratoError("Enlace en destino")
        if actual.exists() and i < len(partes) - 1 and not actual.is_dir():
            raise backup.ContratoError("Un archivo ocupa una carpeta de destino")
        if actual.exists() and i == len(partes) - 1 and not actual.is_file():
            raise backup.ContratoError("Destino existente no regular")
    return actual


def planificar(proyecto):
    """Un plan nuevo refleja el estado actual; no autoriza una ejecución futura."""
    raiz = cargar_proyecto(proyecto)
    reglas = cargar_reglas(raiz)
    filas = []
    for entrada in backup.inventariar(raiz / "origen"):
        fila = dict(entrada)
        fila.update(clasificar(entrada["ruta"], reglas))
        fila["estado"] = "candidato" if "destino" in fila else "revision"
        filas.append(fila)
    grupos = defaultdict(list)
    for fila in filas:
        if fila["estado"] == "candidato":
            grupos[fila["destino"].casefold()].append(fila)
    for grupo in grupos.values():
        if len({f["sha256"] for f in grupo}) > 1:
            for fila in grupo:
                fila.update(
                    estado="conflicto_lote", motivo="mismo_destino_bytes_distintos"
                )
            continue
        primera = grupo[0]
        destino = resolver_destino(raiz, primera["destino"])
        if not destino.exists():
            primera["estado"] = "crear"
        else:
            n, h = backup.hash_archivo(destino)
            coincide = (n, h) == (primera["bytes"], primera["sha256"])
            primera["estado"] = "existente" if coincide else "conflicto_destino"
        for repetida in grupo[1:]:
            repetida.update(estado="duplicado_lote", motivo="mismo_destino_y_bytes",
                           representante=primera["ruta"])
    return {"schema": 1, "proyecto": str(raiz), "reglas": reglas,
            "filas": filas, "conteo": dict(Counter(f["estado"] for f in filas))}


def resumen_plan(proyecto):
    """Etapa 05. La simulación completa no escribe un informe en disco."""
    plan = planificar(proyecto)
    return {"accion": "plan", "aplicado": False, **plan}


def copiar_documento(raiz, fila):
    """Etapa 06. Publicación por archivo, nunca sobrescritura deliberada."""
    origen = (raiz / "origen").joinpath(*PurePosixPath(fila["ruta"]).parts)
    destino = resolver_destino(raiz, fila["destino"])
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.parent / (".parcial_" + uuid.uuid4().hex)
    backup.copiar_contraste(origen, parcial, fila)
    if backup.hash_archivo(parcial) != (fila["bytes"], fila["sha256"]):
        raise backup.IntegridadError("Fallo de contraste del parcial")
    if destino.exists() or destino.is_symlink():
        raise backup.ContratoError("El destino apareció; no se publica")
    parcial.rename(destino)
    return "creado"


def ejecutar(proyecto, aplicar=False):
    """Etapa 07. Bloqueo de organizador -> backup con su bloqueo -> publicación."""
    if type(aplicar) is not bool:
        raise backup.ContratoError("aplicar debe ser booleano")
    if not aplicar:
        return resumen_plan(proyecto)
    raiz = cargar_proyecto(proyecto)
    lock = raiz / "estado" / "organizador.lock"
    token = uuid.uuid4().hex
    try:
        with lock.open("x", encoding="utf-8") as f:
            f.write(token)
    except FileExistsError as error:
        raise backup.BloqueoOcupado("Organizador ocupado") from error
    try:
        plan = planificar(raiz)
        generacion = None
        if plan["conteo"].get("crear", 0):
            generacion = backup.crear_copia(raiz, aplicar=True)["copia"]
        for fila in plan["filas"]:
            if fila["estado"] == "crear":
                try:
                    fila["estado"] = copiar_documento(raiz, fila)
                except (OSError, ValueError) as error:
                    fila.update(estado="error_operativo", motivo=type(error).__name__)
        conteo = dict(Counter(f["estado"] for f in plan["filas"]))
        pendientes = ("revision", "conflicto_lote", "conflicto_destino")
        incidencias = any(conteo.get(k, 0) for k in pendientes)
        codigo = 30 if conteo.get("error_operativo", 0) else 10 if incidencias else 0
        informe = {**plan, "accion": "ejecutar", "aplicado": True,
                   "conteo": conteo, "codigo": codigo, "copia_previa": generacion,
                   "fecha_utc": datetime.now(timezone.utc).isoformat()}
        nombre = "ejecucion_" + uuid.uuid4().hex + ".json"
        informe["informe"] = nombre
        with (raiz / "informes" / nombre).open("x", encoding="utf-8") as f:
            json.dump(informe, f, ensure_ascii=False, indent=2)
        return informe
    finally:
        if (lock.is_file() and not lock.is_symlink()
                and lock.read_text(encoding="utf-8") == token):
            lock.unlink()


def main(argv=None):
    """Etapa 08. CLI independiente de cwd y sin preguntas interactivas."""
    for canal in (sys.stdout, sys.stderr):
        if hasattr(canal, "reconfigure"):
            canal.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="accion", required=True)
    crear = sub.add_parser("crear-demo")
    crear.add_argument("destino", type=Path)
    for accion in ("plan", "ejecutar"):
        p = sub.add_parser(accion)
        p.add_argument("--proyecto", type=Path, required=True)
        if accion == "ejecutar":
            p.add_argument("--aplicar", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    try:
        if args.accion == "crear-demo":
            resultado = {"proyecto": str(crear_demo(args.destino))}
        elif args.accion == "plan":
            resultado = resumen_plan(args.proyecto)
        else:
            resultado = ejecutar(args.proyecto, args.aplicar)
        print(json.dumps(resultado, ensure_ascii=False))
        return resultado.get("codigo", 0)
    except backup.BloqueoOcupado:
        LOG.error("Bloqueo de copias ocupado")
        return 40
    except (backup.ContratoError, backup.IntegridadError, FileExistsError) as error:
        LOG.error("Contrato o integridad: %s", error)
        return 20
    except Exception:
        LOG.exception("Fallo operativo; revisar informe, parciales y archivo")
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
