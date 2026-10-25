"""Gestionar Tratamientos y Procedimientos e Insumos Utilizados (sesiones) en un navegador real (Edge headless) con fetch simulado.
Cada vista se renderiza con Flask (sesión de Administrador: todos los permisos del catálogo) pasando `es_medico` como lo haría la ruta, se reescribe /static a
file:// y se corre un script que usa el DOM, Bootstrap 5 y SweetAlert2 reales. El JSON simulado trae las claves ORDENADAS como Flask y las URL pedidas no pueden
llevar ids no numéricos.
Uso: .\\.venv\\Scripts\\python.exe -I tests\\consultorio\\browser_tratamiento.py <carpeta de salida>      (necesita Edge)
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


def consulta(numero='CON-0000018', estado='en_proceso', id_consulta=18):
    return ordenado({'id_consulta_cab': id_consulta, 'numero': numero, 'estado': estado, 'activo': True, 'id_paciente': 7, 'nombre_paciente': 'JAVIER ACOSTA',
                     'cedula_paciente': '5098745', 'id_medico': 20, 'nombre_medico': 'OSCAR GONZALES', 'fecha_cita': '2026-10-27', 'hora_cita': '09:00:00'})


def resumen(estado, cargar, id_consulta=18):
    return {'consulta': consulta('CON-%07d' % id_consulta, estado, id_consulta), 'contadores': {}, 'acciones': {'iniciar': False, 'finalizar': False, 'cancelar': False, 'cargar_clinico': cargar}}


def trat(i, tipo, estado, sesiones, id_consulta=17, estado_consulta='en_proceso', facturado=False):
    return ordenado({'id_tratamiento': i, 'id_consulta_cab': id_consulta, 'numero_consulta': 'CON-%07d' % id_consulta, 'estado_consulta': estado_consulta, 'id_diagnostico': None,
                     'id_paciente': 7, 'nombre_paciente': 'JAVIER ACOSTA', 'cedula_paciente': '5098745', 'id_medico': 20, 'nombre_medico': 'OSCAR GONZALES',
                     'id_consultorio': 1, 'nombre_consultorio': 'CONSULTORIO 1', 'id_tipo_tratamiento': 3, 'tipo_tratamiento': tipo,
                     'descripcion_tratamiento': 'Tratamiento de varias visitas ' + tipo, 'fecha_tratamiento': '2026-10-20', 'estado': estado,
                     'fecha_registro': '2026-10-20T09:30:00', 'cantidad_sesiones': sesiones, 'facturado': facturado, 'numero_factura': '001-001-0000005' if facturado else None})


def ses(i, numero, id_consulta, estado_consulta='en_proceso', insumos=True):
    return ordenado({'id_sesion': i, 'id_tratamiento': 9, 'id_consulta_cab': id_consulta, 'numero_consulta': 'CON-%07d' % id_consulta, 'estado_consulta': estado_consulta,
                     'numero_sesion': numero, 'fecha_sesion': '2026-10-2%d' % numero, 'descripcion_procedimiento': 'Se realizó el procedimiento ' + str(numero),
                     'observaciones': 'Sin complicaciones', 'proxima_cita': '2026-11-02' if numero == 1 else None, 'activo': True, 'fecha_registro': '2026-10-21T10:00:00',
                     'id_paciente': 7, 'nombre_paciente': 'JAVIER ACOSTA', 'cedula_paciente': '5098745', 'id_medico': 20, 'estado_tratamiento': 'en_seguimiento',
                     'tipo_tratamiento': 'ENDODONCIA',
                     'procedimientos': [ordenado({'id_tipo_procedimiento': 1, 'descripcion': 'LIMPIEZA DE CONDUCTOS'}), ordenado({'id_tipo_procedimiento': 2, 'descripcion': 'OBTURACIÓN'})],
                     'insumos': [ordenado({'id_sesion_insumo': 50 + i, 'id_insumo': 4, 'descripcion_insumo': 'GUANTES', 'cantidad': 2})] if insumos else []})


def detalle(estado='en_seguimiento', sesiones=None, estado_consulta_origen='finalizada', facturado=False):
    t = trat(9, 'ENDODONCIA', estado, len(sesiones or []), 17, estado_consulta_origen, facturado)
    t['sesiones'] = sesiones or []
    return t


SESIONES = [ses(61, 1, 17, 'finalizada'), ses(62, 2, 18, 'en_proceso', insumos=False)]
TRAT_PROPIOS = [trat(31, 'LIMPIEZA DENTAL', 'pendiente', 0, 18), trat(32, 'BLANQUEAMIENTO', 'en_seguimiento', 1, 18), trat(33, 'CORONA', 'pendiente', 0, 18, facturado=True)]
TRAT_OTROS = [trat(9, 'ENDODONCIA', 'en_seguimiento', 2, 17, 'finalizada')]
TRAT_GLOBAL = [trat(9, 'ENDODONCIA', 'en_seguimiento', 2, 17, 'en_proceso'), trat(31, 'LIMPIEZA DENTAL', 'pendiente', 0, 18), trat(34, 'EXTRACCIÓN', 'finalizado', 1, 15, 'finalizada')]
TIPOS = [ordenado({'id_tipo_tratamiento': 3, 'descripcion': 'ENDODONCIA', 'activo': True}), ordenado({'id_tipo_tratamiento': 4, 'descripcion': 'LIMPIEZA DENTAL', 'activo': True})]
DIAGNOSTICOS = [ordenado({'id_diagnostico': 7, 'codigo': 'DX-0007', 'tipo_diagnostico': 'CARIES', 'pieza_dental': '18'})]
PROCEDIMIENTOS = [ordenado({'id_tipo_procedimiento': 1, 'descripcion': 'LIMPIEZA DE CONDUCTOS', 'activo': True}), ordenado({'id_tipo_procedimiento': 2, 'descripcion': 'OBTURACIÓN', 'activo': True}),
                  ordenado({'id_tipo_procedimiento': 3, 'descripcion': 'PROFILAXIS', 'activo': True})]
INSUMOS = [ordenado({'id_insumo': 4, 'descripcion': 'GUANTES', 'presentacion': 'CAJA X 100', 'activo': True}), ordenado({'id_insumo': 5, 'descripcion': 'ANESTESIA', 'presentacion': None, 'activo': True})]

ESCENARIOS = {
    'tr_listado': dict(plantilla='tratamiento-index.html', es_medico=True, url='', lista=TRAT_GLOBAL, total=31, detalle=detalle(sesiones=SESIONES)),
    'tr_consulta': dict(plantilla='tratamiento-index.html', es_medico=True, url='?consulta=18', resumen=resumen('en_proceso', True), propios=TRAT_PROPIOS, otros=TRAT_OTROS,
                        detalle=detalle(sesiones=SESIONES)),
    'tr_consulta_rechazo': dict(plantilla='tratamiento-index.html', es_medico=True, url='?consulta=18', resumen=resumen('en_proceso', True), propios=TRAT_PROPIOS, otros=TRAT_OTROS,
                                detalle=detalle(sesiones=SESIONES), rechazo={'campo': 'id_tipo_tratamiento', 'error': 'El tipo de tratamiento seleccionado está inactivo.'}),
    'tr_lectura': dict(plantilla='tratamiento-index.html', es_medico=False, url='?consulta=18', resumen=resumen('finalizada', False), propios=TRAT_PROPIOS, otros=TRAT_OTROS,
                       detalle=detalle(sesiones=SESIONES)),
    'se_editor': dict(plantilla='sesion-tratamiento-index.html', es_medico=True, url='?tratamiento=9&consulta=18', resumen=resumen('en_proceso', True),
                      detalle=detalle(sesiones=SESIONES), sesion=SESIONES[1], rechazo={'campo': 'insumos', 'error': 'Hay insumos inactivos: GUANTES. Quítelos de la selección.'}),
    'se_ok': dict(plantilla='sesion-tratamiento-index.html', es_medico=True, url='?tratamiento=9&consulta=18', resumen=resumen('en_proceso', True),
                  detalle=detalle(sesiones=SESIONES), sesion=SESIONES[1]),
    'se_consulta_cerrada': dict(plantilla='sesion-tratamiento-index.html', es_medico=True, url='?tratamiento=9&consulta=18', resumen=resumen('finalizada', False),
                                detalle=detalle(sesiones=[ses(61, 1, 17, 'finalizada'), ses(62, 2, 18, 'finalizada')]), sesion=SESIONES[1]),
    'se_otra_consulta': dict(plantilla='sesion-tratamiento-index.html', es_medico=True, url='?tratamiento=9&consulta=19',
                             resumen={**resumen('en_proceso', True, 19), 'consulta': {**resumen('en_proceso', True, 19)['consulta'], 'id_paciente': 99}},
                             detalle=detalle(sesiones=SESIONES), sesion=SESIONES[1]),
    'se_lectura': dict(plantilla='sesion-tratamiento-index.html', es_medico=False, url='?tratamiento=9', resumen=None, detalle=detalle(sesiones=SESIONES), sesion=SESIONES[1]),
    'se_finalizado': dict(plantilla='sesion-tratamiento-index.html', es_medico=True, url='?tratamiento=9&consulta=18', resumen=resumen('en_proceso', True),
                          detalle=detalle('finalizado', SESIONES), sesion=SESIONES[1]),
    'se_sin_tratamiento': dict(plantilla='sesion-tratamiento-index.html', es_medico=True, url='', resumen=None, detalle=None, sesion=None),
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
    else if (/\/api\/v1\/tratamientos\/\d+$/.test(path)) cuerpo.data = E.detalle;
    else if (/\/api\/v1\/tratamientos$/.test(path)) {
      if (/consulta=\d+/.test(url)) cuerpo.data = E.propios;
      else if (/paciente=\d+/.test(url)) cuerpo.data = E.otros;
      else { cuerpo.data = E.lista; cuerpo.total = E.total; }
      if (cuerpo.total === undefined) cuerpo.total = cuerpo.data.length;
    }
    else if (/\/api\/v1\/sesiones-tratamiento\/\d+$/.test(path)) cuerpo.data = E.sesion;
    else if (/\/api\/v1\/tipos-tratamiento$/.test(path)) cuerpo.data = %(tipos)s;
    else if (/\/api\/v1\/diagnosticos-medicos\/consulta\/\d+$/.test(path)) cuerpo.data = %(dx)s;
    else if (/\/api\/v1\/tipos-procedimiento-medico$/.test(path)) cuerpo.data = %(proc)s;
    else if (/\/api\/v1\/tipos-insumo$/.test(path)) cuerpo.data = %(ins)s;
  } else if (metodo === 'POST') {
    if (E.rechazo) { cuerpo = {success: false, data: null, error: E.rechazo.error, campo: E.rechazo.campo}; status = 409; }
    else if (/\/api\/v1\/tratamientos$/.test(path)) { cuerpo.data = {id_tratamiento: 77}; cuerpo.mensaje = 'Tratamiento de ENDODONCIA registrado correctamente.'; status = 201; }
    else if (/\/api\/v1\/sesiones-tratamiento$/.test(path)) { cuerpo.data = {id_sesion: 88, numero_sesion: 3}; cuerpo.mensaje = 'Sesión 3 del tratamiento de ENDODONCIA registrada correctamente.'; status = 201; }
  } else if (metodo === 'PUT') { cuerpo.mensaje = 'Tratamiento de ENDODONCIA finalizado correctamente.'; }
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
"""

