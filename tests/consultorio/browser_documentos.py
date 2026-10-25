"""Generar Recetas, Orden de Estudios y Orden de Análisis en un navegador real (Edge headless) con fetch simulado.
Cada vista se renderiza con Flask (sesión de Administrador: todos los permisos del catálogo) pasando `es_medico` (y `cfg` en las órdenes) como lo harían las rutas,
se reescribe /static a file:// y se corre un script que usa el DOM, Bootstrap 5 y SweetAlert2 reales. El JSON simulado trae las claves ORDENADAS como Flask y las URL
pedidas no pueden llevar ids no numéricos.
Uso: .\\.venv\\Scripts\\python.exe -I tests\\consultorio\\browser_documentos.py <carpeta de salida>      (necesita Edge)
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


def resumen(estado, cargar, id_consulta=18):
    c = ordenado({'id_consulta_cab': id_consulta, 'numero': 'CON-%07d' % id_consulta, 'estado': estado, 'activo': True, 'id_paciente': 7, 'nombre_paciente': 'JAVIER ACOSTA',
                  'cedula_paciente': '5098745', 'id_medico': 20, 'nombre_medico': 'OSCAR GONZALES', 'fecha_cita': '2026-10-27', 'hora_cita': '09:00:00'})
    return {'consulta': c, 'contadores': {}, 'acciones': {'iniciar': False, 'finalizar': False, 'cancelar': False, 'cargar_clinico': cargar}}


def receta(i, estado_consulta='en_proceso', id_consulta=18, activo=True):
    meds = [ordenado({'id_receta_medicamento': i * 10, 'id_medicamento': 4, 'nombre_comercial': 'AMOXICILINA', 'presentacion': 'CAJA X 14', 'dosis': '500 mg', 'frecuencia': 'cada 8 h', 'duracion': '7 días'}),
            ordenado({'id_receta_medicamento': i * 10 + 1, 'id_medicamento': 5, 'nombre_comercial': 'IBUPROFENO', 'presentacion': None, 'dosis': '400 mg', 'frecuencia': 'cada 8 h', 'duracion': '3 días'})]
    return ordenado({'id_receta': i, 'id_consulta_cab': id_consulta, 'numero_consulta': 'CON-%07d' % id_consulta, 'estado_consulta': estado_consulta, 'id_diagnostico': 7, 'codigo_diagnostico': 'DX-0007',
                     'id_tratamiento': None, 'tipo_tratamiento': None, 'indicaciones_generales': 'Tomar con las comidas.', 'fecha_receta': '2026-10-26', 'activo': activo,
                     'fecha_registro': '2026-10-26T09:30:00', 'id_paciente': 7, 'nombre_paciente': 'JAVIER ACOSTA', 'cedula_paciente': '5098745', 'id_medico': 20,
                     'nombre_medico': 'OSCAR GONZALES', 'numero': 'RCT-%07d' % i, 'medicamentos': meds})


def orden(pk, tipo_col, i, estado, estado_consulta='en_proceso', id_consulta=18, prefijo='OES'):
    return ordenado({pk: i, 'id_consulta_cab': id_consulta, 'numero_consulta': 'CON-%07d' % id_consulta, 'estado_consulta': estado_consulta, 'id_diagnostico': 7, 'codigo_diagnostico': 'DX-0007',
                     'id_tratamiento': None, 'tipo_tratamiento': None, tipo_col: 3, 'tipo': 'RADIOGRAFÍA PANORÁMICA', 'motivo_orden': 'Control previo a la extracción',
                     'indicaciones': 'En ayunas', 'fecha_orden': '2026-10-26', 'estado': estado, 'fecha_registro': '2026-10-26T09:30:00', 'id_paciente': 7,
                     'nombre_paciente': 'JAVIER ACOSTA', 'cedula_paciente': '5098745', 'id_medico': 20, 'nombre_medico': 'OSCAR GONZALES', 'numero': '%s-%07d' % (prefijo, i)})


CFG = {
    'estudios': {'titulo': 'Generar Orden de Estudios', 'singular': 'orden de estudios', 'api': '/api/v1/orden-estudios', 'pk': 'id_orden_estudio', 'tipo_col': 'id_tipo_estudio',
                 'api_tipos': '/api/v1/tipos-estudio', 'etiqueta_tipo': 'Tipo de estudio', 'ventana': 'ordenestudio', 'validador': 'ordenEstudio'},
    'analisis': {'titulo': 'Generar Orden de Análisis', 'singular': 'orden de análisis', 'api': '/api/v1/orden-analisis', 'pk': 'id_orden_analisis', 'tipo_col': 'id_tipo_analisis',
                 'api_tipos': '/api/v1/tipos-analisis', 'etiqueta_tipo': 'Tipo de análisis', 'ventana': 'ordenanalisis', 'validador': 'ordenAnalisis'},
}
OE = lambda *a, **k: orden('id_orden_estudio', 'id_tipo_estudio', *a, **k)
OA = lambda *a, **k: orden('id_orden_analisis', 'id_tipo_analisis', *a, prefijo='OAN', **k)
RECETAS_GLOBAL = [receta(31), receta(32, 'finalizada', 15), receta(33)]
ORDENES_GLOBAL = [OE(41, 'pendiente'), OE(42, 'en_proceso', 'finalizada', 15), OE(43, 'enviado', 'cancelada', 16), OE(44, 'completado'), OE(45, 'pendiente', 'finalizada', 17)]
ORDENES_CONSULTA = [OE(41, 'pendiente'), OE(44, 'completado')]
MEDICAMENTOS = [ordenado({'id_medicamento': 4, 'nombre_comercial': 'AMOXICILINA', 'presentacion': 'CAJA X 14', 'activo': True}), ordenado({'id_medicamento': 5, 'nombre_comercial': 'IBUPROFENO', 'presentacion': None, 'activo': True})]
TIPOS_E = [ordenado({'id_tipo_estudio': 3, 'descripcion': 'RADIOGRAFÍA PANORÁMICA', 'activo': True}), ordenado({'id_tipo_estudio': 4, 'descripcion': 'TOMOGRAFÍA', 'activo': True})]
TIPOS_A = [ordenado({'id_tipo_analisis': 3, 'descripcion': 'HEMOGRAMA', 'activo': True})]
DIAGNOSTICOS = [ordenado({'id_diagnostico': 7, 'codigo': 'DX-0007', 'tipo_diagnostico': 'CARIES', 'pieza_dental': '18'})]
TRATAMIENTOS = [ordenado({'id_tratamiento': 9, 'tipo_tratamiento': 'ENDODONCIA', 'estado': 'en_seguimiento'})]
RECHAZO_TIPO = {'campo': 'id_tipo_estudio', 'error': 'El tipo de estudio seleccionado está inactivo.'}

ESCENARIOS = {
    're_listado': dict(plantilla='receta-index.html', es_medico=True, url='', lista=RECETAS_GLOBAL, total=31, detalle=receta(31)),
    're_consulta': dict(plantilla='receta-index.html', es_medico=True, url='?consulta=18', resumen=resumen('en_proceso', True), lista=[receta(31), receta(33)], detalle=receta(31)),
    're_consulta_rechazo': dict(plantilla='receta-index.html', es_medico=True, url='?consulta=18', resumen=resumen('en_proceso', True), lista=[receta(31)], detalle=receta(31),
                                rechazo={'campo': 'medicamentos', 'error': 'Hay medicamentos inactivos: AMOXICILINA. Quítelos de la receta.'}),
    're_lectura': dict(plantilla='receta-index.html', es_medico=False, url='?consulta=18', resumen=resumen('finalizada', False), lista=RECETAS_GLOBAL, detalle=receta(31)),
    'oe_listado': dict(plantilla='orden-clinica-index.html', cfg='estudios', es_medico=True, url='', lista=ORDENES_GLOBAL, total=31, detalle=OE(42, 'en_proceso', 'finalizada', 15)),
    'oe_consulta': dict(plantilla='orden-clinica-index.html', cfg='estudios', es_medico=True, url='?consulta=18', resumen=resumen('en_proceso', True), lista=ORDENES_CONSULTA,
                        detalle=OE(41, 'pendiente')),
    'oe_consulta_rechazo': dict(plantilla='orden-clinica-index.html', cfg='estudios', es_medico=True, url='?consulta=18', resumen=resumen('en_proceso', True), lista=ORDENES_CONSULTA,
                                detalle=OE(41, 'pendiente'), rechazo=RECHAZO_TIPO),
    'oe_lectura': dict(plantilla='orden-clinica-index.html', cfg='estudios', es_medico=False, url='?consulta=18', resumen=resumen('finalizada', False), lista=ORDENES_GLOBAL,
                       detalle=OE(41, 'pendiente')),
    'oa_listado': dict(plantilla='orden-clinica-index.html', cfg='analisis', es_medico=True, url='?consulta=18', resumen=resumen('en_proceso', True),
                       lista=[OA(51, 'pendiente'), OA(52, 'enviado', 'en_proceso')], detalle=OA(51, 'pendiente')),
}

MOCK = r"""
<script>
window.__ESC = %(esc)s;
window.__calls = []; window.__errores = [];
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
    else if (/\/api\/v1\/(recetas|orden-estudios|orden-analisis)\/\d+$/.test(path)) cuerpo.data = E.detalle;
    else if (/\/api\/v1\/(recetas|orden-estudios|orden-analisis)$/.test(path)) { cuerpo.data = E.lista; cuerpo.total = E.total || E.lista.length; }
    else if (/\/api\/v1\/medicamentos$/.test(path)) cuerpo.data = %(meds)s;
    else if (/\/api\/v1\/tipos-estudio$/.test(path)) cuerpo.data = %(te)s;
    else if (/\/api\/v1\/tipos-analisis$/.test(path)) cuerpo.data = %(ta)s;
    else if (/\/api\/v1\/diagnosticos-medicos\/consulta\/\d+$/.test(path)) cuerpo.data = %(dx)s;
    else if (/\/api\/v1\/tratamientos\/consulta\/\d+$/.test(path)) cuerpo.data = %(tr)s;
  } else if (metodo === 'POST') {
    if (E.rechazo) { cuerpo = {success: false, data: null, error: E.rechazo.error, campo: E.rechazo.campo}; status = 409; }
    else { cuerpo.data = {numero: 'DOC-0000077'}; cuerpo.mensaje = 'Documento DOC-0000077 registrado correctamente.'; status = 201; }
  } else if (metodo === 'PUT') { cuerpo.mensaje = 'Orden actualizada a "Enviada".'; }
  else if (metodo === 'DELETE') { cuerpo.mensaje = 'Anulado correctamente.'; }
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
  var sinIdsRaros = function () { return window.__calls.every(function (c) { return !/\/api\/v1\/[a-z-]+\/(true|false|null|undefined)(\/|$)/.test(c.url); }); };
  var fb = function (id) { return $(id).parentElement.querySelector('.invalid-feedback').textContent; };
  var submit = async function (id) { $(id).dispatchEvent(new Event('submit', {cancelable: true, bubbles: true})); await esperar(900); };
  var filas = function () { return Array.prototype.slice.call($('tbody').querySelectorAll('tr')); };
