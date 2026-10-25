"""Gestionar Diagnóstico y Gestionar Odontograma (visual por piezas FDI) en un navegador real (Edge headless) con fetch simulado.
Cada vista se renderiza con Flask (sesión de Administrador: todos los permisos del catálogo) pasando `es_medico` como lo haría la ruta, se reescribe /static a
file:// y se corre un script que usa el DOM, el SVG, Bootstrap 5 y SweetAlert2 reales. El JSON simulado trae las claves ORDENADAS como Flask y las URL
pedidas no pueden llevar ids no numéricos.
Uso: .\\.venv\\Scripts\\python.exe -I tests\\consultorio\\browser_diag_odontograma.py <carpeta de salida>      (necesita Edge)
"""
import html as _h
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1].parent))
from app import app
from flask import render_template, session

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SALIDA = pathlib.Path(sys.argv[1])
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
STATIC = (RAIZ / 'app' / 'static').as_uri() + '/'
SALIDA.mkdir(parents=True, exist_ok=True)


def ordenado(d):
    return {k: d[k] for k in sorted(d)}


def consulta(estado='en_proceso'):
    return ordenado({'id_consulta_cab': 17, 'numero': 'CON-0000017', 'estado': estado, 'activo': True, 'id_paciente': 7, 'nombre_paciente': 'JAVIER ACOSTA',
                     'cedula_paciente': '5098745', 'id_medico': 20, 'nombre_medico': 'OSCAR GONZALES', 'fecha_cita': '2026-10-26', 'hora_cita': '09:00:00'})


def resumen(estado, cargar):
    return {'consulta': consulta(estado), 'contadores': {}, 'acciones': {'iniciar': False, 'finalizar': False, 'cancelar': False, 'cargar_clinico': cargar}}


ESTADOS = [ordenado(e) for e in (
    {'id_estado_dental': 2, 'descripcion': 'Caries', 'color': '#D32F2F', 'simbolo': 'Ca', 'aplica_a': 'SUPERFICIE'},
    {'id_estado_dental': 3, 'descripcion': 'Obturación', 'color': '#757575', 'simbolo': 'Ob', 'aplica_a': 'SUPERFICIE'},
    {'id_estado_dental': 7, 'descripcion': 'Corona', 'color': '#FDD835', 'simbolo': 'Co', 'aplica_a': 'PIEZA'},
    {'id_estado_dental': 5, 'descripcion': 'Extraído', 'color': '#212121', 'simbolo': 'Ex', 'aplica_a': 'PIEZA'})]


def hallazgo(i, pieza, sup, estado, obs=None):
    e = next(x for x in ESTADOS if x['id_estado_dental'] == estado)
    return ordenado({'id_odontograma_detalle': i, 'id_odontograma': 40, 'numero_diente': pieza, 'superficie': sup, 'id_estado_dental': estado,
                     'estado_descripcion': e['descripcion'], 'estado_color': e['color'], 'estado_simbolo': e['simbolo'], 'aplica_a': e['aplica_a'], 'observacion': obs})


HALLAZGOS = [hallazgo(501, 18, 'O', 2, 'sensible'), hallazgo(502, 18, 'M', 3), hallazgo(503, 11, 'T', 7), hallazgo(504, 36, 'T', 5)]


def odontograma(hallazgos=None):
    return ordenado({'id_odontograma': 40, 'id_consulta_cab': 17, 'numero_consulta': 'CON-0000017', 'id_paciente': 7, 'nombre_paciente': 'JAVIER ACOSTA',
                     'cedula_paciente': '5098745', 'id_medico': 20, 'nombre_medico': 'OSCAR GONZALES', 'activo': True, 'estado_consulta': 'en_proceso',
                     'hallazgos': HALLAZGOS if hallazgos is None else hallazgos})


def dx(i, codigo, pieza, estado='en_proceso'):
    return ordenado({'id_diagnostico': i, 'codigo': codigo, 'id_consulta_cab': 17, 'numero_consulta': 'CON-0000017', 'estado_consulta': estado,
                     'id_paciente': 7, 'nombre_paciente': 'JAVIER ACOSTA', 'cedula_paciente': '5098745', 'id_medico': 20, 'nombre_medico': 'OSCAR GONZALES',
                     'id_tipo_diagnostico': 3, 'tipo_diagnostico': 'CARIES DENTAL', 'categoria_tipo': 'PATOLOGÍA', 'descripcion_diagnostico': 'Caries profunda en la 18',
                     'pieza_dental': pieza, 'fecha_diagnostico': '2026-10-26', 'observaciones': 'Control en 7 días', 'fecha_registro': '2026-10-26T09:30:00', 'activo': True,
                     'sintomas': [{'id_sintoma': 1, 'descripcion_sintoma': 'DOLOR AL MASTICAR'}, {'id_sintoma': 2, 'descripcion_sintoma': 'SENSIBILIDAD'}]})


