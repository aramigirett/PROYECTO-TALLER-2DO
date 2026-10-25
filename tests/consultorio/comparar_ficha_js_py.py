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
from app.rutas.modulo_consultorio.validadores_clinicos import validar_diagnostico, validar_ficha, validar_pieza_fdi, validar_superficie

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


# ---- Etapa 4: pieza FDI, superficie y diagnóstico ----
PIEZAS = ['18', 18, '11', '28', '48', '55', '65', '75', '85', '19', '10', '29', '49', '56', '66', '76', '86', '9', '0', '99', 'x', '', None, ' ', '1 8', '018', 1.5, True, '-18', '18.0']
SUPERFICIES = ['O', 'V', 'L', 'M', 'D', 'T', 'o', 't', 'OO', 'X', '', None, 5, ' O ']
ORDEN_DX = ['id_tipo_diagnostico', 'sintomas', 'descripcion_diagnostico', 'pieza_dental', 'observaciones']
DX_BASE = {'id_tipo_diagnostico': 3, 'sintomas': [1, 2], 'descripcion_diagnostico': 'Caries profunda', 'pieza_dental': '18', 'observaciones': 'Control'}
DIAGNOSTICOS = [DX_BASE, {**DX_BASE, 'pieza_dental': None}, {**DX_BASE, 'pieza_dental': ''}, {**DX_BASE, 'observaciones': None}, {**DX_BASE, 'pieza_dental': '19'},
                {**DX_BASE, 'pieza_dental': 55}, {**DX_BASE, 'id_tipo_diagnostico': None}, {**DX_BASE, 'id_tipo_diagnostico': ''}, {**DX_BASE, 'id_tipo_diagnostico': 'x'},
                {**DX_BASE, 'id_tipo_diagnostico': 0}, {**DX_BASE, 'id_tipo_diagnostico': '4'}, {**DX_BASE, 'sintomas': []}, {**DX_BASE, 'sintomas': None},
                {**DX_BASE, 'descripcion_diagnostico': ''}, {**DX_BASE, 'descripcion_diagnostico': '   '}, {**DX_BASE, 'descripcion_diagnostico': 'a' * 1001},
                {**DX_BASE, 'descripcion_diagnostico': 'a' * 1000}, {**DX_BASE, 'descripcion_diagnostico': 'raro'}, {**DX_BASE, 'observaciones': 'b' * 2001},
                {**DX_BASE, 'observaciones': 'b' * 2000}, {**DX_BASE, 'observaciones': 'raro'}, {**DX_BASE, 'id_tipo_diagnostico': None, 'sintomas': []},
                {**DX_BASE, 'sintomas': [], 'pieza_dental': '99'}, {**DX_BASE, 'pieza_dental': '99', 'descripcion_diagnostico': ''}]


def esperado_pieza(v):
    return validar_pieza_fdi(v)[1] or ''


def esperado_superficie(v):
    return validar_superficie(v)[1] or ''


def esperado_dx(caso):
    return validar_diagnostico(caso)[1] or ''


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
var PIEZAS = %(piezas)s;
var SUPERFICIES = %(superficies)s;
var DIAGNOSTICOS = %(dx)s;
var ORDEN_DX = %(orden_dx)s;
var out = [];
for (var i = 0; i < CASOS.length; i++) {
  var errores = V.ficha(CASOS[i]);
  var primero = '';
  if (errores.ficha) { primero = errores.ficha; }
  else { for (var j = 0; j < ORDEN.length && !primero; j++) { if (errores[ORDEN[j]]) primero = errores[ORDEN[j]]; } }
  var imc = primero ? '' : V.imc(CASOS[i].peso, CASOS[i].talla);
  out.push(i + '\t' + primero + '\t' + imc);
}
for (var p = 0; p < PIEZAS.length; p++) out.push('pieza	' + p + '	' + V.piezaFdi(PIEZAS[p], false));
for (var u = 0; u < SUPERFICIES.length; u++) out.push('superficie	' + u + '	' + V.superficie(SUPERFICIES[u]));
for (var d = 0; d < DIAGNOSTICOS.length; d++) {
  var er = V.diagnostico(DIAGNOSTICOS[d]);
  var pri = '';
  for (var k = 0; k < ORDEN_DX.length && !pri; k++) { if (er[ORDEN_DX[k]]) pri = er[ORDEN_DX[k]]; }
  out.push('dx	' + d + '	' + pri);
}
var so = new ActiveXObject('ADODB.Stream'); so.Type = 2; so.Charset = 'utf-8'; so.Open();
so.WriteText(out.join('\n')); so.SaveToFile(WScript.Arguments(1), 2); so.Close();
"""

with tempfile.TemporaryDirectory() as tmp:
    runner = pathlib.Path(tmp) / 'runner.js'
    salida = pathlib.Path(tmp) / 'salida.txt'
    runner.write_text(RUNNER % {'orden': json.dumps(ORDEN), 'casos': json.dumps(CASOS), 'piezas': json.dumps(PIEZAS), 'superficies': json.dumps(SUPERFICIES),
                                'dx': json.dumps(DIAGNOSTICOS), 'orden_dx': json.dumps(ORDEN_DX)}, encoding='ascii')
    proc = subprocess.run(['cscript', '//nologo', '//E:jscript', str(runner), str(RAIZ / 'app' / 'static' / 'js' / 'consultorio-validadores.js'),
                           str(salida)], capture_output=True, text=True)
    if proc.returncode != 0 or not salida.exists():
        print('FAIL el runner JScript no corrió:', proc.stdout[-300:], proc.stderr[-300:])
        sys.exit(1)
    filas = [l.split('\t') for l in salida.read_text(encoding='utf-8-sig').split('\n') if l.strip('\r')]

fallos = 0
total = 0
for fila in filas:
    tipo = fila[0] if not fila[0].isdigit() else 'ficha'
    if tipo == 'ficha':
        i = int(fila[0])
        js_error, js_imc = fila[1], (fila[2].rstrip('\r') if len(fila) > 2 else '')
        py_error, py_imc = esperado(CASOS[i])
        ok = (js_error, js_imc) == (py_error, py_imc)
        etiqueta = json.dumps(CASOS[i], ensure_ascii=False)[:90]
        esp = (py_error or f'IMC {py_imc or "-"}')[:70]
        dif = f'JS=({js_error!r}, {js_imc!r}) PY=({py_error!r}, {py_imc!r})'
    else:
        i = int(fila[1])
        js_error = fila[2].rstrip('\r') if len(fila) > 2 else ''
        py_error = {'pieza': lambda: esperado_pieza(PIEZAS[i]), 'superficie': lambda: esperado_superficie(SUPERFICIES[i]), 'dx': lambda: esperado_dx(DIAGNOSTICOS[i])}[tipo]()
        ok = js_error == py_error
        etiqueta = tipo + ' ' + json.dumps({'pieza': PIEZAS, 'superficie': SUPERFICIES, 'dx': DIAGNOSTICOS}[tipo][i], ensure_ascii=False)[:80]
        esp = (py_error or 'válido')[:70]
        dif = f'JS={js_error!r} PY={py_error!r}'
    total += 1
    fallos += (not ok)
    print(('OK  ' if ok else 'DIFF'), etiqueta, '->', esp if ok else dif)
print('DIFERENCIAS:', fallos, 'de', total)
sys.exit(1 if fallos or total != len(CASOS) + len(PIEZAS) + len(SUPERFICIES) + len(DIAGNOSTICOS) else 0)