"""

PRUEBAS = {}

PRUEBAS['re_listado'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  var f = filas();
  r.tres_filas = f.length === 3;
  r.fila_con_numero_paciente_consulta_y_medicamentos = /RCT-0000031/.test(f[0].textContent) && /JAVIER ACOSTA/.test(f[0].textContent) && /CI 5098745/.test(f[0].textContent)
    && /CON-0000018/.test(f[0].textContent) && /AMOXICILINA/.test(f[0].textContent) && /IBUPROFENO/.test(f[0].textContent);
  r.enlace_a_la_consulta_con_id_numerico = f[0].querySelector('a[href^="/referenciales/consulta/consulta-detalle/"]').getAttribute('href') === '/referenciales/consulta/consulta-detalle/18';
  r.pdf_con_el_id_numerico_en_otra_pestana = f[0].querySelector('a[href$="/pdf"]').getAttribute('href') === '/api/v1/recetas/31/pdf' && f[0].querySelector('a[href$="/pdf"]').getAttribute('target') === '_blank';
  r.anular_solo_si_la_consulta_esta_abierta = !!f[0].querySelector('[data-accion="anular"]') && !f[1].querySelector('[data-accion="anular"]') && !!f[2].querySelector('[data-accion="anular"]');
  r.sin_boton_nuevo_fuera_de_la_consulta = !visible('btnNuevo');
  r.info_paginacion = /Mostrando 1–15 de 31/.test(txt('infoPagina'));
  var fq = $('filtroQ'); fq.value = 'acosta'; fq.dispatchEvent(new Event('input', {bubbles: true})); await esperar(700);
  r.filtro_con_espera = llamadas('GET', /q=acosta/).length === 1;
  $('btnLimpiar').click(); await esperar(400);
  f = filas();
  f[0].querySelector('[data-accion="ver"]').click(); await esperar(600);
  r.ver_con_medicamentos_dosis_e_indicaciones = $('modalVer').classList.contains('show') && /Receta RCT-0000031/.test(txt('verTitulo')) && /500 mg/.test(txt('verCuerpo')) && /cada 8 h/.test(txt('verCuerpo'))
    && /7 días/.test(txt('verCuerpo')) && /Tomar con las comidas/.test(txt('verCuerpo')) && /DX-0007/.test(txt('verCuerpo'));
  r.ver_tiene_el_pdf = $('verPdf').getAttribute('href') === '/api/v1/recetas/31/pdf';
  r.ver_pidio_el_id_numerico = llamadas('GET', /\/api\/v1\/recetas\/31$/).length === 1;
  $('modalVer').querySelector('[data-bs-dismiss="modal"]').click(); await esperar(600);
  filas()[0].querySelector('[data-accion="anular"]').click(); await esperar(400);
  r.anular_pide_confirmacion = !!document.querySelector('.swal2-popup') && /Anular esta receta/.test(document.querySelector('.swal2-popup').textContent) && llamadas('DELETE', /./).length === 0;
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.anular_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/recetas\/31$/).length === 1;
  await cerrarSwal();
"""