DXS = [dx(31, 'DX-0031', '18'), dx(32, 'DX-0032', None), dx(33, 'DX-0033', '55', 'finalizada')]
TIPOS = [ordenado({'id_tipo_diagnostico': 3, 'descripcion_diagnostico': 'CARIES DENTAL', 'tipo_diagnostico': 'PATOLOGÍA', 'activo': True}),
         ordenado({'id_tipo_diagnostico': 4, 'descripcion_diagnostico': 'GINGIVITIS', 'tipo_diagnostico': 'PERIODONTAL', 'activo': True})]
SINTOMAS = [ordenado({'id_sintoma': 1, 'descripcion_sintoma': 'DOLOR AL MASTICAR', 'activo': True}), ordenado({'id_sintoma': 2, 'descripcion_sintoma': 'SENSIBILIDAD', 'activo': True}),
            ordenado({'id_sintoma': 3, 'descripcion_sintoma': 'SANGRADO DE ENCÍAS', 'activo': True})]
OD_LISTA = [ordenado({'id_odontograma': 40, 'id_consulta_cab': 17, 'numero_consulta': 'CON-0000017', 'estado_consulta': 'en_proceso', 'fecha_consulta': '2026-10-26',
                      'nombre_paciente': 'JAVIER ACOSTA', 'cedula_paciente': '5098745', 'nombre_medico': 'OSCAR GONZALES', 'cantidad_hallazgos': 4, 'activo': True}),
            ordenado({'id_odontograma': 41, 'id_consulta_cab': 18, 'numero_consulta': 'CON-0000018', 'estado_consulta': 'finalizada', 'fecha_consulta': '2026-10-20',
                      'nombre_paciente': 'ANA PEREZ', 'cedula_paciente': '1234567', 'nombre_medico': 'OSCAR GONZALES', 'cantidad_hallazgos': 0, 'activo': True})]

ESCENARIOS = {
    'dx_listado_medico': dict(plantilla='diagnostico-index.html', es_medico=True, consulta=None, lista=DXS, total=31),
    'dx_consulta': dict(plantilla='diagnostico-index.html', es_medico=True, consulta=17, resumen=resumen('en_proceso', True), lista=DXS[:2]),
    'dx_consulta_rechazo': dict(plantilla='diagnostico-index.html', es_medico=True, consulta=17, resumen=resumen('en_proceso', True), lista=DXS[:2],
                                rechazo={'campo': 'id_tipo_diagnostico', 'error': 'El tipo de diagnóstico seleccionado está inactivo.'}),
    'dx_lectura': dict(plantilla='diagnostico-index.html', es_medico=False, consulta=17, resumen=resumen('finalizada', False), lista=DXS),
    'odo_listado': dict(plantilla='odontograma-index.html', es_medico=True, consulta=None, lista=OD_LISTA, total=2),
    'odo_sin': dict(plantilla='odontograma-index.html', es_medico=True, consulta=17, resumen=resumen('programada', True), odontograma=None, despues=odontograma([])),
    'odo_editor': dict(plantilla='odontograma-index.html', es_medico=True, consulta=17, resumen=resumen('en_proceso', True), odontograma=odontograma(),
                       rechazo={'campo': 'id_estado_dental', 'error': 'Ese hallazgo ya está registrado en el odontograma (misma pieza, superficie y estado).'}),
    'odo_lectura': dict(plantilla='odontograma-index.html', es_medico=False, consulta=17, resumen=resumen('finalizada', False), odontograma=odontograma()),
}

