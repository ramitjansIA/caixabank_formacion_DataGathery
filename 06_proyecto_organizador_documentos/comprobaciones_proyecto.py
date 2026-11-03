"""Pruebas de contrato. Solo demos propias en TemporaryDirectory; sin tareas."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import contextlib
import csv
import io
import json
import subprocess
import sys
import unittest
import organizador as o

class ProyectoTest(unittest.TestCase):
    def setUp(self):
        self.temporal = TemporaryDirectory(prefix="observatorio_test_")
        self.base = Path(self.temporal.name)
        self.p = o.crear_demo(self.base / "proyecto con espacios")
    def tearDown(self):
        self.temporal.cleanup()
    def test_01_plan_puro_y_conservacion(self):
        antes = o.backup.inventariar(self.p / "origen")
        todos_antes = o.backup.inventariar(self.p)
        r = o.resumen_plan(self.p)
        self.assertEqual(r["conteo"], {"crear":4,"duplicado_lote":1,"revision":3,"conflicto_lote":2})
        self.assertEqual(sum(r["conteo"].values()),10)
        self.assertEqual(antes,o.backup.inventariar(self.p / "origen"))
        self.assertEqual(todos_antes,o.backup.inventariar(self.p))
        self.assertFalse(r["aplicado"])
    def test_02_fecha_forma_y_sufijo(self):
        reglas=o.cargar_reglas(self.p)
        casos={"sin_fecha.txt":"nombre_fuera_de_contrato", "2026-02-30_informe_DOC-001.md":"fecha_invalida", "2026-10-01_otra_DOC-001.md":"tipo_sin_regla", "2026-10-01_informe_DOC-001.txt":"sufijo_incompatible"}
        for nombre,motivo in casos.items():
            self.assertEqual(o.clasificar(nombre,reglas)["motivo"],motivo)
    def test_03_primera_aplicacion_copia_e_informe(self):
        antes=o.backup.inventariar(self.p/"origen")
        r=o.ejecutar(self.p,True)
        self.assertEqual(r["conteo"],{"creado":4,"duplicado_lote":1,"revision":3,"conflicto_lote":2})
        self.assertEqual(r["codigo"],10)
        self.assertEqual(o.backup.verificar_copia(self.p,r["copia_previa"])["n_archivos"],10)
        self.assertEqual(len(o.backup.inventariar(self.p/"archivo")),4)
        self.assertEqual(antes,o.backup.inventariar(self.p/"origen"))
        self.assertEqual(json.loads((self.p/"informes"/r["informe"]).read_text()),r)
        self.assertFalse((self.p/"estado/organizador.lock").exists())
    def test_04_repeticion_no_cambia_salidas(self):
        o.ejecutar(self.p,True)
        antes={p.relative_to(self.p/"archivo").as_posix():(p.read_bytes(),p.stat().st_mtime_ns) for p in (self.p/"archivo").rglob('*') if p.is_file()}
        copias=set((self.p/"copias").iterdir())
        r=o.ejecutar(self.p,True)
        despues={p.relative_to(self.p/"archivo").as_posix():(p.read_bytes(),p.stat().st_mtime_ns) for p in (self.p/"archivo").rglob('*') if p.is_file()}
        self.assertEqual(antes,despues)
        self.assertEqual(copias,set((self.p/"copias").iterdir()))
        self.assertIsNone(r["copia_previa"])
        self.assertEqual(r["conteo"]["existente"],4)
        self.assertEqual(len(list((self.p/"informes").iterdir())),2)
    def test_05_conflicto_destino_no_sobrescribe(self):
        r=o.ejecutar(self.p,True)
        fila=next(f for f in r["filas"] if f["estado"]=="creado")
        destino=self.p/"archivo"/fila["destino"]
        destino.write_bytes(b"Alteracion de aula")
        r2=o.ejecutar(self.p,True)
        self.assertEqual(r2["conteo"]["conflicto_destino"],1)
        self.assertEqual(destino.read_bytes(),b"Alteracion de aula")
    def test_06_restauracion_y_lectura(self):
        r=o.ejecutar(self.p,True)
        original=o.backup.inventariar(self.p/"origen")
        perdida=self.p/"origen/equipo_a/2026-10-01_datos_DOC-001.csv"
        perdida.unlink()
        o.backup.restaurar_copia(self.p,r["copia_previa"],"rescate",True)
        recuperado=self.p/"restauraciones/rescate"
        self.assertEqual(original,o.backup.inventariar(recuperado))
        with (recuperado/"equipo_a/2026-10-01_datos_DOC-001.csv").open(encoding="utf-8",newline="") as f:
            filas=list(csv.DictReader(f,delimiter=";"))
        self.assertEqual(int(filas[0]["importe"]),1200000)
        self.assertFalse(perdida.exists())
    def test_07_regla_peligrosa(self):
        reglas=o.cargar_reglas(self.p)
        reglas["tipos"]["informe"]["carpeta"]="../fuera"
        (self.p/"reglas.json").write_text(json.dumps(reglas))
        with self.assertRaises(o.backup.ContratoError):o.ejecutar(self.p,True)
        self.assertFalse(list((self.p/"archivo").iterdir()))
        self.assertFalse((self.p/"estado/organizador.lock").exists())
    def test_08_bloqueo_ocupado(self):
        lock=self.p/"estado/organizador.lock";lock.write_text("otro")
        with self.assertRaises(o.backup.BloqueoOcupado):o.ejecutar(self.p,True)
        self.assertEqual(lock.read_text(),"otro")
        self.assertFalse(list((self.p/"archivo").iterdir()))
    def test_09_backup_fallido_impide_publicacion(self):
        with patch.object(o.backup,'crear_copia',side_effect=OSError("disco simulado")):
            with self.assertRaises(OSError):o.ejecutar(self.p,True)
        self.assertFalse(list((self.p/"archivo").iterdir()))
        self.assertFalse(list((self.p/"informes").iterdir()))
        self.assertFalse((self.p/"estado/organizador.lock").exists())
    def test_10_fallo_local_no_se_oculta(self):
        original=o.copiar_documento;contador=0
        def falla_una(raiz,fila):
            nonlocal contador
            contador+=1
            if contador==1:raise OSError("fallo de aula")
            return original(raiz,fila)
        with patch.object(o,'copiar_documento',falla_una):r=o.ejecutar(self.p,True)
        self.assertEqual(r["codigo"],30)
        self.assertEqual(r["conteo"]["error_operativo"],1)
        self.assertEqual(r["conteo"]["creado"],3)
        self.assertEqual(len(o.backup.inventariar(self.p/"archivo")),3)
        r2=o.ejecutar(self.p,True)
        self.assertEqual(r2["conteo"]["creado"],1)
        self.assertEqual(r2["conteo"]["existente"],3)
    def test_11_enlace_y_colision(self):
        externo=self.base/"externo";externo.mkdir()
        link=self.p/"archivo/informes"
        try:link.symlink_to(externo,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest("Enlaces no disponibles")
        with self.assertRaises(o.backup.ContratoError):o.planificar(self.p)
        self.assertFalse(list(externo.iterdir()))
        link.unlink();(self.p/"archivo/Informes").mkdir()
        with self.assertRaises(o.backup.ContratoError):o.planificar(self.p)
    def test_12_cambio_antes_de_copia(self):
        fila=next(f for f in o.planificar(self.p)["filas"] if f["estado"]=="crear")
        fuente=self.p/"origen"/fila["ruta"];fuente.write_bytes(b"cambio")
        with self.assertRaises(o.backup.IntegridadError):o.copiar_documento(self.p,fila)
        self.assertFalse((self.p/"archivo"/fila["destino"]).exists())
        self.assertTrue(list((self.p/"archivo").rglob('.parcial_*')))
    def test_13_cli_y_cwd(self):
        motor=Path(o.__file__).resolve()
        cmd=[sys.executable,str(motor),'ejecutar','--proyecto',str(self.p)]
        r=subprocess.run(cmd,cwd=self.base,capture_output=True,text=True)
        self.assertEqual(r.returncode,0);self.assertFalse(json.loads(r.stdout)["aplicado"])
        r=subprocess.run(cmd+['--aplicar'],cwd=self.base,capture_output=True,text=True)
        self.assertEqual(r.returncode,10);self.assertEqual(json.loads(r.stdout)["conteo"]["creado"],4)
        (self.p/"estado/organizador.lock").write_text('otro')
        r=subprocess.run(cmd+['--aplicar'],cwd=self.base,capture_output=True,text=True)
        self.assertEqual(r.returncode,40);self.assertTrue(r.stderr)
    def test_14_nuevo_tipo_y_reclasificacion(self):
        reglas=o.cargar_reglas(self.p)
        reglas["tipos"]["resumen"]={"sufijo":".txt","carpeta":"resumenes"}
        (self.p/"reglas.json").write_text(json.dumps(reglas))
        (self.p/"origen/2026-10-08_resumen_DOC-008.txt").write_text('Ficticio')
        r=o.ejecutar(self.p,True)
        self.assertEqual(r["conteo"]["creado"],5)
        self.assertEqual(o.backup.verificar_copia(self.p,r["copia_previa"])["n_archivos"],11)
    def test_15_carpeta_vacia_y_json_duplicado(self):
        for p in (self.p/"origen").rglob('*'):
            if p.is_file():p.unlink()
        r=o.ejecutar(self.p,True)
        self.assertEqual(r["conteo"],{});self.assertEqual(r["codigo"],0)
        self.assertIsNone(r["copia_previa"])
        (self.p/"reglas.json").write_text('{"schema":1,"schema":2}')
        with self.assertRaises(o.backup.ContratoError):o.cargar_reglas(self.p)
    def test_16_etapas_ejecutables(self):
        raiz=Path(o.__file__).resolve().parent
        p=self.base/"por etapas"
        ordenes=[('01_demo.py',['crear-demo',str(p)],0),('02_configuracion.py',['inspeccionar',str(p)],0),('03_clasificacion.py',['clasificar',str(p)],0),('04_plan.py',['plan',str(p)],0),('05_simulacion.py',['plan',str(p)],0),('06_copia_contrastada.py',['plan',str(p)],0),('07_ejecucion.py',['ejecutar',str(p),'--aplicar'],10),('08_cli.py',['plan','--proyecto',str(p)],0)]
        for archivo,args,codigo in ordenes:
            r=subprocess.run([sys.executable,str(raiz/'etapas'/archivo),*args],cwd=self.base,capture_output=True,text=True)
            self.assertEqual(r.returncode,codigo,r.stderr)
            self.assertIsInstance(json.loads(r.stdout),dict)

if __name__=='__main__':
    unittest.main(verbosity=2)