_ALTA_RE = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.tarjeta_de_la_consulta = visible('tarjetaConsulta') && txt('cNumero') === 'CON-0000018' && /JAVIER ACOSTA/.test(txt('cDetalle')) && /En proceso/.test(txt('cBadge'));
  r.volver_a_la_consulta = visible('btnVolverConsulta') && $('btnVolverConsulta').getAttribute('href') === '/referenciales/consulta/consulta-detalle/18';
  r.pidio_la_consulta_y_sus_recetas = llamadas('GET', /\/consultas\/18\/resumen$/).length === 1 && llamadas('GET', /\/api\/v1\/recetas\?.*consulta=18/).length >= 1;
  r.en_la_consulta_no_se_repiten_paciente_medico_ni_consulta = !visible('tbody') || filas()[0].querySelectorAll('td').length === 4;
  r.boton_nuevo_visible = visible('btnNuevo');
  $('btnNuevo').click(); await esperar(900);
  var modal = $('modalNuevo');
  r.modal_abre_con_una_fila_de_medicamento_y_los_combos = modal.classList.contains('show') && $('filasMed').querySelectorAll('.fila-med').length === 1
    && $('filasMed').querySelector('select').options.length === 3 && $('selDiagnostico').options.length === 2 && $('selTratamiento').options.length === 2;
  await submit('formReceta');
  r.vacio_no_envia_y_marca = llamadas('POST', /./).length === 0 && visible('errMedicamentos') && /dosis, frecuencia y duración|medicamento/.test(txt('errMedicamentos'))
    && $('txtIndicaciones').classList.contains('is-invalid') && /obligatorias/.test(fb('txtIndicaciones'));
  var fila = $('filasMed').querySelector('.fila-med');
  fila.querySelector('[data-campo="medicamento"]').value = '4';
  fila.querySelector('[data-campo="dosis"]').value = '500 mg'; fila.querySelector('[data-campo="frecuencia"]').value = 'cada 8 h'; fila.querySelector('[data-campo="duracion"]').value = '7 días';
  $('btnAgregarMed').click();
  var f2 = $('filasMed').querySelectorAll('.fila-med')[1];
  f2.querySelector('[data-campo="medicamento"]').value = '4';
  f2.querySelector('[data-campo="dosis"]').value = '1'; f2.querySelector('[data-campo="frecuencia"]').value = '2'; f2.querySelector('[data-campo="duracion"]').value = '3';
  escribir('txtIndicaciones', 'Tomar con las comidas');
  await submit('formReceta');
  r.medicamento_repetido_se_rechaza_en_el_formulario = visible('errMedicamentos') && /No repita el mismo medicamento/.test(txt('errMedicamentos')) && llamadas('POST', /./).length === 0;
  f2.querySelector('[data-campo="medicamento"]').value = '5';
  f2.querySelector('[data-campo="duracion"]').value = '';
  await submit('formReceta');
  r.fila_incompleta_se_rechaza = visible('errMedicamentos') && /dosis, frecuencia y duración/.test(txt('errMedicamentos')) && llamadas('POST', /./).length === 0;
  f2.querySelector('[data-campo="duracion"]').value = '3 días';
  escribir('selDiagnostico', '7');
