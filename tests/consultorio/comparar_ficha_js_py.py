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
from app.rutas.modulo_consultorio.validadores_clinicos import (validar_diagnostico, validar_ficha, validar_pieza_fdi, validar_sesion, validar_superficie,
                                                               validar_tratamiento, validar_receta, validar_orden_estudio, validar_orden_analisis)

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


# ---- Etapa 5: tratamiento y sesión (con "hoy" fijo para que JS y Python comparen lo mismo) ----
HOY = '2026-10-25'
ORDEN_TR = ['id_tipo_tratamiento', 'descripcion_tratamiento', 'fecha_tratamiento', 'id_diagnostico']
TR_BASE = {'id_tipo_tratamiento': 3, 'descripcion_tratamiento': 'Limpieza completa', 'fecha_tratamiento': '2026-10-25', 'id_diagnostico': 7}
TRATAMIENTOS = [TR_BASE, {**TR_BASE, 'fecha_tratamiento': None}, {**TR_BASE, 'fecha_tratamiento': ''}, {**TR_BASE, 'id_diagnostico': None}, {**TR_BASE, 'id_diagnostico': ''},
                {**TR_BASE, 'id_diagnostico': 'x'}, {**TR_BASE, 'id_diagnostico': 0}, {**TR_BASE, 'id_diagnostico': '8'}, {**TR_BASE, 'id_tipo_tratamiento': None},
                {**TR_BASE, 'id_tipo_tratamiento': ''}, {**TR_BASE, 'id_tipo_tratamiento': 'x'}, {**TR_BASE, 'id_tipo_tratamiento': 0}, {**TR_BASE, 'id_tipo_tratamiento': '5'},
                {**TR_BASE, 'descripcion_tratamiento': ''}, {**TR_BASE, 'descripcion_tratamiento': '  '}, {**TR_BASE, 'descripcion_tratamiento': 'a' * 1001},
                {**TR_BASE, 'descripcion_tratamiento': 'a' * 1000}, {**TR_BASE, 'descripcion_tratamiento': 'raro'}, {**TR_BASE, 'descripcion_tratamiento': 5},
                {**TR_BASE, 'fecha_tratamiento': '2026-10-26'}, {**TR_BASE, 'fecha_tratamiento': '2026-10-24'}, {**TR_BASE, 'fecha_tratamiento': '2026-02-30'},
                {**TR_BASE, 'fecha_tratamiento': '2026-13-01'}, {**TR_BASE, 'fecha_tratamiento': '25/10/2026'}, {**TR_BASE, 'fecha_tratamiento': '20261024'},
                {**TR_BASE, 'fecha_tratamiento': 'hoy'}, {**TR_BASE, 'fecha_tratamiento': ' 2026-10-25 '}, {**TR_BASE, 'fecha_tratamiento': '2024-02-29'},
                {**TR_BASE, 'fecha_tratamiento': '2025-02-29'}, {**TR_BASE, 'id_tipo_tratamiento': None, 'descripcion_tratamiento': ''},
                {**TR_BASE, 'descripcion_tratamiento': '', 'fecha_tratamiento': '2027-01-01'}, {**TR_BASE, 'id_tipo_tratamiento': True}]
ORDEN_SE = ['procedimientos', 'descripcion_procedimiento', 'observaciones', 'proxima_cita', 'insumos']
SE_BASE = {'procedimientos': [1, 2], 'descripcion_procedimiento': 'Se limpió la pieza 18', 'observaciones': 'Sin complicaciones', 'proxima_cita': '2026-11-02',
           'insumos': [{'id_insumo': 4, 'cantidad': 2}, {'id_insumo': 5, 'cantidad': '10'}]}