PRUEBAS = {}

PRUEBAS['tr_listado'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  var filas = Array.prototype.slice.call($('tbodyGlobal').querySelectorAll('tr'));
  r.tres_filas = filas.length === 3;
  r.fila_con_paciente_tipo_consulta_sesiones_y_estado = /JAVIER ACOSTA/.test(filas[0].textContent) && /CI 5098745/.test(filas[0].textContent) && /ENDODONCIA/.test(filas[0].textContent)
    && /CON-0000017/.test(filas[0].textContent) && /En seguimiento/.test(filas[0].textContent) && filas[0].querySelectorAll('td')[5].textContent.trim() === '2';
  r.enlace_a_la_consulta_con_id_numerico = filas[0].querySelector('a[href^="/referenciales/consulta/consulta-detalle/"]').getAttribute('href') === '/referenciales/consulta/consulta-detalle/17';
  r.enlace_a_sesiones_sin_consulta = filas[0].querySelector('a[href*="sesion-tratamiento-index"]').getAttribute('href') === '/referenciales/sesion-tratamiento/sesion-tratamiento-index?tratamiento=9';
  r.finalizar_solo_en_seguimiento = !!filas[0].querySelector('[data-accion="finalizar"]') && !filas[1].querySelector('[data-accion="finalizar"]') && !filas[2].querySelector('[data-accion="finalizar"]');
  r.anular_solo_si_no_tiene_sesiones_y_la_consulta_esta_abierta = !filas[0].querySelector('[data-accion="anular"]') && !!filas[1].querySelector('[data-accion="anular"]') && !filas[2].querySelector('[data-accion="anular"]');
  r.sin_boton_nuevo_fuera_de_la_consulta = !visible('btnNuevo');
  r.info_paginacion = /Mostrando 1–15 de 31/.test(txt('infoPagina'));
  escribir('filtroEstado', 'pendiente'); await esperar(500);
  r.filtro_estado_va_al_servidor = llamadas('GET', /estado=pendiente/).length === 1;
  var fq = $('filtroQ'); fq.value = 'acosta'; fq.dispatchEvent(new Event('input', {bubbles: true})); await esperar(700);
  r.filtro_texto_con_espera = llamadas('GET', /q=acosta/).length === 1;
  $('btnLimpiar').click(); await esperar(400);
  filas = Array.prototype.slice.call($('tbodyGlobal').querySelectorAll('tr'));
  filas[0].querySelector('[data-accion="ver"]').click(); await esperar(600);
  r.ver_abre_con_el_detalle_y_las_sesiones = $('modalVer').classList.contains('show') && /Tratamiento de ENDODONCIA/.test(txt('verTitulo')) && /Sesiones \(2\)/.test(txt('verCuerpo'))
    && /LIMPIEZA DE CONDUCTOS/.test(txt('verCuerpo')) && /CON-0000018/.test(txt('verCuerpo')) && /Tratamiento de varias visitas/.test(txt('verCuerpo'));
  r.ver_pidio_el_id_numerico = llamadas('GET', /\/api\/v1\/tratamientos\/9$/).length === 1;
  $('modalVer').querySelector('[data-bs-dismiss="modal"]').click(); await esperar(600);
  filas = Array.prototype.slice.call($('tbodyGlobal').querySelectorAll('tr'));
  filas[1].querySelector('[data-accion="anular"]').click(); await esperar(400);
  r.anular_pide_confirmacion = !!document.querySelector('.swal2-popup') && /Anular este tratamiento/.test(document.querySelector('.swal2-popup').textContent) && llamadas('DELETE', /./).length === 0;
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.anular_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/tratamientos\/31$/).length === 1;
  await cerrarSwal();
  filas = Array.prototype.slice.call($('tbodyGlobal').querySelectorAll('tr'));
  filas[0].querySelector('[data-accion="finalizar"]').click(); await esperar(400);
  r.finalizar_pide_confirmacion = !!document.querySelector('.swal2-popup') && /Finalizar este tratamiento/.test(document.querySelector('.swal2-popup').textContent) && llamadas('PUT', /./).length === 0;
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.finalizar_hace_put_al_id_numerico = llamadas('PUT', /\/api\/v1\/tratamientos\/9\/finalizar$/).length === 1;
  await cerrarSwal();