"""

PRUEBAS['re_consulta'] = _ALTA_RE + r"""
  await submit('formReceta');
  var post = llamadas('POST', /\/api\/v1\/recetas$/);
  var b = post.length ? JSON.parse(post[0].body) : {};
  r.un_post = post.length === 1;
  r.post_lleva_consulta_indicaciones_medicamentos_y_vinculo = b.id_consulta_cab === 18 && b.indicaciones_generales === 'Tomar con las comidas' && b.medicamentos.length === 2
    && b.medicamentos[0].id_medicamento === '4' && b.medicamentos[0].dosis === '500 mg' && b.medicamentos[1].id_medicamento === '5' && b.id_diagnostico === '7';
  r.post_no_manda_fecha_paciente_medico_ni_numero = !('fecha_receta' in b) && !('id_paciente' in b) && !('id_medico' in b) && !('numero' in b);
  r.exito = !!document.querySelector('.swal2-popup') && /registrado correctamente/.test(document.querySelector('.swal2-popup').textContent);
  await cerrarSwal();
  r.cierra_el_modal_y_recarga = !$('modalNuevo').classList.contains('show') && llamadas('GET', /\/api\/v1\/recetas\?/).length >= 2;
  filas()[0].querySelector('[data-accion="anular"]').click(); await esperar(400);
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.anular_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/recetas\/31$/).length === 1;
  await cerrarSwal();