SESIONES = [SE_BASE, {**SE_BASE, 'insumos': []}, {**SE_BASE, 'insumos': None}, {**SE_BASE, 'observaciones': None}, {**SE_BASE, 'proxima_cita': None}, {**SE_BASE, 'proxima_cita': ''},
            {**SE_BASE, 'proxima_cita': '2026-10-25'}, {**SE_BASE, 'proxima_cita': '2026-10-24'}, {**SE_BASE, 'proxima_cita': '2026-02-30'}, {**SE_BASE, 'proxima_cita': 'x'},
            {**SE_BASE, 'procedimientos': []}, {**SE_BASE, 'procedimientos': None}, {**SE_BASE, 'procedimientos': ['x']}, {**SE_BASE, 'procedimientos': [0]},
            {**SE_BASE, 'procedimientos': [3, 3]}, {**SE_BASE, 'procedimientos': ['2']},
            {**SE_BASE, 'descripcion_procedimiento': ''}, {**SE_BASE, 'descripcion_procedimiento': '  '}, {**SE_BASE, 'descripcion_procedimiento': 'a' * 1001},
            {**SE_BASE, 'descripcion_procedimiento': 'a' * 1000}, {**SE_BASE, 'descripcion_procedimiento': 'raro'},
            {**SE_BASE, 'observaciones': 'b' * 2001}, {**SE_BASE, 'observaciones': 'b' * 2000}, {**SE_BASE, 'observaciones': 'raro'},
            {**SE_BASE, 'insumos': [{'id_insumo': 4, 'cantidad': 0}]}, {**SE_BASE, 'insumos': [{'id_insumo': 4, 'cantidad': 1000}]},
            {**SE_BASE, 'insumos': [{'id_insumo': 4, 'cantidad': 999}]}, {**SE_BASE, 'insumos': [{'id_insumo': 4, 'cantidad': 1}]},
            {**SE_BASE, 'insumos': [{'id_insumo': 4, 'cantidad': 'x'}]}, {**SE_BASE, 'insumos': [{'id_insumo': 4, 'cantidad': ''}]},
            {**SE_BASE, 'insumos': [{'id_insumo': 4, 'cantidad': None}]}, {**SE_BASE, 'insumos': [{'id_insumo': 4}]}, {**SE_BASE, 'insumos': [{'cantidad': 2}]},
            {**SE_BASE, 'insumos': [{'id_insumo': 0, 'cantidad': 2}]}, {**SE_BASE, 'insumos': [{'id_insumo': 'x', 'cantidad': 2}]}, {**SE_BASE, 'insumos': ['x']},
            {**SE_BASE, 'insumos': [{'id_insumo': 4, 'cantidad': 2}, {'id_insumo': '4', 'cantidad': 3}]}, {**SE_BASE, 'insumos': 'x'},
            {**SE_BASE, 'procedimientos': [], 'descripcion_procedimiento': ''}, {**SE_BASE, 'descripcion_procedimiento': '', 'proxima_cita': '2020-01-01'},
            {**SE_BASE, 'insumos': [{'id_insumo': 4, 'cantidad': 1000}], 'proxima_cita': 'x'}]


# ---- Etapa 6: receta y órdenes ----
ORDEN_RE = ['indicaciones_generales', 'medicamentos', 'id_diagnostico', 'id_tratamiento']
MED = {'id_medicamento': 3, 'dosis': '500 mg', 'frecuencia': 'cada 8 horas', 'duracion': '7 días'}
RE_BASE = {'indicaciones_generales': 'Tomar con comida', 'medicamentos': [MED, {**MED, 'id_medicamento': '4'}], 'id_diagnostico': 7, 'id_tratamiento': None}
RECETAS = [RE_BASE, {**RE_BASE, 'id_diagnostico': None}, {**RE_BASE, 'id_tratamiento': 9}, {**RE_BASE, 'id_tratamiento': 'x'}, {**RE_BASE, 'id_diagnostico': 0},
           {**RE_BASE, 'id_diagnostico': ''}, {**RE_BASE, 'indicaciones_generales': ''}, {**RE_BASE, 'indicaciones_generales': '  '}, {**RE_BASE, 'indicaciones_generales': 'a' * 2001},
           {**RE_BASE, 'indicaciones_generales': 'a' * 2000}, {**RE_BASE, 'indicaciones_generales': 'raro'}, {**RE_BASE, 'indicaciones_generales': 5},
           {**RE_BASE, 'medicamentos': []}, {**RE_BASE, 'medicamentos': None}, {**RE_BASE, 'medicamentos': 'x'}, {**RE_BASE, 'medicamentos': ['x']},
           {**RE_BASE, 'medicamentos': [{**MED, 'id_medicamento': 0}]}, {**RE_BASE, 'medicamentos': [{**MED, 'id_medicamento': None}]},
           {**RE_BASE, 'medicamentos': [{**MED, 'dosis': ''}]}, {**RE_BASE, 'medicamentos': [{**MED, 'frecuencia': '  '}]}, {**RE_BASE, 'medicamentos': [{**MED, 'duracion': None}]},
           {**RE_BASE, 'medicamentos': [{**MED, 'dosis': 'a' * 101}]}, {**RE_BASE, 'medicamentos': [{**MED, 'dosis': 'a' * 100}]}, {**RE_BASE, 'medicamentos': [{**MED, 'duracion': 'raro'}]},
           {**RE_BASE, 'medicamentos': [{**MED, 'dosis': 5}]}, {**RE_BASE, 'medicamentos': [MED, MED]}, {**RE_BASE, 'medicamentos': [MED, {**MED, 'id_medicamento': '3'}]},
           {**RE_BASE, 'medicamentos': [{**MED, 'dosis': ''}, MED, MED]}, {**RE_BASE, 'indicaciones_generales': '', 'medicamentos': []},
           {**RE_BASE, 'medicamentos': [], 'id_diagnostico': 'x'}, {**RE_BASE, 'id_diagnostico': 'x', 'id_tratamiento': 'y'}]
