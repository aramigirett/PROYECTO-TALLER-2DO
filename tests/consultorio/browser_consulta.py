"""Registrar Consulta, Atención de la consulta (con la Ficha Médica) y Fichas Médicas en un navegador real (Edge headless) con fetch simulado.
Renderiza cada vista con Flask (sesión de Administrador: ve todos los botones; qué puede hacer cada rol lo da la API, que acá se simula con los
escenarios), reescribe /static a file:// y corre un script que usa el DOM, Bootstrap 5 y SweetAlert2 reales.
El JSON simulado trae las claves ORDENADAS como Flask (la primera es `activo`, nunca el id) y las URL pedidas no pueden llevar ids no numéricos.
Uso: .\\.venv\\Scripts\\python.exe -I tests\\consultorio\\browser_consulta.py <carpeta de salida>      (necesita Edge)
"""
import html as _h
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app import app

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SALIDA = pathlib.Path(sys.argv[1])
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
STATIC = (RAIZ / 'app' / 'static').as_uri() + '/'
SALIDA.mkdir(parents=True, exist_ok=True)


def ordenado(d):
    return {k: d[k] for k in sorted(d)}


def consulta(id_, estado='programada', **kw):
    return ordenado({'id_consulta_cab': id_, 'numero': f'CON-{id_:07d}', 'estado': estado, 'activo': True, 'id_cita': 500 + id_,
                     'id_paciente': 7, 'nombre_paciente': 'JAVIER ACOSTA', 'cedula_paciente': '5098745', 'id_medico': 20, 'nombre_medico': 'OSCAR GONZALES',
                     'id_consultorio': 2, 'nombre_consultorio': 'CONSULTORIO CENTRAL', 'id_funcionario': 4, 'nombre_funcionario': 'ROCÍO CABRERA',
                     'fecha_cita': '2026-10-26', 'hora_cita': '09:00:00', 'duracion_minutos': kw.get('duracion'), 'fecha_registro': '2026-10-26T08:15:00',
                     'tiene_ficha': kw.get('tiene_ficha', False)})


FICHA = ordenado({'id_ficha_medica': 31, 'id_consulta_cab': 17, 'presion_arterial': '120/80', 'temperatura': 36.5, 'frecuencia_cardiaca': 72,
                  'frecuencia_respiratoria': 16, 'peso': 70.0, 'talla': 175.0, 'imc': 22.86, 'examen_fisico_general': 'Sin hallazgos',
                  'examen_bucal': 'Caries en 36', 'observaciones_medico': None, 'fecha_registro': '2026-10-26T09:10:00'})
CONT0 = {'ficha': 0, 'diagnosticos': 0, 'odontogramas': 0, 'tratamientos': 0, 'recetas': 0, 'ordenes_estudio': 0, 'ordenes_analisis': 0, 'justificativos': 0}


def resumen(estado, acciones, contadores=None, ficha=False):
    c = dict(CONT0, **(contadores or {}))
    if ficha:
        c['ficha'] = 1
    return {'consulta': consulta(17, estado), 'contadores': c, 'acciones': acciones}