MOCK = r"""
<script>
window.__ESC = %(esc)s;
window.__calls = []; window.__errores = []; window.__creado = false;
window.addEventListener('error', function (e) { window.__errores.push(String(e.message)); });
window.addEventListener('unhandledrejection', function (e) { window.__errores.push('promesa: ' + String(e.reason)); });
window.fetch = function (url, opts) {
  var metodo = (opts && opts.method) || 'GET';
  url = String(url);
  window.__calls.push({url: url, method: metodo, body: opts && opts.body ? String(opts.body) : null});
  var E = window.__ESC, status = 200;
  var cuerpo = {success: true, data: null, error: null, mensaje: 'Operación simulada.'};
  var path = url.split('?')[0];
  if (metodo === 'GET') {
    if (/\/api\/v1\/consultas\/\d+\/resumen$/.test(path)) cuerpo.data = E.resumen;
    else if (/\/api\/v1\/estados-dentales$/.test(path)) cuerpo.data = %(estados)s;
    else if (/\/api\/v1\/odontogramas\/consulta\/\d+$/.test(path)) cuerpo.data = (window.__creado && E.despues) ? E.despues : E.odontograma;
    else if (/\/api\/v1\/odontogramas$/.test(path)) { cuerpo.data = E.lista; cuerpo.total = E.total || E.lista.length; }
    else if (/\/api\/v1\/diagnosticos-medicos\/consulta\/\d+$/.test(path)) cuerpo.data = E.lista;
    else if (/\/api\/v1\/diagnosticos-medicos\/\d+$/.test(path)) cuerpo.data = %(dx_detalle)s;
    else if (/\/api\/v1\/diagnosticos-medicos$/.test(path)) { cuerpo.data = E.lista; cuerpo.total = E.total || E.lista.length; }
    else if (/\/api\/v1\/diagnosticos$/.test(path)) cuerpo.data = %(tipos)s;
    else if (/\/api\/v1\/sintomas$/.test(path)) cuerpo.data = %(sintomas)s;
  } else if (metodo === 'POST') {
    if (E.rechazo && /\/(hallazgos|diagnosticos-medicos)$/.test(path)) { cuerpo = {success: false, data: null, error: E.rechazo.error, campo: E.rechazo.campo}; status = 409; }
    else if (/\/api\/v1\/odontogramas$/.test(path)) { window.__creado = true; cuerpo.data = {id_odontograma: 40, precargado_de: null}; cuerpo.mensaje = 'Odontograma de la consulta CON-0000017 creado correctamente.'; status = 201; }
    else if (/\/hallazgos$/.test(path)) { cuerpo.data = {id_odontograma_detalle: 99}; status = 201; }
    else if (/\/diagnosticos-medicos$/.test(path)) { cuerpo.data = {id_diagnostico: 77, codigo: 'DX-0077'}; cuerpo.mensaje = 'Diagnóstico DX-0077 registrado correctamente.'; status = 201; }
  }
  return Promise.resolve({ok: status < 400, status: status, json: function () { return Promise.resolve(cuerpo); }});
};
</script>
"""

COMUN = r"""
  var r = {}; var esperar = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };
  var llamadas = function (m, re) { return window.__calls.filter(function (c) { return c.method === m && re.test(c.url); }); };
  var $ = function (id) { return document.getElementById(id); };
  var visible = function (id) { var e = $(id); return !!e && e.style.display !== 'none' && e.offsetParent !== null; };
  var txt = function (id) { return ($(id).textContent || '').trim(); };
  var escribir = function (id, v) { var e = $(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); };
  var cerrarSwal = async function () { var c = document.querySelector('.swal2-confirm'); if (c) c.click(); await esperar(400); };
  var sinIdsRaros = function () { return window.__calls.every(function (c) { return !/\/api\/v1\/[a-z-]+\/(true|false|null|undefined)(\/|$)/.test(c.url) && !/\/hallazgos\/(true|false|null|undefined)$/.test(c.url); }); };
"""

PRUEBAS = {}