ORDEN_OR = ['id_tipo', 'motivo_orden', 'indicaciones', 'id_diagnostico', 'id_tratamiento']
OR_BASE = {'id_tipo': 3, 'motivo_orden': 'Control radiográfico', 'indicaciones': 'En ayunas', 'id_diagnostico': 7, 'id_tratamiento': None}
ORDENES = [OR_BASE, {**OR_BASE, 'id_diagnostico': None}, {**OR_BASE, 'id_tratamiento': 9}, {**OR_BASE, 'id_tratamiento': 'x'}, {**OR_BASE, 'id_diagnostico': 0},
           {**OR_BASE, 'id_tipo': None}, {**OR_BASE, 'id_tipo': ''}, {**OR_BASE, 'id_tipo': 'x'}, {**OR_BASE, 'id_tipo': 0}, {**OR_BASE, 'id_tipo': '5'}, {**OR_BASE, 'id_tipo': True},
           {**OR_BASE, 'motivo_orden': ''}, {**OR_BASE, 'motivo_orden': '  '}, {**OR_BASE, 'motivo_orden': 'a' * 1001}, {**OR_BASE, 'motivo_orden': 'a' * 1000},
           {**OR_BASE, 'motivo_orden': 'raro'}, {**OR_BASE, 'motivo_orden': 5}, {**OR_BASE, 'indicaciones': None}, {**OR_BASE, 'indicaciones': ''},
           {**OR_BASE, 'indicaciones': 'b' * 2001}, {**OR_BASE, 'indicaciones': 'b' * 2000}, {**OR_BASE, 'indicaciones': 'raro'}, {**OR_BASE, 'indicaciones': 5},
           {**OR_BASE, 'id_tipo': None, 'motivo_orden': ''}, {**OR_BASE, 'motivo_orden': '', 'indicaciones': 'raro'}, {**OR_BASE, 'indicaciones': 'raro', 'id_diagnostico': 'x'}]


def _con_tipo(caso, campo):
    return {(campo if k == 'id_tipo' else k): v for k, v in caso.items()}


def esperado_re(caso):
    return validar_receta(caso)[1] or ''


def esperado_oe(caso):
    return validar_orden_estudio(_con_tipo(caso, 'id_tipo_estudio'))[1] or ''


def esperado_oa(caso):
    return validar_orden_analisis(_con_tipo(caso, 'id_tipo_analisis'))[1] or ''


def esperado_tr(caso):
    return validar_tratamiento(caso, HOY)[1] or ''