ESCENARIOS = {
    # ---- listado ----
    'listado': dict(
        pagina='consulta-index',
        lista=[consulta(11), consulta(12, 'en_proceso', duracion=30), consulta(13, 'finalizada', duracion=45, tiene_ficha=True)],
        total=31,
        kpis={'hoy': 4, 'programadas': 5, 'en_proceso': 2, 'finalizadas': 20, 'canceladas': 1, 'total': 28},
        citas=[ordenado({'id_cita_detalle': 253, 'fecha_cita': '2026-10-26', 'hora_cita': '09:00:00', 'motivo_consulta': 'Control', 'id_paciente': 7,
                         'paciente_nombre': 'JAVIER ACOSTA', 'cedula_paciente': '5098745', 'id_medico': 20, 'medico_nombre': 'OSCAR GONZALES',
                         'id_consultorio': 2, 'nombre_consultorio': 'CONSULTORIO CENTRAL'}),
               ordenado({'id_cita_detalle': 254, 'fecha_cita': '2026-10-26', 'hora_cita': '09:30:00', 'motivo_consulta': 'Dolor', 'id_paciente': 7,
                         'paciente_nombre': 'JAVIER ACOSTA', 'cedula_paciente': '5098745', 'id_medico': 20, 'medico_nombre': 'OSCAR GONZALES',
                         'id_consultorio': 2, 'nombre_consultorio': 'CONSULTORIO CENTRAL'})]),
    # ---- atención de la consulta ----
    'medico_programada': dict(pagina='consulta-detalle', resumen=resumen('programada', {'iniciar': True, 'finalizar': False, 'cancelar': True, 'cargar_clinico': True})),
    'medico_con_ficha': dict(pagina='consulta-detalle', ficha=FICHA, resumen=resumen('en_proceso', {'iniciar': False, 'finalizar': True, 'cancelar': True, 'cargar_clinico': True},
                                                                                      {'diagnosticos': 2, 'tratamientos': 1}, ficha=True)),
    'recepcion': dict(pagina='consulta-detalle', ficha=FICHA, resumen=resumen('programada', {'iniciar': False, 'finalizar': False, 'cancelar': True, 'cargar_clinico': False}, ficha=True)),
    'finalizada': dict(pagina='consulta-detalle', ficha=FICHA, resumen=resumen('finalizada', {'iniciar': False, 'finalizar': False, 'cancelar': False, 'cargar_clinico': False}, ficha=True)),
    # ---- fichas ----
    'fichas': dict(pagina='ficha-medica-index', total=2, lista=[
        ordenado({'id_ficha_medica': 31, 'id_consulta_cab': 17, 'numero_consulta': 'CON-0000017', 'fecha_consulta': '2026-10-26', 'estado_consulta': 'en_proceso',
                  'nombre_paciente': 'JAVIER ACOSTA', 'cedula_paciente': '5098745', 'id_medico': 20, 'nombre_medico': 'OSCAR GONZALES',
                  'fecha_registro': '2026-10-26T09:10:00', 'datos_cargados': 6}),
        ordenado({'id_ficha_medica': 32, 'id_consulta_cab': 18, 'numero_consulta': 'CON-0000018', 'fecha_consulta': '2026-10-25', 'estado_consulta': 'finalizada',
                  'nombre_paciente': 'ANA PEREZ', 'cedula_paciente': '1234567', 'id_medico': 20, 'nombre_medico': 'OSCAR GONZALES',
                  'fecha_registro': '2026-10-25T10:00:00', 'datos_cargados': 3})]),
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
  var E = window.__ESC, ok = true, status = 200;
  var cuerpo = {success: true, data: null, error: null, mensaje: 'Operación simulada.'};
  var path = url.split('?')[0];
  if (metodo === 'GET') {
    if (/\/api\/v1\/consultas\/indicadores$/.test(path)) cuerpo.data = E.kpis;
    else if (/\/api\/v1\/consultas\/citas-disponibles$/.test(path)) cuerpo.data = E.citas;
    else if (/\/api\/v1\/consultas\/\d+\/resumen$/.test(path)) cuerpo.data = E.resumen;
    else if (/\/api\/v1\/ficha-medica\/consulta\/\d+$/.test(path)) cuerpo.data = E.ficha;
    else if (/\/api\/v1\/(consultas|ficha-medica)$/.test(path)) { cuerpo.data = E.lista; cuerpo.total = E.total || E.lista.length; }
  } else if (metodo === 'POST' && /\/api\/v1\/consultas$/.test(path)) {
    cuerpo.data = {id_consulta_cab: 99, numero: 'CON-0000099'}; cuerpo.mensaje = 'Consulta CON-0000099 de JAVIER ACOSTA registrada correctamente.'; status = 201;
  } else if (metodo === 'POST' && /\/api\/v1\/ficha-medica$/.test(path)) { cuerpo.data = {id_ficha_medica: 31, imc: 22.86}; status = 201; }
  return Promise.resolve({ok: ok, status: status, json: function () { return Promise.resolve(cuerpo); }});
};
</script>
"""

PRUEBA_LISTADO = r"""
<pre id="resultado" style="display:none"></pre>
<script>
(function () {
  var r = {}; var esperar = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };
  var llamadas = function (m, re) { return window.__calls.filter(function (c) { return c.method === m && re.test(c.url); }); };
  var txt = function (id) { return (document.getElementById(id).textContent || '').trim(); };
  var filas = function () { return Array.prototype.slice.call(document.querySelectorAll('#tbodyConsultas tr')); };
  (async function () {
    try {
      await esperar(700);
      r.sin_errores_al_cargar = window.__errores.length === 0;
      r.kpis = txt('kpiHoy') === '4' && txt('kpiProgramadas') === '5' && txt('kpiEnProceso') === '2' && txt('kpiFinalizadas') === '20';
      r.tres_filas = filas().length === 3;
      var primera = filas()[0];
      r.fila_con_numero_paciente_y_ci = /CON-0000011/.test(primera.textContent) && /JAVIER ACOSTA/.test(primera.textContent) && /CI 5098745/.test(primera.textContent);
      r.badges = /Programada/.test(filas()[0].textContent) && /En proceso/.test(filas()[1].textContent) && /Finalizada/.test(filas()[2].textContent);
      r.ficha_marcada_solo_en_la_tercera = !filas()[0].querySelector('.fa-check-circle') && !!filas()[2].querySelector('.fa-check-circle');
      r.abrir_apunta_al_detalle_con_id_numerico = filas().every(function (f, i) { return f.querySelector('a.btn').getAttribute('href') === '/referenciales/consulta/consulta-detalle/' + (11 + i); });
      r.pide_pagina_1_de_15 = llamadas('GET', /\/api\/v1\/consultas\?.*pagina=1.*por_pagina=15|\/api\/v1\/consultas\?.*por_pagina=15.*pagina=1/).length >= 1;
      r.info_paginacion = /Mostrando 1–15 de 31/.test(txt('infoPagina'));
      r.anterior_deshabilitado_siguiente_no = document.getElementById('btnAnterior').disabled && !document.getElementById('btnSiguiente').disabled;
      document.getElementById('btnSiguiente').click(); await esperar(400);
      r.siguiente_pide_pagina_2 = llamadas('GET', /pagina=2/).length === 1;
      document.getElementById('btnAnterior').click(); await esperar(300);

      // filtros
      var fe = document.getElementById('filtroEstado'); fe.value = 'finalizada'; fe.dispatchEvent(new Event('change', {bubbles: true})); await esperar(400);
      r.filtro_estado_va_al_servidor = llamadas('GET', /estado=finalizada/).length >= 1;
      document.getElementById('btnLimpiarFiltros').click(); await esperar(400);
      r.limpiar_quita_el_filtro = document.getElementById('filtroEstado').value === '';
      var fp = document.getElementById('filtroPaciente'); fp.value = '5098'; fp.dispatchEvent(new Event('input', {bubbles: true})); await esperar(700);
      r.filtro_paciente_con_espera = llamadas('GET', /q=5098/).length === 1;
      document.getElementById('btnLimpiarFiltros').click(); await esperar(400);

      // anular: confirma, DELETE al id numérico
      filas()[0].querySelector('[data-accion="anular"]').click(); await esperar(400);
      var popup = document.querySelector('.swal2-popup');
      r.anular_pide_confirmacion = !!popup && /Anular/.test(popup.textContent) && /CON-0000011/.test(popup.textContent) && /Confirmado/.test(popup.textContent);
      r.sin_delete_antes_de_confirmar = llamadas('DELETE', /./).length === 0;
      document.querySelector('.swal2-confirm').click(); await esperar(700);
      r.anular_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/consultas\/11$/).length === 1;
      r.anular_muestra_exito = !!document.querySelector('.swal2-popup') && /Anulad/.test(document.querySelector('.swal2-popup').textContent);
      var cerrar = document.querySelector('.swal2-confirm'); if (cerrar) cerrar.click(); await esperar(400);
      r.ninguna_url_con_id_no_numerico = window.__calls.every(function (c) { return !/\/api\/v1\/[a-z-]+\/(true|false|null|undefined)(\/|$)/.test(c.url); });

      // nueva consulta
      var modalEl = document.getElementById('modalNueva');
      document.getElementById('btnNueva').click(); await esperar(900);
      r.modal_abre = modalEl.classList.contains('show');
      r.pide_las_citas_disponibles = llamadas('GET', /citas-disponibles$/).length === 1;
      r.dos_citas = modalEl.querySelectorAll('#tbodyCitas tr').length === 2;
      r.registrar_deshabilitado_sin_cita = document.getElementById('btnRegistrar').disabled;
      var q = document.getElementById('txtBuscarCita'); q.value = 'acosta'; q.dispatchEvent(new Event('input', {bubbles: true})); await esperar(600);
      r.buscar_va_al_servidor = llamadas('GET', /citas-disponibles\?q=acosta/).length === 1;
      modalEl.querySelector('button[data-cita="254"]').click(); await esperar(300);
      r.elegir_muestra_resumen_y_habilita = document.getElementById('bloqueElegida').style.display === 'block' && /JAVIER ACOSTA/.test(txt('resumenCita')) && !document.getElementById('btnRegistrar').disabled;
      var d = document.getElementById('txtDuracion'); d.value = 'abc';
      document.getElementById('btnRegistrar').click(); await esperar(300);
      r.duracion_invalida_no_envia = llamadas('POST', /./).length === 0 && d.classList.contains('is-invalid');
      d.value = '30';
      document.getElementById('btnRegistrar').click(); await esperar(900);
      var post = llamadas('POST', /\/api\/v1\/consultas$/);
      r.registrar_hace_un_post = post.length === 1;
      var cuerpo = post.length ? JSON.parse(post[0].body) : {};
      r.post_lleva_la_cita_elegida_y_la_duracion = cuerpo.id_cita === 254 && String(cuerpo.duracion_minutos) === '30';
      r.post_no_manda_paciente_medico_ni_estado = !('id_paciente' in cuerpo) && !('id_medico' in cuerpo) && !('estado' in cuerpo) && !('id_funcionario' in cuerpo);
      popup = document.querySelector('.swal2-popup');
      r.exito_ofrece_abrir_la_consulta = !!popup && /registrada correctamente/.test(popup.textContent) && /Abrir la consulta/.test(popup.textContent);
      r.modal_se_cerro = !modalEl.classList.contains('show');
      r.sin_errores_al_final = window.__errores.length === 0;
      if (window.__errores.length) r.errores = window.__errores;
    } catch (e) { r.EXCEPCION = String(e && e.stack || e); }
    document.getElementById('resultado').textContent = JSON.stringify(r);
  })();
})();
</script>
"""

PRUEBA_FICHAS = r"""
<pre id="resultado" style="display:none"></pre>
<script>
(function () {
  var r = {}; var esperar = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };
  var llamadas = function (m, re) { return window.__calls.filter(function (c) { return c.method === m && re.test(c.url); }); };
  (async function () {
    try {
      await esperar(700);
      var filas = Array.prototype.slice.call(document.querySelectorAll('#tbodyFichas tr'));
      r.sin_errores_al_cargar = window.__errores.length === 0;
      r.dos_filas = filas.length === 2;
      r.identifica_la_ficha = /CON-0000017/.test(filas[0].textContent) && /JAVIER ACOSTA/.test(filas[0].textContent) && /CI 5098745/.test(filas[0].textContent) && /6 de 9/.test(filas[0].textContent);
      r.estados_de_la_consulta = /En proceso/.test(filas[0].textContent) && /Finalizada/.test(filas[1].textContent);
      r.abrir_consulta_con_id_numerico_de_la_consulta = filas[0].querySelector('a').getAttribute('href') === '/referenciales/consulta/consulta-detalle/17' && filas[1].querySelector('a').getAttribute('href') === '/referenciales/consulta/consulta-detalle/18';
      r.no_muestra_valores_clinicos = !/36\.5|120\/80|Caries|Sin hallazgos/.test(document.getElementById('tbodyFichas').textContent);
      r.sin_botones_de_anular_ni_editar = !document.querySelector('[data-accion]');
      var fd = document.getElementById('filtroDesde'); fd.value = '2026-10-01'; fd.dispatchEvent(new Event('change', {bubbles: true})); await esperar(400);
      r.filtro_fecha_va_al_servidor = llamadas('GET', /desde=2026-10-01/).length === 1;
      r.ninguna_url_con_id_no_numerico = window.__calls.every(function (c) { return !/\/(true|false|null|undefined)(\/|$)/.test(c.url); });
      r.sin_errores_al_final = window.__errores.length === 0;
    } catch (e) { r.EXCEPCION = String(e && e.stack || e); }
    document.getElementById('resultado').textContent = JSON.stringify(r);
  })();
})();
</script>
"""

# La atención de la consulta se prueba por escenario: cada uno trae su `bloque` de comprobaciones.
PRUEBA_DETALLE = r"""
<pre id="resultado" style="display:none"></pre>
<script>
(function () {
  var r = {}; var esperar = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };
  var llamadas = function (m, re) { return window.__calls.filter(function (c) { return c.method === m && re.test(c.url); }); };
  var $ = function (id) { return document.getElementById(id); };
  var visible = function (id) { var e = $(id); return !!e && e.style.display !== 'none' && e.offsetParent !== null; };
  var txt = function (id) { return ($(id).textContent || '').trim(); };
  var escribir = function (id, v) { var e = $(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); };
  var enviar = function () { $('fichaForm').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true})); };
  var cerrarSwal = async function () { var c = document.querySelector('.swal2-confirm'); if (c) c.click(); await esperar(400); };
  (async function () {
    try {
      await esperar(900);
      var esc = window.__ESC.nombre;
      r.sin_errores_al_cargar = window.__errores.length === 0;
      r.cabecera = /JAVIER ACOSTA/.test(txt('dPaciente')) && /CI 5098745/.test(txt('dCedula')) && /OSCAR GONZALES/.test(txt('dMedico')) && /CONSULTORIO CENTRAL/.test(txt('dConsultorio'))
        && /26\/10\/2026 09:00/.test(txt('dFecha')) && /ROCÍO CABRERA/.test(txt('dFuncionario'));
      r.pidio_el_resumen_con_id_numerico = llamadas('GET', /\/api\/v1\/consultas\/\d+\/resumen$/).length === 1;
      var grid = $('gridMovimientos');
      r.siete_tarjetas_clinicas = grid.querySelectorAll('.card').length === 7;
      var enlaces = Array.prototype.slice.call(grid.querySelectorAll('a'));
      r.enlaces_con_la_consulta = enlaces.every(function (a) { return /\?consulta=17(&|$)/.test(a.getAttribute('href')); });
      r.diagnosticos_lleva_paciente_y_medico = /diagnostico-index\?consulta=17&paciente=7&medico=20/.test(enlaces[0].getAttribute('href'));

      if (esc === 'medico_programada') {
        r.badge_programada = /Programada/.test(txt('badgeEstado'));
        r.botones_iniciar_y_cancelar = visible('btnIniciar') && !visible('btnFinalizar') && visible('btnCancelar');
        r.tarjetas_dicen_abrir = enlaces.every(function (a) { return /Abrir/.test(a.textContent); });
        r.sin_aviso_de_lectura = !visible('avisoLectura');
        r.ficha_sin_registrar = /Sin ficha/.test(txt('badgeFicha')) && visible('btnRegistrarFicha') && !visible('btnEditarFicha') && !visible('btnAnularFicha');
        $('btnRegistrarFicha').click(); await esperar(300);
        r.formulario_abierto = visible('fichaForm');
        // vacía
        enviar(); await esperar(300);
        r.ficha_vacia_no_envia = llamadas('POST', /./).length === 0 && /al menos un dato/.test(txt('errFicha')) && visible('errFicha');
        // rangos
        escribir('fTemperatura', '50'); escribir('fPresion', '80/120'); enviar(); await esperar(300);
        r.rangos_marcados_y_no_envia = llamadas('POST', /./).length === 0 && $('fTemperatura').classList.contains('is-invalid') && $('fPresion').classList.contains('is-invalid')
          && /entre 30 y 45/.test($('fTemperatura').parentElement.querySelector('.invalid-feedback').textContent)
          && /mayor que la diastólica/.test($('fPresion').parentElement.querySelector('.invalid-feedback').textContent);
        escribir('fTemperatura', '36,5'); escribir('fPresion', '120/80');
        r.al_corregir_se_limpia_el_error = !$('fTemperatura').classList.contains('is-invalid');
        // IMC en vivo
        escribir('fPeso', '70'); escribir('fTalla', '175');
        r.imc_en_vivo = $('fImc').value === '22.86';
        escribir('fTalla', ''); r.imc_se_vacia_sin_talla = $('fImc').value === '';
        escribir('fTalla', '175');
        escribir('fExamenBucal', 'Sin hallazgos');
        enviar(); await esperar(900);
        var post = llamadas('POST', /\/api\/v1\/ficha-medica$/);
        r.un_post_a_ficha_medica = post.length === 1;
        var b = post.length ? JSON.parse(post[0].body) : {};
        r.post_lleva_la_consulta_y_los_datos = b.id_consulta_cab === 17 && b.presion_arterial === '120/80' && b.temperatura === '36,5' && b.peso === '70' && b.examen_bucal === 'Sin hallazgos';
        r.post_no_manda_imc = !('imc' in b);
        r.exito = !!document.querySelector('.swal2-popup') && /registrada correctamente|Ficha registrada/.test(document.querySelector('.swal2-popup').textContent);
        await cerrarSwal();
        // estado: iniciar
        $('btnIniciar').click(); await esperar(400);
        r.iniciar_pide_confirmacion = !!document.querySelector('.swal2-popup') && /Iniciar la atención/.test(document.querySelector('.swal2-popup').textContent) && llamadas('PATCH', /./).length === 0;
        document.querySelector('.swal2-confirm').click(); await esperar(800);
        var p = llamadas('PATCH', /\/api\/v1\/consultas\/17\/estado$/);
        r.iniciar_hace_patch_al_id_numerico = p.length === 1 && JSON.parse(p[0].body).estado === 'en_proceso';
        await cerrarSwal();
        // cancelar
        $('btnCancelar').click(); await esperar(400);
        r.cancelar_avisa_de_la_cita = !!document.querySelector('.swal2-popup') && /Cancelado/.test(document.querySelector('.swal2-popup').textContent) && /No se puede deshacer/.test(document.querySelector('.swal2-popup').textContent);
        document.querySelector('.swal2-confirm').click(); await esperar(800);
        p = llamadas('PATCH', /\/estado$/);
        r.cancelar_hace_patch = p.length === 2 && JSON.parse(p[1].body).estado === 'cancelada';
        await cerrarSwal();
      }

      if (esc === 'medico_con_ficha') {
        r.badge_en_proceso = /En proceso/.test(txt('badgeEstado'));
        r.finalizar_y_cancelar = !visible('btnIniciar') && visible('btnFinalizar') && visible('btnCancelar');
        r.contadores = /2/.test(grid.textContent) && grid.querySelectorAll('.h3')[0].textContent === '2' && grid.querySelectorAll('.h3')[2].textContent === '1';
        r.ficha_vista_con_valores = /Registrada/.test(txt('badgeFicha')) && visible('fichaVista') && /120\/80/.test(txt('fichaValores')) && /22.86/.test(txt('fichaValores')) && /Caries en 36/.test(txt('fichaTextos'));
        r.editar_y_anular_visibles = visible('btnEditarFicha') && visible('btnAnularFicha') && !visible('btnRegistrarFicha');
        $('btnEditarFicha').click(); await esperar(300);
        r.editar_precarga = $('fPresion').value === '120/80' && $('fTemperatura').value === '36.5' && $('fPeso').value === '70' && $('fImc').value === '22.86' && $('fExamenBucal').value === 'Caries en 36';
        escribir('fTemperatura', '37,2');
        enviar(); await esperar(900);
        var put = llamadas('PUT', /\/api\/v1\/ficha-medica\/31$/);
        r.editar_hace_put_al_id_de_la_ficha = put.length === 1 && JSON.parse(put[0].body).temperatura === '37,2';
        await cerrarSwal();
        $('btnAnularFicha').click(); await esperar(400);
        r.anular_pide_confirmacion = !!document.querySelector('.swal2-popup') && /Anular la ficha/.test(document.querySelector('.swal2-popup').textContent) && llamadas('DELETE', /./).length === 0;
        document.querySelector('.swal2-confirm').click(); await esperar(800);
        r.anular_hace_delete_al_id_numerico = llamadas('DELETE', /\/api\/v1\/ficha-medica\/31$/).length === 1;
        await cerrarSwal();
        // finalizar: valida la duración
        $('btnFinalizar').click(); await esperar(400);
        var inp = document.querySelector('.swal2-input'); inp.value = 'abc';
        document.querySelector('.swal2-confirm').click(); await esperar(400);
        r.finalizar_valida_la_duracion = /entre 1 y 480/.test((document.querySelector('.swal2-validation-message') || {}).textContent || '') && llamadas('PATCH', /./).length === 0;
        document.querySelector('.swal2-input').value = '45';
        document.querySelector('.swal2-confirm').click(); await esperar(800);
        var f = llamadas('PATCH', /\/estado$/);
        r.finalizar_manda_estado_y_duracion = f.length === 1 && JSON.parse(f[0].body).estado === 'finalizada' && String(JSON.parse(f[0].body).duracion_minutos) === '45';
        await cerrarSwal();
      }

      if (esc === 'recepcion') {
        r.solo_cancelar = !visible('btnIniciar') && !visible('btnFinalizar') && visible('btnCancelar');
        r.aviso_de_lectura = visible('avisoLectura') && /médico de la consulta/.test(txt('avisoLectura'));
        r.tarjetas_dicen_ver = enlaces.every(function (a) { return /Ver/.test(a.textContent) && !/Abrir/.test(a.textContent); });
        r.ficha_solo_lectura = visible('fichaVista') && !visible('btnRegistrarFicha') && !visible('btnEditarFicha') && !visible('btnAnularFicha');
      }

      if (esc === 'finalizada') {
        r.badge_finalizada = /Finalizada/.test(txt('badgeEstado'));
        r.sin_botones_de_estado = !visible('btnIniciar') && !visible('btnFinalizar') && !visible('btnCancelar');
        r.aviso_finalizada = visible('avisoLectura') && /finalizada/.test(txt('avisoLectura')) && /no se puede anular/.test(txt('avisoLectura'));
        r.ficha_solo_lectura = visible('fichaVista') && !visible('btnEditarFicha') && !visible('btnAnularFicha');
        r.tarjetas_dicen_ver = enlaces.every(function (a) { return /Ver/.test(a.textContent); });
      }
      r.ninguna_url_con_id_no_numerico = window.__calls.every(function (c) { return !/\/api\/v1\/[a-z-]+\/(true|false|null|undefined)(\/|$)/.test(c.url); });
      r.sin_errores_al_final = window.__errores.length === 0;
      if (window.__errores.length) r.errores = window.__errores;
    } catch (e) { r.EXCEPCION = String(e && e.stack || e); }
    $('resultado').textContent = JSON.stringify(r);
  })();
})();
</script>
"""

URLS = {'consulta-index': '/referenciales/consulta/consulta-index',
        'consulta-detalle': '/referenciales/consulta/consulta-detalle/17',
        'ficha-medica-index': '/referenciales/ficha-medica/ficha-medica-index'}
PRUEBAS = {'consulta-index': PRUEBA_LISTADO, 'consulta-detalle': PRUEBA_DETALLE, 'ficha-medica-index': PRUEBA_FICHAS}

c = app.test_client()
with c.session_transaction() as s:
    s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

# Para renderizar la atención de la consulta 17 hace falta que exista y sea visible: se usa la API simulada, pero la ruta consulta
# al servidor, así que se renderiza la plantilla directamente con el cliente de pruebas de Flask y un contexto de solicitud.
from flask import render_template
total_fallos = 0
for nombre, esc in ESCENARIOS.items():
    esc = dict(esc, nombre=nombre)
    pagina = esc['pagina']
    if pagina == 'consulta-detalle':
        with app.test_request_context(URLS[pagina]):
            from flask import session
            session['id_usuario'] = 1; session['id_rol'] = 1; session['nombre_rol'] = 'Administrador'
            html = render_template('consulta-detalle.html', id_consulta=17, numero='CON-0000017')
    else:
        html = c.get(URLS[pagina]).get_data(as_text=True)
    html = html.replace('"/static/', '"' + STATIC)
    html = html.replace('<head>', '<head>' + MOCK % {'esc': json.dumps(esc)}, 1)
    html = html.replace('</body>', PRUEBAS[pagina] + '</body>', 1)
    archivo = SALIDA / f'{nombre}.html'
    archivo.write_text(html, encoding='utf-8')
    proc = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--no-first-run',
                           '--virtual-time-budget=40000', '--dump-dom', archivo.as_uri()],
                          capture_output=True, text=True, encoding='utf-8', timeout=180)
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
        print('     detalle:', json.dumps(r, ensure_ascii=False)[:1500])
print('VISTAS CON FALLOS:', total_fallos)