PRUEBAS['dx_listado_medico'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  var filas = Array.prototype.slice.call($('tbodyGlobal').querySelectorAll('tr'));
  r.tres_filas = filas.length === 3;
  r.fila_con_codigo_paciente_consulta_tipo_y_pieza = /DX-0031/.test(filas[0].textContent) && /JAVIER ACOSTA/.test(filas[0].textContent) && /CI 5098745/.test(filas[0].textContent) && /CON-0000017/.test(filas[0].textContent) && /CARIES DENTAL/.test(filas[0].textContent);
  r.pieza_o_guion = filas[0].querySelectorAll('td')[6].textContent.trim() === '18' && filas[1].querySelectorAll('td')[6].textContent.trim() === '—';
  r.enlace_a_la_consulta_con_id_numerico = filas[0].querySelector('a').getAttribute('href') === '/referenciales/consulta/consulta-detalle/17';
  r.anular_solo_en_consultas_abiertas = !!filas[0].querySelector('[data-accion="anular"]') && !!filas[1].querySelector('[data-accion="anular"]') && !filas[2].querySelector('[data-accion="anular"]');
  r.sin_boton_nuevo_fuera_de_la_consulta = !visible('btnNuevo');
  r.info_paginacion = /Mostrando 1–15 de 31/.test(txt('infoPagina'));
  var fq = $('filtroQ'); fq.value = 'DX-0031'; fq.dispatchEvent(new Event('input', {bubbles: true})); await esperar(700);
  r.filtro_con_espera = llamadas('GET', /q=DX-0031/).length === 1;
  $('btnLimpiar').click(); await esperar(400);
  filas = Array.prototype.slice.call($('tbodyGlobal').querySelectorAll('tr'));   // el listado se volvió a pintar
  filas[0].querySelector('[data-accion="ver"]').click(); await esperar(600);
  var m = $('modalVer');
  r.ver_abre_con_todo_el_diagnostico = m.classList.contains('show') && /Diagnóstico DX-0031/.test(txt('verTitulo')) && /DOLOR AL MASTICAR/.test(txt('verCuerpo')) && /SENSIBILIDAD/.test(txt('verCuerpo'))
    && /Caries profunda/.test(txt('verCuerpo')) && /Control en 7 días/.test(txt('verCuerpo')) && /PATOLOGÍA/.test(txt('verCuerpo'));
  r.ver_pidio_el_id_numerico = llamadas('GET', /\/api\/v1\/diagnosticos-medicos\/31$/).length === 1;
  m.querySelector('[data-bs-dismiss="modal"]').click(); await esperar(600);
  $('tbodyGlobal').querySelectorAll('tr')[0].querySelector('[data-accion="anular"]').click(); await esperar(400);
  r.anular_pide_confirmacion = !!document.querySelector('.swal2-popup') && /Anular este diagnóstico/.test(document.querySelector('.swal2-popup').textContent) && /DX-0031/.test(document.querySelector('.swal2-popup').textContent) && llamadas('DELETE', /./).length === 0;
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.anular_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/diagnosticos-medicos\/31$/).length === 1;
  await cerrarSwal();
"""

_ALTA_DX = r"""
  var fb = function (id) { return $(id).parentElement.querySelector('.invalid-feedback').textContent; };
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.tarjeta_de_la_consulta = visible('tarjetaConsulta') && txt('cNumero') === 'CON-0000017' && /JAVIER ACOSTA/.test(txt('cDetalle')) && /En proceso/.test(txt('cBadge'));
  r.volver_a_la_consulta = visible('btnVolverConsulta') && $('btnVolverConsulta').getAttribute('href') === '/referenciales/consulta/consulta-detalle/17';
  r.diagnosticos_de_la_consulta = $('tbodyConsulta').querySelectorAll('tr').length === 2 && /DX-0031/.test($('tbodyConsulta').textContent) && /DOLOR AL MASTICAR/.test($('tbodyConsulta').textContent);
  r.pidio_la_resumen_y_el_lookup = llamadas('GET', /\/consultas\/17\/resumen$/).length === 1 && llamadas('GET', /diagnosticos-medicos\/consulta\/17$/).length >= 1;
  r.boton_nuevo_visible = visible('btnNuevo');
  $('btnNuevo').click(); await esperar(900);
  var modal = $('modalNuevo');
  r.modal_abre_y_carga_tipos_y_sintomas = modal.classList.contains('show') && $('selTipo').options.length === 3 && $('listaSintomas').querySelectorAll('input[type=checkbox]').length === 3;
  r.selector_de_piezas_fdi = $('selPieza').querySelectorAll('optgroup').length === 8 && $('selPieza').querySelectorAll('option').length === 1 + 32 + 20 && !!$('selPieza').querySelector('option[value="18"]') && !!$('selPieza').querySelector('option[value="85"]') && !$('selPieza').querySelector('option[value="19"]');
  // vacío
  $('formDx').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true})); await esperar(300);
  r.vacio_no_envia = llamadas('POST', /./).length === 0;
  r.vacio_marca_tipo_sintomas_y_descripcion = $('selTipo').classList.contains('is-invalid') && /obligatorio/.test(fb('selTipo')) && visible('errSintomas') && /al menos un síntoma/.test(txt('errSintomas'))
    && $('txtDescripcion').classList.contains('is-invalid') && /obligatoria/.test(fb('txtDescripcion'));
  // buscador de síntomas
  escribir('txtBuscarSintoma', 'sang'); r.buscador_filtra = $('listaSintomas').querySelectorAll('input[type=checkbox]').length === 1;
  escribir('txtBuscarSintoma', '');
  var cbs = $('listaSintomas').querySelectorAll('input[type=checkbox]');
  cbs[0].checked = true; cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
  cbs[1].checked = true; cbs[1].dispatchEvent(new Event('change', {bubbles: true}));
  r.contador_de_sintomas = /2 elegidos/.test(txt('contadorSintomas')) && !visible('errSintomas');
  escribir('selTipo', '3'); escribir('selPieza', '18');
  escribir('txtDescripcion', 'Caries profunda'); escribir('txtObservaciones', 'Control');
