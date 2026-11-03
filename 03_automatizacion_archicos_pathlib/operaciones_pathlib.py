"""Bloque 03: herramientas didácticas para un laboratorio temporal privado."""
from pathlib import Path, PureWindowsPath, PurePosixPath
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
from copy import deepcopy
import shutil
import json

VERSION_LAB = "pathlib-aula-1.0"


def validar_nombre_simple(nombre):
    """Política conservadora de nombres para la práctica Windows/Linux."""
    if not isinstance(nombre, str) or not nombre or nombre in {".", ".."}:
        raise ValueError("Se requiere un nombre simple no vacío")
    if nombre != nombre.strip() or nombre.endswith("."):
        raise ValueError("No se admiten espacios extremos ni punto final")
    prohibidos = set('<>:"/\\|?*')
    if any(c in prohibidos or ord(c) < 32 for c in nombre):
        raise ValueError("Nombre con separadores o caracteres no admitidos")
    reservados = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefijo}{i}" for prefijo in ("COM", "LPT") for i in range(1, 10)
    }
    if nombre.split(".", 1)[0].upper() in reservados:
        raise ValueError("Nombre reservado en Windows")
    return nombre


def asegurar_dentro(base, ruta, exigir_existencia=False):
    """Control didáctico de alcance, sin seguir enlaces ni aceptar '..'.

    La raíz debe ser una carpeta real, privada y sin modificaciones concurrentes.
    No constituye una frontera de seguridad frente a procesos hostiles.
    """
    raiz = Path(base).resolve(strict=True)
    if not raiz.is_dir():
        raise NotADirectoryError(raiz)
    candidata = Path(ruta)
    if not candidata.is_absolute():
        candidata = raiz / candidata
    if ".." in candidata.parts:
        raise ValueError("La política del laboratorio no admite '..'")
    try:
        relativa = candidata.relative_to(raiz)
    except ValueError as error:
        raise ValueError("Ruta fuera del laboratorio") from error
    paso = raiz
    for parte in relativa.parts:
        paso = paso / parte
        if paso.is_symlink():
            raise ValueError("La práctica no opera sobre enlaces simbólicos")
    resuelta = candidata.resolve(strict=exigir_existencia)
    if not resuelta.is_relative_to(raiz):
        raise ValueError("Destino resuelto fuera del laboratorio")
    return resuelta


def crear_entorno(base):
    """Crea datos nuevos; nunca reutiliza ni vacía una carpeta existente."""
    contenedor = Path(base).resolve(strict=True)
    raiz = contenedor / "laboratorio_pathlib"
    raiz.mkdir(exist_ok=False)
    entrada, salida = raiz / "entrada", raiz / "salida"
    entrada.mkdir()
    salida.mkdir()
    (entrada / "subcarpeta").mkdir()
    textos = {
        "listado_2024.csv": "id;importe;anio\nDEMO-001;100;2024\n",
        "listado_2025.CSV": "id;importe;anio\nDEMO-002;200;2025\n",
        "notas.txt": "Datos ficticios para aprender a manejar rutas.\n",
        "vacio.txt": "",
        "con espacios.txt": "La ruta puede contener espacios y acentos: revisión.\n",
        "subcarpeta/contexto.json": '{"territorio": "DEMO", "poblacion": 1000}\n',
        "archivo.tar.gz": "Ejemplo de nombre compuesto; no es un archivo comprimido.\n",
    }
    for relativa, texto in textos.items():
        with (entrada / relativa).open("x", encoding="utf-8", newline="\n") as f:
            f.write(texto)
    return {"raiz": raiz, "entrada": entrada, "salida": salida}