"""

PRUEBAS['re_consulta_rechazo'] = _ALTA_RE + r"""
  await submit('formReceta');
  r.el_servidor_rechaza_y_el_error_va_a_medicamentos = visible('errMedicamentos') && /inactivos/.test(txt('errMedicamentos'));
  r.el_modal_sigue_abierto_y_el_boton_se_rehabilita = $('modalNuevo').classList.contains('show') && !$('btnGuardar').disabled;
  r.no_se_mostro_exito = !document.querySelector('.swal2-popup');
"""

PRUEBAS['re_lectura'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.sin_boton_nuevo_ni_formulario = !$('btnNuevo') && !$('formReceta');
  r.aviso_de_consulta_cerrada = /Finalizada/.test(txt('cBadge')) && /solo lectura/.test(txt('cAviso'));
  r.sin_anular_pero_con_ver_y_pdf = !document.querySelector('[data-accion="anular"]') && !!document.querySelector('[data-accion="ver"]') && !!document.querySelector('a[href$="/pdf"]');
  filas()[0].querySelector('[data-accion="ver"]').click(); await esperar(600);
  r.ver_abre = $('modalVer').classList.contains('show');
"""

PRUEBAS['oe_listado'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  var f = filas();
  r.cinco_filas = f.length === 5;
  r.fila_con_numero_paciente_tipo_y_estado = /OES-0000041/.test(f[0].textContent) && /JAVIER ACOSTA/.test(f[0].textContent) && /RADIOGRAFÍA PANORÁMICA/.test(f[0].textContent) && /Pendiente/.test(f[0].textContent);
  r.pdf_de_la_orden_de_estudios = f[0].querySelector('a[href$="/pdf"]').getAttribute('href') === '/api/v1/orden-estudios/41/pdf';
  // 0 pendiente/abierta · 1 en_proceso/finalizada · 2 enviado/cancelada · 3 completado/abierta · 4 pendiente/finalizada
  r.avanzar_en_las_abiertas = !!f[0].querySelector('[data-accion="avanzar"]');
  r.avanzar_TAMBIEN_con_la_consulta_finalizada = !!f[1].querySelector('[data-accion="avanzar"]') && !!f[4].querySelector('[data-accion="avanzar"]');
  r.sin_avanzar_con_la_consulta_cancelada = !f[2].querySelector('[data-accion="avanzar"]');
  r.sin_avanzar_si_esta_completada = !f[3].querySelector('[data-accion="avanzar"]');
  r.cancelar_solo_abiertas_y_no_completadas = !!f[0].querySelector('[data-accion="anular"]') && !f[1].querySelector('[data-accion="anular"]') && !f[2].querySelector('[data-accion="anular"]')
    && !f[3].querySelector('[data-accion="anular"]') && !f[4].querySelector('[data-accion="anular"]');
  r.titulo_del_boton_avanzar_dice_el_siguiente_estado = /Pasar a En proceso/.test(f[0].querySelector('[data-accion="avanzar"]').getAttribute('title') || '') === false && /Enviada/.test(f[0].querySelector('[data-accion="avanzar"]').getAttribute('title'))
    && /Completada/.test(f[1].querySelector('[data-accion="avanzar"]').getAttribute('title'));
  escribir('filtroEstado', 'enviado'); await esperar(500);
  r.filtro_estado_va_al_servidor = llamadas('GET', /estado=enviado/).length === 1;
  $('btnLimpiar').click(); await esperar(400);
  f = filas();
  f[0].querySelector('[data-accion="ver"]').click(); await esperar(600);
  r.ver_con_motivo_indicaciones_y_pdf = $('modalVer').classList.contains('show') && /OES-0000042|OES-0000041/.test(txt('verTitulo')) && /Control previo/.test(txt('verCuerpo')) && /En ayunas/.test(txt('verCuerpo'))
    && /\/api\/v1\/orden-estudios\/\d+\/pdf$/.test($('verPdf').getAttribute('href'));
  $('modalVer').querySelector('[data-bs-dismiss="modal"]').click(); await esperar(600);
  f = filas();
  f[1].querySelector('[data-accion="avanzar"]').click(); await esperar(400);
  r.avanzar_pide_confirmacion = !!document.querySelector('.swal2-popup') && /Completada/.test(document.querySelector('.swal2-popup').textContent) && llamadas('PUT', /./).length === 0;
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.avanzar_hace_put_al_id_numerico_sin_mandar_el_estado = llamadas('PUT', /\/api\/v1\/orden-estudios\/42\/estado$/).length === 1 && llamadas('PUT', /./)[0].body === null;
  await cerrarSwal();
  f = filas();
  f[0].querySelector('[data-accion="anular"]').click(); await esperar(400);
  r.cancelar_avisa_que_es_definitivo = !!document.querySelector('.swal2-popup') && /Cancelar esta orden de estudios/.test(document.querySelector('.swal2-popup').textContent) && /definitivo/.test(document.querySelector('.swal2-popup').textContent);
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.cancelar_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/orden-estudios\/41$/).length === 1;
  await cerrarSwal();