"""

PRUEBAS['dx_consulta'] = _ALTA_DX + r"""
  $('formDx').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true})); await esperar(900);
  var post = llamadas('POST', /\/api\/v1\/diagnosticos-medicos$/);
  r.un_post = post.length === 1;
  var b = post.length ? JSON.parse(post[0].body) : {};
  r.post_lleva_consulta_tipo_sintomas_descripcion_y_pieza = b.id_consulta_cab === 17 && b.id_tipo_diagnostico === '3' && JSON.stringify(b.sintomas) === '[1,2]' && b.descripcion_diagnostico === 'Caries profunda' && b.pieza_dental === '18';
  r.post_no_manda_fecha_paciente_medico_ni_codigo = !('fecha_diagnostico' in b) && !('id_paciente' in b) && !('id_medico' in b) && !('codigo' in b);
  r.exito = !!document.querySelector('.swal2-popup') && /DX-0077 registrado/.test(document.querySelector('.swal2-popup').textContent);
  await cerrarSwal();
  r.cierra_el_modal_y_recarga_la_lista = !$('modalNuevo').classList.contains('show') && llamadas('GET', /diagnosticos-medicos\/consulta\/17$/).length >= 2;
  // anular desde la consulta
  $('tbodyConsulta').querySelectorAll('tr')[0].querySelector('[data-accion="anular"]').click(); await esperar(400);
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.anular_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/diagnosticos-medicos\/31$/).length === 1;
  await cerrarSwal();
"""

PRUEBAS['dx_consulta_rechazo'] = _ALTA_DX + r"""
  $('formDx').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true})); await esperar(900);
  r.el_servidor_rechaza_y_el_error_va_al_campo = $('selTipo').classList.contains('is-invalid') && /inactivo/.test(fb('selTipo'));
  r.el_modal_sigue_abierto_y_el_boton_se_rehabilita = $('modalNuevo').classList.contains('show') && !$('btnGuardar').disabled;
  r.no_se_mostro_exito = !document.querySelector('.swal2-popup');
"""

PRUEBAS['dx_lectura'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.sin_boton_nuevo_ni_formulario = !$('btnNuevo') && !$('formDx');
  r.aviso_de_consulta_cerrada = /Finalizada/.test(txt('cBadge')) && /solo lectura/.test(txt('cAviso'));
  var filas = $('tbodyConsulta').querySelectorAll('tr');
  r.tres_diagnosticos = filas.length === 3;
  r.sin_botones_de_anular = !$('tbodyConsulta').querySelector('[data-accion="anular"]');
  r.ver_si = !!filas[0].querySelector('[data-accion="ver"]');
  filas[0].querySelector('[data-accion="ver"]').click(); await esperar(600);
  r.ver_abre = $('modalVer').classList.contains('show') && /DX-0031/.test(txt('verTitulo'));
"""

PRUEBAS['odo_listado'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  var filas = Array.prototype.slice.call($('tbodyGlobal').querySelectorAll('tr'));
  r.dos_filas = filas.length === 2;
  r.fila_con_consulta_paciente_y_hallazgos = /CON-0000017/.test(filas[0].textContent) && /JAVIER ACOSTA/.test(filas[0].textContent) && /CI 5098745/.test(filas[0].textContent) && filas[0].querySelectorAll('td')[4].textContent.trim() === '4';
  r.abrir_va_a_la_consulta_con_id_numerico = filas[0].querySelector('a').getAttribute('href') === '/referenciales/odontograma/odontograma-index?consulta=17';
  r.anular_solo_si_la_consulta_esta_abierta = !!filas[0].querySelector('[data-accion="anular"]') && !filas[1].querySelector('[data-accion="anular"]');
  var fd = $('filtroDesde'); fd.value = '2026-10-01'; fd.dispatchEvent(new Event('change', {bubbles: true})); await esperar(400);
  r.filtro_de_fecha_va_al_servidor = llamadas('GET', /desde=2026-10-01/).length === 1;
  filas = Array.prototype.slice.call($('tbodyGlobal').querySelectorAll('tr'));   // el listado se volvió a pintar
  filas[0].querySelector('[data-accion="anular"]').click(); await esperar(400);
  r.anular_pide_confirmacion = !!document.querySelector('.swal2-popup') && /Anular este odontograma/.test(document.querySelector('.swal2-popup').textContent) && llamadas('DELETE', /./).length === 0;
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.anular_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/odontogramas\/40$/).length === 1;
  await cerrarSwal();