"""

_ALTA = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.tarjeta_de_la_consulta = visible('tarjetaConsulta') && txt('cNumero') === 'CON-0000018' && /JAVIER ACOSTA/.test(txt('cDetalle')) && /En proceso/.test(txt('cBadge'));
  r.volver_a_la_consulta = visible('btnVolverConsulta') && $('btnVolverConsulta').getAttribute('href') === '/referenciales/consulta/consulta-detalle/18';
  var propios = Array.prototype.slice.call($('tbodyConsulta').querySelectorAll('tr'));
  r.propios_tres = propios.length === 3 && /LIMPIEZA DENTAL/.test(propios[0].textContent) && /Pendiente/.test(propios[0].textContent);
  r.el_facturado_no_se_anula = !propios[2].querySelector('[data-accion="anular"]') && !!propios[0].querySelector('[data-accion="anular"]') && !propios[1].querySelector('[data-accion="anular"]');
  var otros = Array.prototype.slice.call($('tbodyOtros').querySelectorAll('tr'));
  r.en_curso_del_paciente_de_otra_consulta = otros.length === 1 && /ENDODONCIA/.test(otros[0].textContent) && /CON-0000017/.test(otros[0].textContent) && /En seguimiento/.test(otros[0].textContent);
  r.pidio_los_en_curso_del_paciente_con_id_numerico = llamadas('GET', /\/api\/v1\/tratamientos\?paciente=7&en_curso=1/).length === 1;
  r.registrar_sesion_en_esta_consulta = otros[0].querySelector('a[href*="sesion-tratamiento-index"]').getAttribute('href') === '/referenciales/sesion-tratamiento/sesion-tratamiento-index?tratamiento=9&consulta=18'
    && /Registrar sesión en esta consulta/.test(otros[0].querySelector('a[href*="sesion-tratamiento-index"]').getAttribute('title'));
  r.finalizar_tambien_desde_los_otros = !!otros[0].querySelector('[data-accion="finalizar"]');
  r.sin_anular_en_otra_consulta_con_sesiones = !otros[0].querySelector('[data-accion="anular"]');
  r.boton_nuevo_visible = visible('btnNuevo');
  $('btnNuevo').click(); await esperar(900);
  var modal = $('modalNuevo');
  r.modal_abre_con_tipos_diagnosticos_y_fecha_de_hoy = modal.classList.contains('show') && $('selTipo').options.length === 3 && $('selDiagnostico').options.length === 2
    && /^\d{4}-\d{2}-\d{2}$/.test($('txtFecha').value) && $('txtFecha').max === $('txtFecha').value;
  r.el_diagnostico_se_ve_con_codigo_y_pieza = /DX-0007/.test($('selDiagnostico').options[1].textContent) && /pieza 18/.test($('selDiagnostico').options[1].textContent);
  var hoyTxt = $('txtFecha').value;
  escribir('txtFecha', '');
  await submit('formTr');
  r.vacio_no_envia = llamadas('POST', /./).length === 0;
  r.vacio_marca_tipo_y_descripcion = $('selTipo').classList.contains('is-invalid') && /obligatorio/.test(fb('selTipo')) && $('txtDescripcion').classList.contains('is-invalid') && /obligatoria/.test(fb('txtDescripcion'));
  escribir('txtFecha', '2099-01-01'); escribir('selTipo', '3'); escribir('txtDescripcion', 'Conducto del 18');
  await submit('formTr');
  r.fecha_futura_se_rechaza_en_el_formulario = $('txtFecha').classList.contains('is-invalid') && /futura/.test(fb('txtFecha')) && llamadas('POST', /./).length === 0;
  escribir('txtFecha', hoyTxt); escribir('selDiagnostico', '7');
"""