"""

_ALTA_OE = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.tarjeta_y_volver_a_la_consulta = visible('tarjetaConsulta') && txt('cNumero') === 'CON-0000018' && $('btnVolverConsulta').getAttribute('href') === '/referenciales/consulta/consulta-detalle/18';
  r.boton_nuevo_visible_con_su_nombre = visible('btnNuevo') && /Nueva orden de estudios/.test(txt('btnNuevo'));
  r.dos_filas_sin_columnas_de_paciente = filas().length === 2 && filas()[0].querySelectorAll('td').length === 5;
  $('btnNuevo').click(); await esperar(900);
  r.modal_abre_con_tipos_diagnosticos_y_tratamientos = $('modalNuevo').classList.contains('show') && $('selTipo').options.length === 3 && $('selDiagnostico').options.length === 2 && $('selTratamiento').options.length === 2;
  r.pidio_el_catalogo_de_estudios = llamadas('GET', /\/api\/v1\/tipos-estudio$/).length === 1 && llamadas('GET', /\/api\/v1\/tratamientos\/consulta\/18$/).length === 1;
  await submit('formOrden');
  r.vacio_no_envia_y_marca = llamadas('POST', /./).length === 0 && $('selTipo').classList.contains('is-invalid') && /tipo de estudio es obligatorio/.test(fb('selTipo')) && $('txtMotivo').classList.contains('is-invalid');
  escribir('selTipo', '3'); escribir('txtMotivo', 'Control previo'); escribir('txtIndicaciones', 'En ayunas'); escribir('selDiagnostico', '7'); escribir('selTratamiento', '9');
"""