"""

PRUEBAS['odo_sin'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.tarjeta_de_la_consulta = visible('tarjetaConsulta') && txt('cNumero') === 'CON-0000017' && /Programada/.test(txt('cBadge'));
  r.volver_a_la_consulta = $('btnVolverConsulta').getAttribute('href') === '/referenciales/consulta/consulta-detalle/17';
  r.sin_odontograma_ofrece_crearlo = visible('tarjetaSinOdo') && visible('btnCrearOdo') && !visible('filaOdo') && /precargado|Se crea precargado/.test(txt('textoSinOdo'));
  $('btnCrearOdo').click(); await esperar(900);
  var post = llamadas('POST', /\/api\/v1\/odontogramas$/);
  r.crear_hace_un_post_con_la_consulta = post.length === 1 && JSON.parse(post[0].body).id_consulta_cab === 17;
  r.avisa_del_alta = !!document.querySelector('.swal2-popup') && /creado correctamente/.test(document.querySelector('.swal2-popup').textContent);
  await esperar(3500);
  r.despues_se_muestra_el_odontograma_vacio = visible('filaOdo') && !visible('tarjetaSinOdo') && document.querySelectorAll('.odo-pieza').length === 32 && /0 hallazgos/.test(txt('resumenOdo'));
"""

PRUEBAS['odo_editor'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  var piezas = function () { return Array.prototype.slice.call(document.querySelectorAll('.odo-pieza')); };
  var pieza = function (n) { return document.querySelector('.odo-pieza[data-pieza="' + n + '"]'); };
  var sup = function (n, s) { return document.querySelector('.odo-superficie[data-pieza="' + n + '"][data-superficie="' + s + '"]'); };
  r.dibuja_las_32_piezas_permanentes = piezas().length === 32;
  r.cada_pieza_tiene_5_superficies = piezas().every(function (p) { return p.querySelectorAll('.odo-superficie').length === 5; });
  var numeros = piezas().map(function (p) { return parseInt(p.dataset.pieza, 10); }).sort(function (a, b) { return a - b; });
  r.nomenclatura_fdi = JSON.stringify(numeros) === JSON.stringify([11,12,13,14,15,16,17,18,21,22,23,24,25,26,27,28,31,32,33,34,35,36,37,38,41,42,43,44,45,46,47,48]);
  r.hay_linea_media = !!document.querySelector('.odo-mitad');
  // orientación: la mesial mira a la línea media; la vestibular, hacia afuera
  var lado = function (n, lado) { var p = pieza(n); var pol = Array.prototype.slice.call(p.querySelectorAll('polygon')); var pts = { arriba: '0,0 34,0 26,8 8,8', abajo: '8,26 26,26 34,34 0,34', izquierda: '0,0 8,8 8,26 0,34', derecha: '34,0 34,34 26,26 26,8' }[lado]; return pol.filter(function (x) { return x.getAttribute('points') === pts; })[0].dataset.superficie; };
  r.cuadrante_1_mesial_a_la_derecha = lado(18, 'derecha') === 'M' && lado(18, 'izquierda') === 'D';
  r.cuadrante_2_mesial_a_la_izquierda = lado(21, 'izquierda') === 'M' && lado(21, 'derecha') === 'D';
  r.cuadrante_4_mesial_a_la_derecha = lado(41, 'derecha') === 'M';
  r.cuadrante_3_mesial_a_la_izquierda = lado(31, 'izquierda') === 'M';
  r.arcada_superior_vestibular_arriba = lado(18, 'arriba') === 'V' && lado(18, 'abajo') === 'L';
  r.arcada_inferior_vestibular_abajo = lado(48, 'arriba') === 'L' && lado(48, 'abajo') === 'V';
  // color por estado
  r.superficie_con_caries_en_rojo = /#D32F2F/i.test(sup(18, 'O').getAttribute('style') || '');
  r.superficie_con_obturacion_en_gris = /#757575/i.test(sup(18, 'M').getAttribute('style') || '');
  r.superficie_sin_hallazgo_vacia = !sup(18, 'V').getAttribute('style');
  r.pieza_completa_con_contorno_de_color_y_simbolo = /#FDD835/i.test(pieza(11).querySelector('.odo-contorno').getAttribute('style') || '') && /Co/.test(pieza(11).textContent);
  r.pieza_extraida_contorno_oscuro = /#212121/i.test(pieza(36).querySelector('.odo-contorno').getAttribute('style') || '') && /Ex/.test(pieza(36).textContent);
  r.piezas_con_hallazgos_marcadas = pieza(18).classList.contains('con-hallazgos') && pieza(11).classList.contains('con-hallazgos') && !pieza(12).classList.contains('con-hallazgos');
  r.tooltip_con_los_estados = /Caries/.test(sup(18, 'O').querySelector('title').textContent);
  r.leyenda_con_los_4_estados = $('leyenda').querySelectorAll('.odo-muestra').length === 4;
  r.tabla_con_los_4_hallazgos = $('tbodyTodos').querySelectorAll('tr').length === 4 && /\(4\)/.test(txt('cantidadTotal')) && /4 hallazgos/.test(txt('resumenOdo'));
  // dentición temporal
  $('chkTemporal').checked = true; $('chkTemporal').dispatchEvent(new Event('change', {bubbles: true})); await esperar(300);
  r.con_temporal_dibuja_52_piezas = piezas().length === 52 && !!pieza(55) && !!pieza(85) && !!pieza(61) && !!pieza(71) && !pieza(56);
  $('chkTemporal').checked = false; $('chkTemporal').dispatchEvent(new Event('change', {bubbles: true})); await esperar(300);
  r.sin_temporal_vuelve_a_32 = piezas().length === 32;
  // seleccionar una superficie
  sup(18, 'O').dispatchEvent(new MouseEvent('click', {bubbles: true})); await esperar(300);
  r.seleccion_pieza_y_superficie = txt('selPieza') === '18' && $('grupoSuperficie').querySelector('button.active').dataset.superficie === 'O' && pieza(18).classList.contains('seleccionada') && sup(18, 'O').classList.contains('elegida');
  r.estados_de_superficie_solamente = $('listaEstados').querySelectorAll('button').length === 2 && /Caries/.test($('listaEstados').textContent) && !/Corona/.test($('listaEstados').textContent);
  r.hallazgos_de_la_pieza = $('hallazgosPieza').querySelectorAll('[data-quitar]').length === 2 && /sensible/.test(txt('hallazgosPieza'));
  r.agregar_deshabilitado_sin_estado = $('btnAgregar').disabled;
  // agregar un hallazgo repetido: el servidor lo rechaza y el error se muestra en el panel
  $('listaEstados').querySelector('button[data-estado="2"]').click(); await esperar(200);
  r.con_estado_habilita_agregar = !$('btnAgregar').disabled;
  escribir('txtObservacion', 'otra vez');
  $('btnAgregar').click(); await esperar(700);
  var post = llamadas('POST', /\/api\/v1\/odontogramas\/40\/hallazgos$/);
  var b = post.length ? JSON.parse(post[0].body) : {};
  r.post_a_hallazgos_con_pieza_superficie_y_estado = post.length === 1 && b.numero_diente === 18 && b.superficie === 'O' && b.id_estado_dental === 2 && b.observacion === 'otra vez';
  r.error_del_servidor_en_el_panel = visible('errHallazgo') && /ya está registrado/.test(txt('errHallazgo'));
  // pieza completa: solo estados de pieza
  pieza(11).querySelector('.odo-numero').dispatchEvent(new MouseEvent('click', {bubbles: true})); await esperar(300);
  r.numero_elige_pieza_completa = txt('selPieza') === '11' && $('grupoSuperficie').querySelector('button.active').dataset.superficie === 'T';
  r.estados_de_pieza_solamente = $('listaEstados').querySelectorAll('button').length === 2 && /Corona/.test($('listaEstados').textContent) && !/Caries/.test($('listaEstados').textContent);
  // cambiar a una superficie limpia el estado elegido
  $('listaEstados').querySelector('button[data-estado="7"]').click(); await esperar(200);
  $('grupoSuperficie').querySelector('[data-superficie="V"]').click(); await esperar(200);
  r.cambiar_de_tipo_de_superficie_limpia_el_estado = $('btnAgregar').disabled && /Caries/.test($('listaEstados').textContent);
  // quitar un hallazgo
  sup(18, 'O').dispatchEvent(new MouseEvent('click', {bubbles: true})); await esperar(300);
  $('hallazgosPieza').querySelector('[data-quitar="501"]').click(); await esperar(400);
  r.quitar_pide_confirmacion = !!document.querySelector('.swal2-popup') && /Quitar este hallazgo/.test(document.querySelector('.swal2-popup').textContent) && llamadas('DELETE', /./).length === 0;
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.quitar_hace_delete_al_id_del_hallazgo = llamadas('DELETE', /\/api\/v1\/odontogramas\/hallazgos\/501$/).length === 1;
  await cerrarSwal();
  // anular el odontograma
  r.boton_anular_visible = visible('btnAnularOdo');
  $('btnAnularOdo').click(); await esperar(400);
  r.anular_avisa_que_es_definitivo = !!document.querySelector('.swal2-popup') && /definitivo/.test(document.querySelector('.swal2-popup').textContent);
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.anular_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/odontogramas\/40$/).length === 1;
  await cerrarSwal();