PRUEBAS['tr_consulta'] = _ALTA + r"""
  await submit('formTr');
  var post = llamadas('POST', /\/api\/v1\/tratamientos$/);
  r.un_post = post.length === 1;
  var b = post.length ? JSON.parse(post[0].body) : {};
  r.post_lleva_consulta_tipo_descripcion_fecha_y_diagnostico = b.id_consulta_cab === 18 && b.id_tipo_tratamiento === '3' && b.descripcion_tratamiento === 'Conducto del 18' && b.fecha_tratamiento === hoyTxt && b.id_diagnostico === '7';
  r.post_no_manda_paciente_medico_ni_estado = !('id_paciente' in b) && !('id_medico' in b) && !('estado' in b) && !('id_consultorio' in b);
  r.exito = !!document.querySelector('.swal2-popup') && /registrado correctamente/.test(document.querySelector('.swal2-popup').textContent);
  await cerrarSwal();
  r.cierra_el_modal_y_recarga = !$('modalNuevo').classList.contains('show') && llamadas('GET', /\/api\/v1\/tratamientos\?consulta=18/).length >= 2;
  var filas = $('tbodyConsulta').querySelectorAll('tr');
  filas[0].querySelector('[data-accion="anular"]').click(); await esperar(400);
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.anular_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/tratamientos\/31$/).length === 1;
  await cerrarSwal();
"""