PRUEBAS['oe_consulta'] = _ALTA_OE + r"""
  await submit('formOrden');
  var post = llamadas('POST', /\/api\/v1\/orden-estudios$/);
  var b = post.length ? JSON.parse(post[0].body) : {};
  r.un_post_con_consulta_tipo_motivo_indicaciones_y_vinculos = post.length === 1 && b.id_consulta_cab === 18 && b.id_tipo_estudio === '3' && b.motivo_orden === 'Control previo' && b.indicaciones === 'En ayunas'
    && b.id_diagnostico === '7' && b.id_tratamiento === '9';
  r.post_no_manda_estado_fecha_ni_paciente = !('estado' in b) && !('fecha_orden' in b) && !('id_paciente' in b) && !('id_tipo_analisis' in b);
  r.exito = !!document.querySelector('.swal2-popup') && /registrado correctamente/.test(document.querySelector('.swal2-popup').textContent);
  await cerrarSwal();
  r.cierra_el_modal_y_recarga = !$('modalNuevo').classList.contains('show') && llamadas('GET', /\/api\/v1\/orden-estudios\?.*consulta=18/).length >= 2;
"""

PRUEBAS['oe_consulta_rechazo'] = _ALTA_OE + r"""
  await submit('formOrden');
  r.el_servidor_rechaza_y_el_error_va_al_campo = $('selTipo').classList.contains('is-invalid') && /inactivo/.test(fb('selTipo'));
  r.el_modal_sigue_abierto_y_el_boton_se_rehabilita = $('modalNuevo').classList.contains('show') && !$('btnGuardar').disabled;
  r.no_se_mostro_exito = !document.querySelector('.swal2-popup');
"""