"""

PRUEBAS['odo_lectura'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.aviso_de_solo_lectura = /Finalizada/.test(txt('cBadge')) && /solo lectura/.test(txt('cAviso'));
  r.dibuja_las_piezas = document.querySelectorAll('.odo-pieza').length === 32;
  r.sin_crear_ni_anular = !$('btnCrearOdo') && !$('btnAnularOdo');
  document.querySelector('.odo-superficie[data-pieza="18"][data-superficie="O"]').dispatchEvent(new MouseEvent('click', {bubbles: true})); await esperar(300);
  r.se_puede_consultar_la_pieza = txt('selPieza') === '18' && $('hallazgosPieza').textContent.indexOf('Caries') >= 0;
  r.panel_de_edicion_oculto = $('panelEditar').style.display === 'none';
  r.sin_botones_de_quitar = $('hallazgosPieza').querySelectorAll('[data-quitar]').length === 0;
  r.la_leyenda_y_la_tabla_siguen = $('leyenda').querySelectorAll('.odo-muestra').length === 4 && $('tbodyTodos').querySelectorAll('tr').length === 4;
"""


def armar(nombre, esc):
    esc = dict(esc, nombre=nombre)
    with app.test_request_context('/'):
        session['id_usuario'] = 1; session['id_rol'] = 1; session['nombre_rol'] = 'Administrador'
        html = render_template(esc['plantilla'], es_medico=esc['es_medico'])
    html = html.replace('"/static/', '"' + STATIC)
    mock = MOCK % {'esc': json.dumps(esc), 'estados': json.dumps(ESTADOS), 'dx_detalle': json.dumps(DXS[0]), 'tipos': json.dumps(TIPOS), 'sintomas': json.dumps(SINTOMAS)}
    html = html.replace('<head>', '<head>' + mock, 1)
    prueba = ('<pre id="resultado" style="display:none"></pre><script>(function () { (async function () { try {\n'
              'await new Promise(function (ok) { setTimeout(ok, 900); });\n' + COMUN + PRUEBAS[nombre] +
              '\nr.ninguna_url_con_id_no_numerico = sinIdsRaros(); r.sin_errores_al_final = window.__errores.length === 0; if (window.__errores.length) r.errores = window.__errores;\n'
              '} catch (e) { r.EXCEPCION = String(e && e.stack || e); } document.getElementById("resultado").textContent = JSON.stringify(r); })(); })();</script>')
    # `r` se declara dentro de COMUN: la prueba entera va en el mismo ámbito
    html = html.replace('</body>', prueba + '</body>', 1)
    return html