def inventariar(base, carpeta):
    """Inventario explícito de archivos regulares, ordenado por ruta.

    Se recorren directorios con iterdir para no depender de errores que
    glob/rglob puedan omitir. Se excluyen enlaces y se propagan fallos.
    El árbol debe permanecer estable durante esta práctica sin concurrencia.
    """
    raiz = Path(base).resolve(strict=True)
    carpeta = asegurar_dentro(raiz, carpeta, exigir_existencia=True)
    if not carpeta.is_dir():
        raise NotADirectoryError(carpeta)
    filas, pendientes = [], [carpeta]
    while pendientes:
        actual = pendientes.pop()
        for ruta in sorted(actual.iterdir(), key=lambda p: p.as_posix()):
            if ruta.is_symlink():
                continue
            ruta = asegurar_dentro(raiz, ruta, exigir_existencia=True)
            if ruta.is_dir():
                pendientes.append(ruta)
            elif ruta.is_file():
                info = ruta.stat()
                filas.append({"ruta": ruta.relative_to(raiz).as_posix(),
                              "nombre": ruta.name, "extension": ruta.suffix.lower(),
                              "bytes": info.st_size,
                              "modificado_utc": datetime.fromtimestamp(
                                  info.st_mtime, tz=timezone.utc).isoformat()})
    return sorted(filas, key=lambda f: f["ruta"])


def escribir_texto_nuevo(base, destino, texto):
    """Escritura exclusiva: falla si existe, incluso si está vacío."""
    if not isinstance(texto, str):
        raise TypeError("El contenido debe ser texto")
    destino = asegurar_dentro(base, destino)
    # La carpeta debe crearse expresamente antes de escribir.
    if not destino.parent.is_dir():
        raise FileNotFoundError(destino.parent)
    with destino.open("x", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    return destino


def copiar_nuevo(base, origen, destino):
    """Copia el contenido con creación exclusiva del archivo de destino.

    No copia propietarios ni ACL ni promete preservación de metadatos.
    Si falla durante la escritura puede quedar una copia parcial para revisar.
    """
    origen = asegurar_dentro(base, origen, exigir_existencia=True)
    destino = asegurar_dentro(base, destino)
    if not origen.is_file():
        raise ValueError("El origen debe ser un archivo regular")
    if not destino.parent.is_dir():
        raise FileNotFoundError(destino.parent)
    with origen.open("rb") as fuente, destino.open("xb") as salida:
        shutil.copyfileobj(fuente, salida)
    return destino


def trasladar_local(base, origen, destino, simular=True):
    """Previsualiza o usa Path.rename en el laboratorio sin concurrencia.

    La comprobación previa de colisión NO hace rename exclusivo frente a
    carreras en POSIX. Solo se usa con datos temporales y un único escritor.
    No es una operación general entre unidades o sistemas de archivos.
    """
    if type(simular) is not bool:
        raise TypeError("simular debe ser un booleano")
    origen = asegurar_dentro(base, origen, exigir_existencia=True)
    destino = asegurar_dentro(base, destino)
    if not origen.is_file():
        raise ValueError("La práctica solo traslada archivos regulares")
    if origen == destino:
        raise ValueError("Origen y destino coinciden")
    if destino.exists() or destino.is_symlink():
        raise FileExistsError(destino)
    if not destino.parent.is_dir():
        raise FileNotFoundError(destino.parent)
    plan = {"origen": str(origen), "destino": str(destino),
            "ejecutado": not simular}
    if not simular:
        origen.rename(destino)
    return plan


def renombrar_local(base, origen, nuevo_nombre, simular=True):
    validar_nombre_simple(nuevo_nombre)
    origen = asegurar_dentro(base, origen, exigir_existencia=True)
    return trasladar_local(base, origen, origen.with_name(nuevo_nombre), simular)


def borrar_demo(base, ruta, simular=True):
    """Solo un archivo del laboratorio. Sin borrado recursivo."""
    if type(simular) is not bool:
        raise TypeError("simular debe ser un booleano")
    ruta = asegurar_dentro(base, ruta, exigir_existencia=True)
    if not ruta.is_file():
        raise ValueError("Solo se admite un archivo regular")
    if not simular:
        ruta.unlink()
    return {"ruta": str(ruta), "eliminado": not simular}
