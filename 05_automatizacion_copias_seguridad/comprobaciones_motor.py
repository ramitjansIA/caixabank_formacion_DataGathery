from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys,json,subprocess,copy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import copias_seguridad as m
n=0
def rejects(fn,types=(ValueError,OSError,RuntimeError)):
 global n
 try:fn()
 except types:n+=1;return
 raise AssertionError('No se produjo el rechazo esperado')
with TemporaryDirectory() as t:
 b=Path(t);p=m.crear_demo(b/'proyecto con espacios')
 rejects(lambda:m.crear_demo(p));rejects(lambda:m.cargar_proyecto(b))
 for v in ['.','..','a/../b','/tmp/x','C:/x','a\\b','CON','a.','a ','x//y']:
  rejects(lambda v=v:m.ruta_relativa_segura(v))
 for v in [0,-1,True]:rejects(lambda v=v:m.retener_copias(p,v))
 rejects(lambda:m.json_estricto('{"a":1,"a":2}'))
 rejects(lambda:m.json_estricto('{"a":NaN}'))
 with m.bloqueo(p):rejects(lambda:m.crear_copia(p,True))
 r=m.crear_copia(p,True);folder=p/'copias'/r['copia'];mf=json.loads((folder/'manifiesto.json').read_text())
 for mutate in [lambda d:d.update(bytes_totales=0),lambda d:d['archivos'][0].update(ruta='../x'),lambda d:d['archivos'][0].update(sha256='x'*64),lambda d:d.update(extra=1),lambda d:d['archivos'].append(copy.deepcopy(d['archivos'][0]))]:
  d=copy.deepcopy(mf);mutate(d);rejects(lambda d=d:m.validar_manifiesto(d))
 m.restaurar_copia(p,r['copia'],'ensayo',True)
 rejects(lambda:m.restaurar_copia(p,r['copia'],'ensayo',True))
 (folder/'contenido/extra.txt').write_text('x');rejects(lambda:m.verificar_copia(p,r['copia']));(folder/'contenido/extra.txt').unlink()
 try:
  link=p/'origen/enlace';link.symlink_to(p/'origen/vacio.txt');rejects(lambda:m.crear_copia(p,True));link.unlink()
 except NotImplementedError:pass
 p2=m.crear_demo(b/'cambio')
 original=m.copiar_contraste
 def cambiar(o,d,e):
  o.write_bytes(o.read_bytes()+b'!');return original(o,d,e)
 with patch.object(m,'copiar_contraste',cambiar):rejects(lambda:m.crear_copia(p2,True))
 assert not any(m.re.fullmatch(m.PATRON_COPIA,x.name) for x in (p2/'copias').iterdir());n+=1
 assert any(x.name.startswith('.parcial_') for x in (p2/'copias').iterdir());n+=1
 cli=Path(m.__file__).resolve()
 (folder/'contenido/vacio.txt').write_text('alterado')
 cmd=subprocess.run([sys.executable,str(cli),'verificar','--proyecto',str(p),'--copia',r['copia']],capture_output=True,cwd=b)
 assert cmd.returncode==10 and cmd.stderr;n+=1
 rejects(lambda:m.retener_copias(p,1,True))
 p3=m.crear_demo(b/'vacia')
 import shutil
 shutil.rmtree(p3/'origen');(p3/'origen').mkdir();rejects(lambda:m.crear_copia(p3,True))
print(n,'comprobaciones adicionales correctas')