total_fallos = 0
for nombre, esc in ESCENARIOS.items():
    archivo = SALIDA / f'{nombre}.html'
    archivo.write_text(armar(nombre, esc), encoding='utf-8')
    url = archivo.as_uri() + (f"?consulta={esc['consulta']}" if esc.get('consulta') else '')
    proc = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--no-first-run', '--virtual-time-budget=60000', '--dump-dom', url],
                          capture_output=True, text=True, encoding='utf-8', timeout=240)
    m = re.search(r'<pre id="resultado"[^>]*>(.*?)</pre>', proc.stdout, re.S)
    if not m or not m.group(1).strip():
        print(f'FAIL {nombre}: la página no produjo resultado (¿error de sintaxis?)'); total_fallos += 1
        print(proc.stderr[-400:]); continue
    r = json.loads(_h.unescape(m.group(1)))
    bools = [k for k, v in r.items() if isinstance(v, bool)]
    malos = [k for k in bools if not r[k]] + (['EXCEPCION'] if 'EXCEPCION' in r else [])
    print(('OK  ' if not malos else 'FAIL'), nombre, '| checks:', len(bools))
    if malos:
        total_fallos += 1
        print('     fallan:', malos)
        print('     detalle:', json.dumps(r, ensure_ascii=False)[:1600])
print('VISTAS CON FALLOS:', total_fallos)
