"""Pruebas acotadas del flujo Excel I, sin archivos personales ni tareas."""
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import date, datetime
from openpyxl import Workbook, load_workbook
import json,subprocess,sys,unittest
import excel_observatorio as e

class ExcelTest(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix="test_excel07_")
        self.base=Path(self.tmp.name)
        self.p=e.preparar_demo(self.base/"caso con espacios")
        self.entrada=self.p/"entrada_excel/seguimiento_entrada.xlsx"
    def tearDown(self):self.tmp.cleanup()
    def modificar(self,celda,valor):
        w=load_workbook(self.entrada);w.active[celda]=valor;w.save(self.entrada);w.close()
    def test_01_continuidad_y_tipos(self):
        f=e.leer_entradas(self.entrada)
        self.assertEqual(len(f),10)
        self.assertEqual(f[0]["entrada_id"],"0001")
        self.assertEqual(sum(x['fecha'] is None for x in f),2)
        self.assertTrue(all(type(x['bytes']) is int for x in f))
        self.assertEqual(dict(e.Counter(x['estado'] for x in f)),{'revision':3,'creado':4,'conflicto_lote':2,'duplicado_lote':1})
    def test_02_simulacion_no_escribe(self):
        antes=self.entrada.read_bytes();r=e.generar(self.p)
        self.assertFalse(r['aplicado']);self.assertFalse(list((self.p/'salida_excel').iterdir()))
        self.assertEqual(antes,self.entrada.read_bytes())
    def test_03_entrega_reconciliada(self):
        antes=self.entrada.read_bytes();r=e.generar(self.p,True)
        e.verificar_libro(r['salida'],e.leer_entradas(self.entrada))
        w=load_workbook(r['salida'])
        try:
            self.assertEqual(w['Resumen']['B13'].value,10)
            self.assertEqual(w['Resumen']['B14'].value,5)
            self.assertEqual(w['Documentos']['A5'].value,'0001')
            self.assertEqual(w['Documentos']['A5'].data_type,'s')
            self.assertEqual(w['Documentos']['D5'].data_type,'n')
            self.assertEqual(w['Documentos']['C6'].number_format,'dd/mm/yyyy')
        finally:w.close()
        self.assertEqual(antes,self.entrada.read_bytes())
    def test_04_no_sobrescritura(self):
        r=e.generar(self.p,True);antes=Path(r['salida']).read_bytes()
        with self.assertRaises(FileExistsError):e.generar(self.p,True)
        self.assertEqual(antes,Path(r['salida']).read_bytes())
        self.assertTrue(e.generar(self.p,True,'version2.xlsx')['verificado'])
    def test_05_cabecera_y_id(self):
        self.modificar('A1','otro')
        with self.assertRaises(ValueError):e.generar(self.p,True)
        self.assertFalse(list((self.p/'salida_excel').iterdir()))
    def test_06_formula_entrada(self):
        self.modificar('D2','=1+1')
        with self.assertRaisesRegex(ValueError,'fórmula'):e.leer_entradas(self.entrada)
    def test_07_fecha_texto_y_id_numero(self):
        self.modificar('C2','01/10/2026')
        with self.assertRaisesRegex(ValueError,'fecha'):e.leer_entradas(self.entrada)
        self.modificar('C2',None);self.modificar('A2',1)
        with self.assertRaisesRegex(ValueError,'entrada_id'):e.leer_entradas(self.entrada)
    def test_08_id_repetido(self):
        self.modificar('A3','0001')
        with self.assertRaisesRegex(ValueError,'repetido'):e.leer_entradas(self.entrada)
    def test_09_cero_es_valido(self):
        self.modificar('D2',0)
        f=e.leer_entradas(self.entrada);self.assertEqual(f[0]['bytes'],0)
        self.modificar('D2',True)
        with self.assertRaisesRegex(ValueError,'bytes'):e.leer_entradas(self.entrada)
    def test_10_estado_y_ruta(self):
        self.modificar('E2','inventado')
        with self.assertRaisesRegex(ValueError,'estado'):e.leer_entradas(self.entrada)
        self.modificar('E2','revision');self.modificar('B2','../fuera')
        with self.assertRaises(ValueError):e.leer_entradas(self.entrada)
    def test_11_formula_cache_y_literal(self):
        w=Workbook();s=w.active;s['A1']=4;s['A2']=6;s['A3']='=SUM(A1:A2)'
        e.escribir_celda(s,4,1,'=1+1');p=self.base/'formulas.xlsx';w.save(p);w.close()
        a=load_workbook(p,data_only=False);b=load_workbook(p,data_only=True)
        try:
            self.assertEqual(a.active['A3'].value,'=SUM(A1:A2)')
            self.assertIsNone(b.active['A3'].value)
            self.assertEqual(a.active['A4'].data_type,'s')
            self.assertEqual(b.active['A4'].value,'=1+1')
        finally:a.close();b.close()
    def test_12_cli_cwd_y_nombre_peligroso(self):
        motor=Path(e.__file__).resolve()
        cmd=[sys.executable,str(motor),'generar','--proyecto',str(self.p)]
        r=subprocess.run(cmd,cwd=self.base,capture_output=True,text=True)
        self.assertEqual(r.returncode,0);self.assertFalse(json.loads(r.stdout)['aplicado'])
        r=subprocess.run(cmd+['--aplicar'],cwd=self.base,capture_output=True,text=True)
        self.assertEqual(r.returncode,0);self.assertTrue(json.loads(r.stdout)['verificado'])
        r=subprocess.run(cmd+['--aplicar','--nombre','../fuera.xlsx'],cwd=self.base,capture_output=True,text=True)
        self.assertEqual(r.returncode,20);self.assertFalse((self.base/'fuera.xlsx').exists())

if __name__=='__main__':unittest.main(verbosity=2)