def esperado_se(caso):
    return validar_sesion(caso, HOY)[1] or ''


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
var HOY = %(hoy)s;
var TRATAMIENTOS = %(tr)s;
var ORDEN_TR = %(orden_tr)s;
var SESIONES = %(se)s;
var ORDEN_SE = %(orden_se)s;
var RECETAS = %(re)s;
var ORDEN_RE = %(orden_re)s;
var ORDENES = %(ord)s;
var ORDEN_OR = %(orden_or)s;
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
for (var t = 0; t < TRATAMIENTOS.length; t++) {
  var et = V.tratamiento(TRATAMIENTOS[t], HOY);
  var prt = '';
  for (var kt = 0; kt < ORDEN_TR.length && !prt; kt++) { if (et[ORDEN_TR[kt]]) prt = et[ORDEN_TR[kt]]; }
  out.push('tr	' + t + '	' + prt);
}
for (var q = 0; q < SESIONES.length; q++) {
  var es = V.sesion(SESIONES[q], HOY);
  var prs = '';
  for (var ks = 0; ks < ORDEN_SE.length && !prs; ks++) { if (es[ORDEN_SE[ks]]) prs = es[ORDEN_SE[ks]]; }
  out.push('se	' + q + '	' + prs);
}
var conTipo = function (o, campo) { var c = {}; for (var k in o) { if (o.hasOwnProperty(k)) c[k === 'id_tipo' ? campo : k] = o[k]; } return c; };
for (var a = 0; a < RECETAS.length; a++) {
  var er2 = V.receta(RECETAS[a]);
  var p2 = '';
  for (var k2 = 0; k2 < ORDEN_RE.length && !p2; k2++) { if (er2[ORDEN_RE[k2]]) p2 = er2[ORDEN_RE[k2]]; }
  out.push('re	' + a + '	' + p2);
}
for (var b = 0; b < ORDENES.length; b++) {
  var ee = V.ordenEstudio(conTipo(ORDENES[b], 'id_tipo_estudio')), ea = V.ordenAnalisis(conTipo(ORDENES[b], 'id_tipo_analisis'));
  var pe = '', pa = '';
  for (var k3 = 0; k3 < ORDEN_OR.length; k3++) {
    var cn = ORDEN_OR[k3];
    if (!pe && ee[cn === 'id_tipo' ? 'id_tipo_estudio' : cn]) pe = ee[cn === 'id_tipo' ? 'id_tipo_estudio' : cn];
    if (!pa && ea[cn === 'id_tipo' ? 'id_tipo_analisis' : cn]) pa = ea[cn === 'id_tipo' ? 'id_tipo_analisis' : cn];
  }
  out.push('oe	' + b + '	' + pe);
  out.push('oa	' + b + '	' + pa);
}
var so = new ActiveXObject('ADODB.Stream'); so.Type = 2; so.Charset = 'utf-8'; so.Open();
so.WriteText(out.join('\n')); so.SaveToFile(WScript.Arguments(1), 2); so.Close();
"""

with tempfile.TemporaryDirectory() as tmp:
    runner = pathlib.Path(tmp) / 'runner.js'
    salida = pathlib.Path(tmp) / 'salida.txt'
    runner.write_text(RUNNER % {'orden': json.dumps(ORDEN), 'casos': json.dumps(CASOS), 'piezas': json.dumps(PIEZAS), 'superficies': json.dumps(SUPERFICIES),
                                'dx': json.dumps(DIAGNOSTICOS), 'orden_dx': json.dumps(ORDEN_DX), 'hoy': json.dumps(HOY), 'tr': json.dumps(TRATAMIENTOS),
                                'orden_tr': json.dumps(ORDEN_TR), 'se': json.dumps(SESIONES), 'orden_se': json.dumps(ORDEN_SE),
                                're': json.dumps(RECETAS), 'orden_re': json.dumps(ORDEN_RE), 'ord': json.dumps(ORDENES), 'orden_or': json.dumps(ORDEN_OR)}, encoding='ascii')
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
        py_error = {'pieza': lambda: esperado_pieza(PIEZAS[i]), 'superficie': lambda: esperado_superficie(SUPERFICIES[i]), 'dx': lambda: esperado_dx(DIAGNOSTICOS[i]), 'tr': lambda: esperado_tr(TRATAMIENTOS[i]),
                    'se': lambda: esperado_se(SESIONES[i]), 're': lambda: esperado_re(RECETAS[i]),
                    'oe': lambda: esperado_oe(ORDENES[i]), 'oa': lambda: esperado_oa(ORDENES[i])}[tipo]()
        ok = js_error == py_error
        etiqueta = tipo + ' ' + json.dumps({'pieza': PIEZAS, 'superficie': SUPERFICIES, 'dx': DIAGNOSTICOS, 'tr': TRATAMIENTOS, 'se': SESIONES, 're': RECETAS, 'oe': ORDENES, 'oa': ORDENES}[tipo][i], ensure_ascii=False)[:80]
        esp = (py_error or 'válido')[:70]
        dif = f'JS={js_error!r} PY={py_error!r}'
    total += 1
    fallos += (not ok)
    print(('OK  ' if ok else 'DIFF'), etiqueta, '->', esp if ok else dif)
print('DIFERENCIAS:', fallos, 'de', total)
sys.exit(1 if fallos or total != len(CASOS) + len(PIEZAS) + len(SUPERFICIES) + len(DIAGNOSTICOS) + len(TRATAMIENTOS) + len(SESIONES) + len(RECETAS) + 2 * len(ORDENES) else 0)
