"""Que app/static/js/consultorio-validadores.js (ejecutado con JScript de Windows, sin navegador) dé lo MISMO que
app/rutas/modulo_consultorio/validadores_clinicos.py para los mismos casos: el primer error de la ficha (en el orden del servidor) y el IMC.
Uso: .\\.venv\\Scripts\\python.exe -I tests\\consultorio\\comparar_ficha_js_py.py      (necesita cscript; no usa la base de datos)
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from app.rutas.modulo_consultorio.validadores_clinicos import validar_ficha

ORDEN = ['presion_arterial', 'temperatura', 'frecuencia_cardiaca', 'frecuencia_respiratoria', 'peso', 'talla',
         'examen_fisico_general', 'examen_bucal', 'observaciones_medico']
LARGO = 'a' * 2001

CASOS = [
    {},                                                                  # sin ningún dato
    {'temperatura': '', 'peso': '   '},                                  # solo vacíos
    {'observaciones_medico': 'Paciente refiere dolor'},                  # un solo dato de texto
    {'presion_arterial': '120/80'}, {'presion_arterial': '120 / 80'}, {'presion_arterial': '50/30'}, {'presion_arterial': '300/200'},
    {'presion_arterial': '49/30'}, {'presion_arterial': '301/100'}, {'presion_arterial': '120/29'}, {'presion_arterial': '120/201'},
    {'presion_arterial': '80/120'}, {'presion_arterial': '100/100'}, {'presion_arterial': '12/8'}, {'presion_arterial': '1200/80'},
    {'presion_arterial': 'abc'}, {'presion_arterial': '120-80'}, {'presion_arterial': '120/'},
    {'temperatura': '36.5'}, {'temperatura': '36,5'}, {'temperatura': '30'}, {'temperatura': '45'}, {'temperatura': '29.99'},
    {'temperatura': '45.01'}, {'temperatura': '36.555'}, {'temperatura': 'x'}, {'temperatura': '-36'}, {'temperatura': 99},
    {'frecuencia_cardiaca': '72'}, {'frecuencia_cardiaca': '20'}, {'frecuencia_cardiaca': '250'}, {'frecuencia_cardiaca': '19'},
    {'frecuencia_cardiaca': '251'}, {'frecuencia_cardiaca': '72.5'}, {'frecuencia_cardiaca': 'a'}, {'frecuencia_cardiaca': -5},
    {'frecuencia_respiratoria': '16'}, {'frecuencia_respiratoria': '5'}, {'frecuencia_respiratoria': '80'},
    {'frecuencia_respiratoria': '4'}, {'frecuencia_respiratoria': '81'}, {'frecuencia_respiratoria': '16.5'},
    {'peso': '70'}, {'peso': '70.5'}, {'peso': '1'}, {'peso': '500'}, {'peso': '0.99'}, {'peso': '500.01'}, {'peso': '-70'}, {'peso': 'x'},
    {'talla': '175'}, {'talla': '30'}, {'talla': '250'}, {'talla': '29.9'}, {'talla': '250.1'}, {'talla': '1.75'}, {'talla': 'x'},
    {'peso': '70', 'talla': '175'}, {'peso': '70.5', 'talla': '175.5'}, {'peso': '55,5', 'talla': '160'}, {'peso': '100', 'talla': '170'},
    {'peso': '45', 'talla': '150'}, {'peso': '80', 'talla': '180'}, {'peso': '65.2', 'talla': '168'}, {'peso': '70'}, {'talla': '175'},
    {'peso': '70', 'talla': '175', 'imc': '999'},                        # el IMC del navegador se ignora
    {'examen_bucal': LARGO}, {'examen_bucal': LARGO[:2000]}, {'examen_fisico_general': 'raro\x01'}, {'examen_fisico_general': 'dos\nlíneas\ty tab'},
    {'presion_arterial': '120/80', 'temperatura': '50'},                 # el primer error en el orden del servidor
    {'temperatura': '50', 'peso': '1000'}, {'peso': '1000', 'talla': 'x'},
]


def esperado(caso):
    valores, error, campo = validar_ficha(caso)
    if error:
        return error, ''
    return '', '' if valores['imc'] is None else str(valores['imc'])


RUNNER = r"""
var window = this;
var st = new ActiveXObject('ADODB.Stream');
st.Type = 2; st.Charset = 'utf-8'; st.Open();
st.LoadFromFile(WScript.Arguments(0));
var codigo = st.ReadText(); st.Close();
eval(codigo);
var V = window.ConsultorioValidadores;
var ORDEN = %(orden)s;
var CASOS = %(casos)s;
var out = [];
for (var i = 0; i < CASOS.length; i++) {
  var errores = V.ficha(CASOS[i]);
  var primero = '';
  if (errores.ficha) { primero = errores.ficha; }
  else { for (var j = 0; j < ORDEN.length && !primero; j++) { if (errores[ORDEN[j]]) primero = errores[ORDEN[j]]; } }
  var imc = primero ? '' : V.imc(CASOS[i].peso, CASOS[i].talla);
  out.push(i + '\t' + primero + '\t' + imc);
}
var so = new ActiveXObject('ADODB.Stream'); so.Type = 2; so.Charset = 'utf-8'; so.Open();
so.WriteText(out.join('\n')); so.SaveToFile(WScript.Arguments(1), 2); so.Close();
"""

with tempfile.TemporaryDirectory() as tmp:
    runner = pathlib.Path(tmp) / 'runner.js'
    salida = pathlib.Path(tmp) / 'salida.txt'
    runner.write_text(RUNNER % {'orden': json.dumps(ORDEN), 'casos': json.dumps(CASOS)}, encoding='ascii')
    proc = subprocess.run(['cscript', '//nologo', '//E:jscript', str(runner), str(RAIZ / 'app' / 'static' / 'js' / 'consultorio-validadores.js'),
                           str(salida)], capture_output=True, text=True)
    if proc.returncode != 0 or not salida.exists():
        print('FAIL el runner JScript no corrió:', proc.stdout[-300:], proc.stderr[-300:])
        sys.exit(1)
    filas = [l.split('\t') for l in salida.read_text(encoding='utf-8-sig').split('\n') if l.strip('\r')]

fallos = 0
for fila in filas:
    i = int(fila[0])
    js_error, js_imc = fila[1], (fila[2].rstrip('\r') if len(fila) > 2 else '')
    py_error, py_imc = esperado(CASOS[i])
    ok = (js_error, js_imc) == (py_error, py_imc)
    fallos += (not ok)
    print(('OK  ' if ok else 'DIFF'), json.dumps(CASOS[i], ensure_ascii=False)[:90], '->',
          (py_error or f'IMC {py_imc or "-"}')[:70] if ok else f'JS=({js_error!r}, {js_imc!r}) PY=({py_error!r}, {py_imc!r})')
print('DIFERENCIAS:', fallos, 'de', len(CASOS))
sys.exit(1 if fallos or len(filas) != len(CASOS) else 0)