PRUEBAS['tr_consulta_rechazo'] = _ALTA + r"""
  await submit('formTr');
  r.el_servidor_rechaza_y_el_error_va_al_campo = $('selTipo').classList.contains('is-invalid') && /inactivo/.test(fb('selTipo'));
  r.el_modal_sigue_abierto_y_el_boton_se_rehabilita = $('modalNuevo').classList.contains('show') && !$('btnGuardar').disabled;
  r.no_se_mostro_exito = !document.querySelector('.swal2-popup');
"""

PRUEBAS['tr_lectura'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.sin_boton_nuevo_ni_formulario = !$('btnNuevo') && !$('formTr');
  r.aviso_de_consulta_cerrada = /Finalizada/.test(txt('cBadge')) && /solo lectura/.test(txt('cAviso'));
  var propios = $('tbodyConsulta').querySelectorAll('tr');
  r.tres_tratamientos = propios.length === 3;
  r.sin_botones_de_anular_ni_finalizar = !document.querySelector('[data-accion="anular"]') && !document.querySelector('[data-accion="finalizar"]');
  r.ver_si = !!propios[0].querySelector('[data-accion="ver"]');
  var otros = $('tbodyOtros').querySelectorAll('tr');
  r.los_otros_solo_tienen_sesiones_para_consultar = /Sesiones/.test(otros[0].querySelector('a[href*="sesion-tratamiento-index"]').getAttribute('title')) && !/Registrar/.test(otros[0].querySelector('a[href*="sesion-tratamiento-index"]').getAttribute('title'));
  propios[0].querySelector('[data-accion="ver"]').click(); await esperar(600);
  r.ver_abre = $('modalVer').classList.contains('show');
"""

_ABRIR_SES = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.tarjeta_del_tratamiento = txt('tTipo') === 'ENDODONCIA' && /En seguimiento/.test(txt('tBadge')) && /JAVIER ACOSTA/.test($('tDetalle').textContent) && /CON-0000017/.test($('tDetalle').innerHTML);
  r.pidio_el_tratamiento_con_id_numerico = llamadas('GET', /\/api\/v1\/tratamientos\/9$/).length >= 1;
  r.tarjeta_de_la_consulta_de_registro = visible('tarjetaConsulta') && txt('cNumero') === 'CON-0000018' && /En proceso/.test(txt('cBadge'));
  r.volver_a_la_consulta = $('btnVolver').getAttribute('href') === '/referenciales/consulta/consulta-detalle/18' && /Volver a la consulta/.test(txt('txtVolver'));
  var filas = Array.prototype.slice.call($('tbodySesiones').querySelectorAll('tr'));
  r.dos_sesiones_con_consulta_procedimientos_e_insumos = filas.length === 2 && /CON-0000017/.test(filas[0].textContent) && /CON-0000018/.test(filas[1].textContent)
    && /LIMPIEZA DE CONDUCTOS/.test(filas[0].textContent) && /GUANTES × 2/.test(filas[0].textContent) && /OBTURACIÓN/.test(filas[1].textContent);
  r.una_sesion_sin_insumos_muestra_guion = !/GUANTES/.test(filas[1].textContent);
  r.cantidad_de_sesiones = /\(2\)/.test(txt('cantidadSesiones'));
  r.solo_la_ultima_se_anula = !filas[0].querySelector('[data-accion="anular"]') && !!filas[1].querySelector('[data-accion="anular"]');
"""

PRUEBAS['se_editor'] = _ABRIR_SES + r"""
  r.finalizar_visible_en_seguimiento = visible('btnFinalizar');
  r.nueva_sesion_visible = visible('btnNuevo');
  filas[0].querySelector('[data-accion="ver"]').click(); await esperar(600);
  r.ver_abre_con_todo = $('modalVer').classList.contains('show') && /Sesión 2/.test(txt('verTitulo')) && /Se realizó el procedimiento 2/.test(txt('verCuerpo')) && /Sin complicaciones/.test(txt('verCuerpo'));
  r.ver_pidio_el_id_numerico = llamadas('GET', /\/api\/v1\/sesiones-tratamiento\/61$/).length === 1;
  $('modalVer').querySelector('[data-bs-dismiss="modal"]').click(); await esperar(600);
  $('btnNuevo').click(); await esperar(900);
  r.modal_abre_con_procedimientos_e_insumos_cargados = $('modalNuevo').classList.contains('show') && $('listaProcedimientos').querySelectorAll('input[type=checkbox]').length === 3
    && $('filasInsumos').querySelectorAll('.fila-insumo').length === 0;
  await submit('formSes');
  r.vacio_no_envia_y_marca = llamadas('POST', /./).length === 0 && visible('errProcedimientos') && /al menos un procedimiento/.test(txt('errProcedimientos'))
    && $('txtDescripcion').classList.contains('is-invalid') && /obligatoria/.test(fb('txtDescripcion'));
  escribir('txtBuscarProc', 'prof'); r.buscador_filtra_procedimientos = $('listaProcedimientos').querySelectorAll('input[type=checkbox]').length === 1;
  escribir('txtBuscarProc', '');
  var cbs = $('listaProcedimientos').querySelectorAll('input[type=checkbox]');
  cbs[0].checked = true; cbs[0].dispatchEvent(new Event('change', {bubbles: true}));
  cbs[2].checked = true; cbs[2].dispatchEvent(new Event('change', {bubbles: true}));
  r.contador_de_procedimientos = /2 elegidos/.test(txt('contadorProc')) && !visible('errProcedimientos');
  escribir('txtDescripcion', 'Se limpió el conducto');
  // insumos
  $('btnAgregarInsumo').click(); $('btnAgregarInsumo').click();
  var f = $('filasInsumos').querySelectorAll('.fila-insumo');
  r.agregar_dos_filas_de_insumo = f.length === 2 && f[0].querySelector('select').options.length === 3 && /CAJA X 100/.test(f[0].querySelector('select').options[1].textContent);
  f[0].querySelector('select').value = '4'; f[0].querySelector('[data-campo="cantidad"]').value = '0';
  f[1].querySelector('select').value = '4'; f[1].querySelector('[data-campo="cantidad"]').value = '3';
  await submit('formSes');
  r.cantidad_cero_se_rechaza_en_el_formulario = visible('errInsumos') && /de 1 a 999/.test(txt('errInsumos')) && llamadas('POST', /./).length === 0;
  f[0].querySelector('[data-campo="cantidad"]').value = '2';
  await submit('formSes');
  r.insumo_repetido_se_rechaza_en_el_formulario = visible('errInsumos') && /No repita el mismo insumo/.test(txt('errInsumos')) && llamadas('POST', /./).length === 0;
  f[1].querySelector('[data-quitar]').click();
  r.quitar_una_fila = $('filasInsumos').querySelectorAll('.fila-insumo').length === 1 && !visible('errInsumos');
  escribir('txtProxima', '2000-01-01');
  await submit('formSes');
  r.proxima_cita_pasada_se_rechaza = $('txtProxima').classList.contains('is-invalid') && /anterior a hoy/.test(fb('txtProxima')) && llamadas('POST', /./).length === 0;
  escribir('txtProxima', '');
  await submit('formSes');
  var post = llamadas('POST', /\/api\/v1\/sesiones-tratamiento$/);
  var b = post.length ? JSON.parse(post[0].body) : {};
  r.un_post_con_tratamiento_consulta_procedimientos_e_insumos = post.length === 1 && b.id_tratamiento === 9 && b.id_consulta_cab === 18 && JSON.stringify(b.procedimientos) === '[1,3]'
    && b.descripcion_procedimiento === 'Se limpió el conducto' && b.insumos.length === 1 && b.insumos[0].id_insumo === '4' && b.insumos[0].cantidad === '2';
  r.post_no_manda_numero_ni_fecha = !('numero_sesion' in b) && !('fecha_sesion' in b);
  r.error_del_servidor_en_el_campo_insumos = visible('errInsumos') && /inactivos/.test(txt('errInsumos')) && $('modalNuevo').classList.contains('show') && !$('btnGuardar').disabled;
"""

PRUEBAS['se_ok'] = _ABRIR_SES + r"""
  $('btnNuevo').click(); await esperar(900);
  var cbs = $('listaProcedimientos').querySelectorAll('input[type=checkbox]');
  cbs[1].checked = true; cbs[1].dispatchEvent(new Event('change', {bubbles: true}));
  escribir('txtDescripcion', 'Sesión de obturación');
  await submit('formSes');
  var post = llamadas('POST', /\/api\/v1\/sesiones-tratamiento$/);
  r.alta_sin_insumos_es_valida = post.length === 1 && JSON.parse(post[0].body).insumos.length === 0;
  r.exito = !!document.querySelector('.swal2-popup') && /Sesión 3/.test(document.querySelector('.swal2-popup').textContent);
  await cerrarSwal();
  r.recarga_el_tratamiento = !$('modalNuevo').classList.contains('show') && llamadas('GET', /\/api\/v1\/tratamientos\/9$/).length >= 2;
  $('tbodySesiones').querySelectorAll('tr')[1].querySelector('[data-accion="anular"]').click(); await esperar(400);
  r.anular_avisa_que_es_definitiva = !!document.querySelector('.swal2-popup') && /definitiva/.test(document.querySelector('.swal2-popup').textContent) && llamadas('DELETE', /./).length === 0;
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.anular_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/sesiones-tratamiento\/62$/).length === 1;
  await cerrarSwal();
  $('btnFinalizar').click(); await esperar(400);
  r.finalizar_pide_confirmacion = !!document.querySelector('.swal2-popup') && /Finalizar este tratamiento/.test(document.querySelector('.swal2-popup').textContent) && llamadas('PUT', /./).length === 0;
  document.querySelector('.swal2-confirm').click(); await esperar(700);
  r.finalizar_hace_put_al_id_numerico = llamadas('PUT', /\/api\/v1\/tratamientos\/9\/finalizar$/).length === 1;
  await cerrarSwal();
"""

PRUEBAS['se_consulta_cerrada'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.aviso_de_consulta_cerrada = /cerrada/.test(txt('cAviso'));
  r.sin_nueva_sesion = !visible('btnNuevo');
  r.sin_anular_porque_la_consulta_de_la_sesion_esta_finalizada = !document.querySelector('[data-accion="anular"]');
  r.se_pueden_ver_las_sesiones = $('tbodySesiones').querySelectorAll('[data-accion="ver"]').length === 2;
  r.finalizar_sigue_disponible = visible('btnFinalizar');
"""

PRUEBAS['se_otra_consulta'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.aviso_de_que_no_es_el_mismo_paciente = /mismo paciente y médico/.test(txt('cAviso'));
  r.sin_nueva_sesion = !visible('btnNuevo');
"""

PRUEBAS['se_lectura'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.sin_botones_ni_formulario = !$('btnNuevo') && !$('btnFinalizar') && !$('formSes');
  r.sin_tarjeta_de_consulta = !visible('tarjetaConsulta');
  r.volver_a_tratamientos = $('btnVolver').getAttribute('href') === '/referenciales/tratamiento/tratamiento-index' && /Volver a tratamientos/.test(txt('txtVolver'));
  var filas = $('tbodySesiones').querySelectorAll('tr');
  r.dos_sesiones_solo_lectura = filas.length === 2 && !document.querySelector('[data-accion="anular"]') && filas[0].querySelectorAll('[data-accion="ver"]').length === 1;
"""

PRUEBAS['se_finalizado'] = r"""
  r.sin_errores_al_cargar = window.__errores.length === 0;
  r.tratamiento_finalizado = /Finalizado/.test(txt('tBadge'));
  r.sin_nueva_sesion_ni_finalizar = !visible('btnNuevo') && !visible('btnFinalizar');
  r.sin_anular_sesiones = !document.querySelector('[data-accion="anular"]');
"""

PRUEBAS['se_sin_tratamiento'] = r"""
  r.sin_errores = window.__errores.length === 0;
  r.pide_elegir_un_tratamiento = visible('sinTratamiento') && /Gestionar Tratamientos/.test(txt('sinTratamiento')) && !visible('contenedor');
  r.no_pidio_nada_al_servidor = window.__calls.length === 0;
"""


def armar(nombre, esc):
    esc = dict(esc, nombre=nombre)
    with app.test_request_context('/'):
        session['id_usuario'] = 1; session['id_rol'] = 1; session['nombre_rol'] = 'Administrador'
        html = render_template(esc['plantilla'], es_medico=esc['es_medico'])
    html = html.replace('"/static/', '"' + STATIC)
    mock = MOCK % {'esc': json.dumps(esc), 'tipos': json.dumps(TIPOS), 'dx': json.dumps(DIAGNOSTICOS), 'proc': json.dumps(PROCEDIMIENTOS), 'ins': json.dumps(INSUMOS)}
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