PRUEBAS['oe_lectura'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.sin_boton_nuevo_ni_formulario = !$('btnNuevo') && !$('formOrden');
  r.aviso_de_consulta_cerrada = /Finalizada/.test(txt('cBadge')) && /solo lectura|no admite/.test(txt('cAviso'));
  r.sin_avanzar_ni_cancelar_pero_con_ver_y_pdf = !document.querySelector('[data-accion="avanzar"]') && !document.querySelector('[data-accion="anular"]') && !!document.querySelector('[data-accion="ver"]')
    && !!document.querySelector('a[href$="/pdf"]');
"""

PRUEBAS['oa_listado'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.titulo_de_analisis = /Orden de Análisis/.test(document.querySelector('.page-title').textContent) && /Nueva orden de análisis/.test(txt('btnNuevo'));
  var f = filas();
  r.usa_la_api_de_analisis_y_su_pdf = llamadas('GET', /\/api\/v1\/orden-analisis\?/).length >= 1 && f[0].querySelector('a[href$="/pdf"]').getAttribute('href') === '/api/v1/orden-analisis/51/pdf' && /OAN-0000051/.test(f[0].textContent);
  $('btnNuevo').click(); await esperar(900);
  r.pide_el_catalogo_de_analisis = llamadas('GET', /\/api\/v1\/tipos-analisis$/).length === 1 && llamadas('GET', /\/api\/v1\/tipos-estudio$/).length === 0 && $('selTipo').options.length === 2;
  r.la_etiqueta_es_tipo_de_analisis = /Tipo de análisis/.test($('modalNuevo').textContent);
  escribir('selTipo', '3'); escribir('txtMotivo', 'Hemograma previo');
  await submit('formOrden');
  var post = llamadas('POST', /\/api\/v1\/orden-analisis$/);
  var b = post.length ? JSON.parse(post[0].body) : {};
  r.post_con_id_tipo_analisis = post.length === 1 && b.id_tipo_analisis === '3' && !('id_tipo_estudio' in b) && b.motivo_orden === 'Hemograma previo';
  await cerrarSwal();
  f = filas();
  f[1].querySelector('[data-accion="avanzar"]').click(); await esperar(400);
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.avanzar_va_a_la_api_de_analisis = llamadas('PUT', /\/api\/v1\/orden-analisis\/52\/estado$/).length === 1;
  await cerrarSwal();
"""


def armar(nombre, esc):
    esc = dict(esc, nombre=nombre)
    with app.test_request_context('/'):
        session['id_usuario'] = 1; session['id_rol'] = 1; session['nombre_rol'] = 'Administrador'
        if esc['plantilla'] == 'orden-clinica-index.html':
            html = render_template('orden-clinica-index.html', cfg=dict(CFG[esc['cfg']], es_medico=esc['es_medico']))
        else:
            html = render_template(esc['plantilla'], es_medico=esc['es_medico'])
    html = html.replace('"/static/', '"' + STATIC)
    mock = MOCK % {'esc': json.dumps(esc), 'meds': json.dumps(MEDICAMENTOS), 'te': json.dumps(TIPOS_E), 'ta': json.dumps(TIPOS_A), 'dx': json.dumps(DIAGNOSTICOS), 'tr': json.dumps(TRATAMIENTOS)}
    html = html.replace('<head>', '<head>' + mock, 1)
    prueba = ('<pre id="resultado" style="display:none"></pre><script>(function () { (async function () { try {\n'
              'await new Promise(function (ok) { setTimeout(ok, 900); });\n' + COMUN + PRUEBAS[nombre] +
              '\nr.ninguna_url_con_id_no_numerico = sinIdsRaros(); r.sin_errores_al_final = window.__errores.length === 0; if (window.__errores.length) r.errores = window.__errores;\n'
              '} catch (e) { r.EXCEPCION = String(e && e.stack || e); } document.getElementById("resultado").textContent = JSON.stringify(r); })(); })();</script>')
    return html.replace('</body>', prueba + '</body>', 1)


total_fallos = 0
for nombre, esc in ESCENARIOS.items():
    archivo = SALIDA / f'{nombre}.html'
    archivo.write_text(armar(nombre, esc), encoding='utf-8')
    url = archivo.as_uri() + esc['url']
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
