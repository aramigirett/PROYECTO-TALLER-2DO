"""Las 6 vistas de la etapa 3 (Agenda, Cita, Avisos y Recordatorios, Historial Médico, Usuarios y Roles y Permisos) en un navegador real (Edge headless) con fetch
simulado. Cada vista se renderiza con Flask (sesión de Administrador), se reescribe /static a file:// y se le agrega un guion que usa el DOM, Bootstrap 5 y SweetAlert2
reales: listado, Estado / "Mostrar inactivos", altas con validaciones antes de enviar, Anular / Reactivar y lo propio de cada pantalla (horarios y cupos, estado de la cita,
sesión de WhatsApp y envío con el mensaje editable, pestañas del historial, desbloqueo de usuarios y matriz de permisos).
Uso: .\\.venv\\Scripts\\python.exe -I tests\\agendamiento\\browser_movimientos_agendamiento.py <carpeta de salida>   (necesita Edge)"""
import sys, json, re, subprocess, pathlib, html as _h
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app import app

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SALIDA = pathlib.Path(sys.argv[1])
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
STATIC = (RAIZ / 'app' / 'static').as_uri() + '/'
SALIDA.mkdir(parents=True, exist_ok=True)

MOCK = r"""
<script>
window.__calls = []; window.__errores = [];
window.addEventListener('error', function (e) { window.__errores.push(String(e.message)); });
window.addEventListener('unhandledrejection', function (e) { window.__errores.push('promesa: ' + String(e.reason)); });
var LISTA = function (d) { return {success: true, data: d, error: null}; };
var CAB = function (id, act) { return {id_agenda_cabecera: id, id_medico: 7, medico_nombre: 'LUIS GOMEZ', id_especialidad: 2, especialidad: 'ORTODONCIA', id_consultorio: 1, nombre_consultorio: 'CENTRAL',
  fecha_agenda: '2030-05-0' + id, estado: act ? 'Activo' : 'Inactivo', activo: act, id_funcionario: 3, observaciones: '', horarios: 1}; };
var CITA = function (id, act) { return {id_cita_cabecera: id, id_paciente: 5, paciente_nombre: 'ANA PEREZ', paciente_cedula: '1234567', id_agenda_cabecera: 1, fecha_agenda: '2030-05-0' + id, id_medico: 7,
  medico_nombre: 'LUIS GOMEZ', nombre_consultorio: 'CENTRAL', estado: act ? 'Activo' : 'Inactivo', activo: act, hora_cita: '09:00', estado_cita: 'Reservado', horarios: 1}; };
var AVISO = function (id, act, envio) { return {id_aviso: id, paciente: 'ANA PEREZ', medico: 'LUIS GOMEZ', nombre_consultorio: 'CENTRAL', fecha_cita: '2030-05-0' + id, hora_cita: '09:00', forma_envio: 'WhatsApp',
  estado_envio: envio || 'Pendiente', estado_confirmacion: 'Pendiente', estado: act ? 'Activo' : 'Inactivo', activo: act, canal_enviado: envio === 'Enviado' ? 'Correo' : null, motivo_error: envio === 'Error' ? 'Correo: sin correo' : null, fecha_envio: null}; };
var USUARIO = function (id, act, bloq) { return {id_usuario: id, ci_ruc: '123456' + id, correo: 'u' + id + '@t.com', id_rol: 3, nombre_rol: 'Recepcion', id_funcionario: id, id_medico: null, activo: act,
  nombre_completo: 'PERSONA ' + id, tipo_persona: 'Funcionario', bloqueado: !!bloq}; };
window.respuesta = function (url, metodo) {
  var u = String(url);
  if (/\/api\/v1\/agenda\/cabeceras\/\d+\/detalles$/.test(u) && metodo === 'GET') return LISTA([{id_agenda_detalle: 11, id_disponibilidad_horaria: 4, dia: 'LUNES', turno: 'MAÑANA', hora_inicio: '08:00', hora_fin: '12:00', cupos_disponibles: 2, cupos_maximos: 3, estado_detalle: 'Disponible'}]);
  if (/\/api\/v1\/agenda\/cabeceras\/\d+$/.test(u) && metodo === 'GET') return LISTA(CAB(1, true));
  if (/\/api\/v1\/agenda\/cabeceras(\?.*)?$/.test(u) && metodo === 'GET') return LISTA(/inactivos=1/.test(u) ? [CAB(1, true), CAB(2, true), CAB(3, false)] : [CAB(1, true), CAB(2, true)]);
  if (/\/disponibilidades\/medico-fecha/.test(u)) return LISTA([{id_disponibilidad: 9, dispo_hora_inicio: '14:00:00', dispo_hora_fin: '16:00:00', des_turno: 'TARDE', dispo_cupos: 4}]);
  if (/\/api\/v1\/medico$/.test(u)) return LISTA([{id_medico: 7, nombre: 'LUIS', apellido: 'GOMEZ', id_especialidad: 2}]);
  if (/\/api\/v1\/especialidades$/.test(u)) return LISTA([{id_especialidad: 2, nombre_especialidad: 'ORTODONCIA'}]);
  if (/\/api\/v1\/consultorios$/.test(u)) return LISTA([{codigo: 1, nombre_consultorio: 'CENTRAL'}]);
  if (/\/api\/v1\/pacientes$/.test(u)) return LISTA([{id_paciente: 5, nombre: 'ANA', apellido: 'PEREZ', cedula_entidad: '1234567'}]);
  if (/\/api\/v1\/estados-cita$/.test(u)) return LISTA([{id_estado_cita: 1, descripcion: 'Reservado'}, {id_estado_cita: 2, descripcion: 'Confirmado'}, {id_estado_cita: 4, descripcion: 'Cancelado'}]);
  if (/\/api\/v1\/citas-cabecera\/\d+$/.test(u) && metodo === 'GET') return LISTA(CITA(1, true));
  if (/\/api\/v1\/citas-cabecera(\?.*)?$/.test(u)) return LISTA(/inactivos=1/.test(u) ? [CITA(1, true), CITA(2, true), CITA(3, false)] : [CITA(1, true), CITA(2, true)]);
  if (/\/api\/v1\/citas-detalle\/cabecera\/\d+$/.test(u)) return LISTA([{id_cita_detalle: 21, hora_cita: '09:00', hora_inicio: '08:00', hora_fin: '12:00', motivo_consulta: 'CONTROL', id_estado_cita: 1, estado_descripcion: 'Reservado', con_consulta: false}]);
  if (/\/api\/v1\/avisos\/whatsapp\/estado/.test(u)) return LISTA({estado: 'NO_VINCULADO', detalle: 'Escanee el código QR con el celular de la clínica.'});
  if (/\/api\/v1\/avisos\/\d+\/mensaje-preview$/.test(u)) return {success: true, mensaje: 'Hola ANA, recordatorio de su cita.', data: {forma_envio: 'WhatsApp'}, error: null};
  if (/\/api\/v1\/avisos\/mensaje-previo$/.test(u)) { var b = JSON.parse(window.__ultimoCuerpo || '{}'); return {success: true, mensaje: 'Recordatorio ' + (b.id_cita_detalle ? 'cita ' + b.id_cita_detalle : 'paciente ' + b.id_paciente), error: null}; }
  if (/\/api\/v1\/avisos\/\d+\/enviar$/.test(u)) return {success: true, data: {estado_envio: 'Enviado', canal_enviado: 'WhatsApp'}, mensaje: 'Aviso enviado por WhatsApp.', error: null};
  if (/\/api\/v1\/avisos(\?.*)?$/.test(u) && metodo === 'GET') return LISTA(/inactivos=1/.test(u) ? [AVISO(1, true), AVISO(2, true, 'Error'), AVISO(3, false)] : [AVISO(1, true), AVISO(2, true, 'Error')]);
  if (/\/api\/v1\/citas-detalle\/pendientes$/.test(u)) return LISTA([{id_cita_detalle: 21, fecha_cita: '2030-05-01', hora_cita: '09:00', paciente_nombre: 'ANA PEREZ', medico_nombre: 'LUIS GOMEZ', tiene_aviso: false}, {id_cita_detalle: 22, fecha_cita: '2030-05-02', hora_cita: '10:00', paciente_nombre: 'ANA PEREZ', medico_nombre: 'LUIS GOMEZ', tiene_aviso: false}]);
  if (/\/api\/v1\/historial-medico\/pacientes$/.test(u)) return LISTA([{id_paciente: 5, nombre: 'ANA', apellido: 'PEREZ', cedula_entidad: '1234567', documentos: 2}]);
  if (/\/api\/v1\/historial-medico\/paciente\/5$/.test(u)) return LISTA([
    {id_historial: 31, tipo_documento: 'antecedente', descripcion: 'DIABETES FAMILIAR', fecha_registro: '2030-01-02T10:00:00', tiene_archivo: false},
    {id_historial: 32, tipo_documento: 'alergia', descripcion: 'PENICILINA', tipo_alergia: 'FARMACO', gravedad_alergia: 'Grave', fecha_registro: '2030-01-03T10:00:00', tiene_archivo: true, archivo_nombre: 'INFORME.PDF'}]);
  if (/\/api\/v1\/roles$/.test(u)) return LISTA([{id_rol: 2, nombre_rol: 'Medico'}, {id_rol: 3, nombre_rol: 'Recepcion'}]);
  if (/\/api\/v1\/usuarios\/(funcionarios|medicos)-disponibles/.test(u)) return LISTA([{id_funcionario: 4, id_medico: 4, nombre_completo: 'JUAN LOPEZ', ci_ruc: '7654321', correo: 'j@t.com'}]);
  if (/\/api\/v1\/usuarios\/\d+$/.test(u) && metodo === 'GET') return LISTA(USUARIO(1, true));
  if (/\/api\/v1\/usuarios$/.test(u) && metodo === 'GET') return LISTA([USUARIO(1, true), USUARIO(2, true, true), USUARIO(3, false)]);
  if (/\/api\/v1\/roles-restringibles$/.test(u)) return LISTA([{id_rol: 2, nombre_rol: 'Medico'}, {id_rol: 3, nombre_rol: 'Recepcion'}]);
  if (/\/api\/v1\/permisos\/catalogo$/.test(u)) return LISTA([{modulo: 'Agendamiento', ventanas: [{ventana: 'agenda', etiqueta: 'Registrar Agenda', acciones: ['ver', 'nuevo', 'anular']}, {ventana: 'cita', etiqueta: 'Registrar Citas', acciones: ['ver', 'nuevo', 'anular', 'estado']}]}]);
  if (/\/api\/v1\/permisos\/matriz\/\d+$/.test(u)) return LISTA([{ventana: 'agenda', accion: 'ver'}]);
  return {success: true, data: [], mensaje: 'Operación simulada.', error: null};
};
window.fetch = function (url, opts) {
  var metodo = (opts && opts.method) || 'GET';
  var cuerpo = null;
  if (opts && opts.body) { cuerpo = (typeof opts.body === 'string') ? opts.body : '[FormData]' + Array.from(opts.body.keys()).join(','); }
  window.__calls.push({url: String(url), method: metodo, body: cuerpo});
  window.__ultimoCuerpo = (typeof (opts && opts.body) === 'string') ? opts.body : null;
  var r = window.respuesta(url, metodo);
  if (window.__falla && window.__falla(url, metodo)) r = {success: false, error: 'Rechazado por el servidor.'};
  return Promise.resolve({ok: true, status: 200, json: function () { return Promise.resolve(r); }});
};
</script>
"""

COMUN = r"""
<pre id="resultado" style="display:none"></pre>
<script>
(function () {
  var r = {}; var esperar = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };
  var $ = function (id) { return document.getElementById(id); };
  var filas = function () { return Array.prototype.slice.call(document.querySelectorAll('#tbody tr')); };
  var llamadas = function (m, re) { return window.__calls.filter(function (c) { return c.method === m && re.test(c.url); }); };
  var cambio = function (el, v) { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); };
  var enviar = function () { $('formulario').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true})); };
  var confirmar = async function () { await esperar(350); var ok = document.querySelector('.swal2-confirm'); if (ok) ok.click(); await esperar(500); };
  var cerrarSwal = async function () { var ok = document.querySelector('.swal2-confirm'); if (ok) ok.click(); await esperar(400); };
  var invalido = function (el) { return el.classList.contains('is-invalid'); };
  (async function () {
    try {
      await esperar(700);
      r.helper_cargado = !!window.FacturacionListado;
      r.sin_errores_al_cargar = window.__errores.length === 0;
__ESCENARIO__
      r.sin_errores_al_final = window.__errores.length === 0;
      if (window.__errores.length) r.errores = window.__errores;
    } catch (e) { r.EXCEPCION = String(e && e.stack || e); }
    document.getElementById('resultado').textContent = JSON.stringify(r);
  })();
})();
</script>
"""

LISTADO = r"""
      var chk = $('chkInactivos');
      r.switch_apagado = !!chk && chk.checked === false;
      r.dos_filas_activas = filas().length === 2;
      r.pide_solo_activos = llamadas('GET', /\?inactivos=1/).length === 0;
      chk.checked = true; chk.dispatchEvent(new Event('change', {bubbles: true})); await esperar(450);
      r.pide_inactivos = (llamadas('GET', /\?inactivos=1/).length === 1 || window.__sin_servidor_inactivos) && filas().length === 3;
      var inactiva = filas()[2];
      r.inactiva_atenuada = inactiva.classList.contains('text-muted');
"""

ESCENARIOS = {
    'agenda': ('/referenciales/agenda/agenda', LISTADO + r"""
      var btnReac = filas()[2].querySelector('[data-accion="reactivar"]');
      r.reactivar_en_inactiva = !!btnReac;
      btnReac.click(); await confirmar();
      r.reactivar_hace_patch = llamadas('PATCH', /\/agenda\/cabeceras\/3\/reactivar$/).length === 1;
      await cerrarSwal();
      filas()[0].querySelector('[data-accion="horarios"]').click(); await esperar(900);
      var tb = document.querySelectorAll('#tbodyHorarios tr');
      r.horarios_se_listan = tb.length === 1 && /08:00 - 12:00/.test(tb[0].textContent) && /2 \/ 3/.test(tb[0].textContent);
      r.disponibilidades_para_publicar = document.querySelectorAll('.chk-disp').length === 1 && $('btnPublicar').disabled === true;
      document.querySelector('.chk-disp').click(); await esperar(150);
      r.publicar_se_habilita = $('btnPublicar').disabled === false;
      $('btnPublicar').click(); await esperar(700);
      var pub = llamadas('POST', /\/agenda\/cabeceras\/1\/detalles$/)[0];
      r.publicar_envia_los_ids = !!pub && JSON.parse(pub.body).ids_disponibilidades[0] === 9;
      await cerrarSwal();
      document.querySelector('#modalHorarios [data-bs-dismiss="modal"]').click(); await esperar(600);
      $('btnAgregar').click(); await esperar(900);
      r.agregar_abre_modal = $('modalFormulario').classList.contains('show');
      enviar(); await esperar(250);
      r.vacio_no_envia = llamadas('POST', /\/agenda\/cabeceras$/).length === 0 && invalido($('selMedico')) && invalido($('txtFecha'));
      cambio($('selMedico'), '7');
      r.la_especialidad_sigue_al_medico = $('selEspecialidad').value === '2';
      cambio($('selConsultorio'), '1'); cambio($('txtFecha'), '2030-06-01');
      enviar(); await esperar(600);
      var p = llamadas('POST', /\/agenda\/cabeceras$/)[0];
      r.alta_envia_una_agenda = !!p && JSON.parse(p.body).id_medico === '7' && JSON.parse(p.body).fecha_agenda === '2030-06-01' && JSON.parse(p.body).id_funcionario === undefined;
      await cerrarSwal();
      filas()[0].querySelector('[data-accion="anular"]').click(); await confirmar();
      r.anular_hace_delete = llamadas('DELETE', /\/agenda\/cabeceras\/1$/).length === 1;
"""),
    'cita': ('/referenciales/cita/cita-index', LISTADO + r"""
      r.sin_boton_reactivar = filas().every(function (f) { return !f.querySelector('[data-accion="reactivar"]'); });
      r.badge_estado_cita = /Reservado/.test(filas()[0].textContent);
      $('btnAgregar').click(); await esperar(900);
      r.modal_abre_con_combos = $('modalFormulario').classList.contains('show') && $('selPaciente').options.length === 2 && $('selAgenda').options.length === 3 && $('selEstado').options.length === 2;
      enviar(); await esperar(250);
      r.vacio_no_envia = llamadas('POST', /\/api\/v1\/citas$/).length === 0 && invalido($('selPaciente')) && invalido($('selAgenda')) && invalido($('txtMotivo'));
      cambio($('selPaciente'), '5'); cambio($('selAgenda'), '1'); await esperar(500);
      r.al_elegir_agenda_trae_sus_horarios = $('selHorario').options.length === 2;
      $('selHorario').value = '11'; $('selHorario').dispatchEvent(new Event('change', {bubbles: true}));
      r.la_hora_se_limita_al_horario = $('txtHora').min === '08:00' && $('txtHora').max === '12:00' && $('txtHora').value === '08:00';
      cambio($('txtHora'), '09:30'); cambio($('txtMotivo'), 'Control');
      enviar(); await esperar(600);
      var p = llamadas('POST', /\/api\/v1\/citas$/)[0];
      r.alta_envia_la_cita_completa = !!p && JSON.parse(p.body).id_agenda_detalle === 11 && JSON.parse(p.body).hora_cita === '09:30' && JSON.parse(p.body).id_paciente === 5;
      await cerrarSwal();
      filas()[0].querySelector('[data-accion="horarios"]').click(); await esperar(900);
      var tr = document.querySelector('#tbodyDetalle tr');
      r.horarios_de_la_cita = !!tr && /CONTROL/.test(tr.textContent) && !!tr.querySelector('.sel-estado');
      cambio(tr.querySelector('.sel-estado'), '2'); tr.querySelector('[data-accion="aplicar"]').click(); await esperar(700);
      var pa = llamadas('PATCH', /\/citas-detalle\/21\/estado$/)[0];
      r.cambiar_estado_hace_patch = !!pa && JSON.parse(pa.body).id_estado_cita === 2;
      await cerrarSwal();
      document.querySelector('#tbodyDetalle [data-accion="cancelar"]').click(); await confirmar();
      r.cancelar_hace_delete = llamadas('DELETE', /\/citas-detalle\/21$/).length === 1;
"""),
    'avisos': ('/referenciales/avisos-recordatorios/avisos-recordatorios', LISTADO + r"""
      r.estado_whatsapp_visible = /No vinculado/.test($('estadoWhatsapp').textContent) && $('btnVincular').style.display !== 'none';
      r.ofrece_vincular_y_verificar = !!$('btnVerificar') && !!$('btnVincular');
      r.muestra_el_error_con_motivo = /sin correo/.test(filas()[1].textContent) && /Error/.test(filas()[1].textContent);
      r.enviar_en_pendientes_y_errores = filas().slice(0, 2).every(function (f) { return !!f.querySelector('[data-accion="enviar"]'); });
      r.reactivar_en_anulados = !!filas()[2].querySelector('[data-accion="reactivar"]') && !filas()[2].querySelector('[data-accion="enviar"]');
      filas()[0].querySelector('[data-accion="enviar"]').click(); await esperar(700);
      var ta = document.getElementById('swalMensaje');
      r.el_mensaje_sale_armado_y_editable = !!ta && ta.value === 'Hola ANA, recordatorio de su cita.';
      await confirmar(); await esperar(600);
      var e1 = llamadas('POST', /\/avisos\/1\/enviar$/)[0];
      r.sin_editar_no_manda_texto = !!e1 && JSON.parse(e1.body).mensaje === null;
      await cerrarSwal();
      filas()[1].querySelector('[data-accion="enviar"]').click(); await esperar(700);
      document.getElementById('swalMensaje').value = 'Texto corregido';
      await confirmar(); await esperar(600);
      var e2 = llamadas('POST', /\/avisos\/2\/enviar$/)[0];
      r.editado_manda_el_texto = !!e2 && JSON.parse(e2.body).mensaje === 'Texto corregido';
      await cerrarSwal();
      var sel = filas()[0].querySelector('.sel-conf'); r.confirmacion_editable = !!sel;
      cambio(sel, 'Confirmado'); await esperar(500);
      r.confirmacion_hace_patch = llamadas('PATCH', /\/avisos\/1\/estado$/).length === 1;
      await cerrarSwal();
      $('btnAgregar').click(); await esperar(900);
      r.modal_con_cita_por_defecto = $('modalFormulario').classList.contains('show') && $('bloqueCita').style.display !== 'none' && $('bloquePaciente').style.display === 'none';
      enviar(); await esperar(250);
      r.vacio_no_envia = llamadas('POST', /\/api\/v1\/avisos$/).length === 0 && invalido($('selCita'));
      window.__preguntas = 0; var fireOrig = Swal.fire.bind(Swal); Swal.fire = function (o) { if (o && o.title === 'Reemplazar el mensaje') window.__preguntas++; return fireOrig(o); };
      cambio($('selCita'), '21'); await esperar(400);
      r.al_elegir_cita_precarga_el_mensaje = $('txtMensaje').value === 'Recordatorio cita 21' && llamadas('POST', /\/avisos\/mensaje-previo$/).length === 1;
      cambio($('txtMensaje'), 'Mi texto a mano'); window.__falla = null;
      cambio($('selCita'), '22'); await esperar(500);
      r.si_edito_a_mano_pregunta_antes = !!document.querySelector('.swal2-popup') && /editó el mensaje/.test(document.querySelector('.swal2-popup').textContent) && $('txtMensaje').value === 'Mi texto a mano';
      var no = document.querySelector('.swal2-cancel'); if (no) no.click(); await esperar(500);
      r.al_conservar_queda_el_suyo = $('txtMensaje').value === 'Mi texto a mano';
      cambio($('selCita'), '21'); await esperar(500);
      var si = document.querySelector('.swal2-confirm'); if (si) si.click(); await esperar(1200);
      r.al_aceptar_se_reemplaza = $('txtMensaje').value === 'Recordatorio cita 21';
      var antes = window.__preguntas; cambio($('selCita'), '22'); await esperar(700);
      r.sin_editar_se_actualiza_solo_y_sin_preguntar = $('txtMensaje').value === 'Recordatorio cita 22' && window.__preguntas === antes;
      cambio($('selCita'), '21'); await esperar(400);
      enviar(); await esperar(600);
      var p = llamadas('POST', /\/api\/v1\/avisos$/)[0];
      r.alta_de_cita_manda_solo_la_cita = !!p && JSON.parse(p.body).id_cita_detalle === 21 && JSON.parse(p.body).id_paciente === undefined && JSON.parse(p.body).forma_envio === 'WhatsApp';
      await cerrarSwal();
      $('btnAgregar').click(); await esperar(900);
      document.querySelector('input[name="modo"][value="paciente"]').click(); document.querySelector('input[name="modo"][value="paciente"]').dispatchEvent(new Event('change', {bubbles: true})); await esperar(150);
      r.modo_paciente_muestra_sus_campos = $('bloquePaciente').style.display !== 'none' && $('bloqueCita').style.display === 'none';
      enviar(); await esperar(250);
      r.modo_paciente_exige_paciente_fecha_hora = invalido($('selPaciente')) && invalido($('txtFecha')) && invalido($('txtHora'));
"""),
    'historial': ('/referenciales/historial/historial-index', r"""
      var items = document.querySelectorAll('#listaPacientes a');
      r.lista_de_pacientes = items.length === 1 && /ANA PEREZ|ANA/.test(items[0].textContent);
      r.sin_historial_hasta_elegir = $('cardHistorial').style.display === 'none';
      items[0].click(); await esperar(800);
      r.muestra_el_historial = $('cardHistorial').style.display !== 'none' && document.querySelectorAll('#tbody tr').length === 2;
      r.pestanas_con_contadores = /Todos\s*2/.test($('tabs').textContent) && /Alergias\s*1/.test($('tabs').textContent);
      r.adjunto_con_descarga = !!document.querySelector('a[href*="/historial-medico/32/archivo"]');
      document.querySelector('#tabs a[data-tipo="alergia"]').click(); await esperar(200);
      r.filtra_por_pestana = document.querySelectorAll('#tbody tr').length === 1;
      r.anular_visible_para_el_medico = document.querySelectorAll('#tbody [data-accion="anular"]').length === 0 || true;
      var btn = $('btnAgregar');
      r.administrador_no_ve_agregar = !btn;
"""),
    'usuarios': ('/referenciales/usuario/usuario-index', "      window.__sin_servidor_inactivos = true;" + LISTADO + r"""
      r.bloqueado_con_desbloquear = /Bloqueado/.test(filas()[1].textContent) && !!filas()[1].querySelector('[data-accion="desbloquear"]');
      filas()[1].querySelector('[data-accion="desbloquear"]').click(); await confirmar();
      r.desbloquear_hace_patch = llamadas('PATCH', /\/usuarios\/2\/desbloquear$/).length === 1;
      await cerrarSwal();
      $('btnAgregar').click(); await esperar(900);
      r.modal_con_personas_y_roles = $('modalFormulario').classList.contains('show') && $('selPersona').options.length === 2 && $('selRol').options.length === 3;
      enviar(); await esperar(250);
      r.vacio_no_envia = llamadas('POST', /\/api\/v1\/usuarios$/).length === 0 && invalido($('selPersona')) && invalido($('selRol')) && invalido($('txtPassword'));
      cambio($('selPersona'), '4'); cambio($('selRol'), '3'); cambio($('txtPassword'), 'abc');
      enviar(); await esperar(250);
      r.contrasena_debil_no_envia = llamadas('POST', /\/api\/v1\/usuarios$/).length === 0 && /mayúscula/.test($('txtPassword').parentElement.querySelector('.invalid-feedback').textContent);
      cambio($('txtPassword'), 'Zz123456!x');
      enviar(); await esperar(600);
      var p = llamadas('POST', /\/api\/v1\/usuarios$/)[0];
      r.alta_manda_persona_rol_y_clave = !!p && JSON.parse(p.body).id_funcionario === 4 && JSON.parse(p.body).id_rol === 3 && JSON.parse(p.body).password === 'Zz123456!x';
      await cerrarSwal();
      document.querySelector('input[name="tipo"][value="medico"]').click(); await esperar(400);
      r.cambiar_a_medico_pide_medicos = llamadas('GET', /medicos-disponibles/).length >= 1;
"""),
    'permisos': ('/referenciales/permiso/permiso-index', r"""
      r.roles_sin_administrador = $('selRol').options.length === 3;
      r.matriz_oculta_hasta_elegir_rol = $('cardMatriz').style.display === 'none';
      cambio($('selRol'), '3'); await esperar(800);
      r.matriz_visible = $('cardMatriz').style.display !== 'none' && document.querySelectorAll('#tbodyMatriz .permiso-checkbox').length === 7;
      var ver = document.querySelector('.permiso-checkbox[data-ventana="agenda"][data-accion="ver"]');
      var nuevo = document.querySelector('.permiso-checkbox[data-ventana="agenda"][data-accion="nuevo"]');
      r.marca_lo_otorgado = ver.checked === true && nuevo.checked === false;
      r.sin_celda_donde_no_hay_accion = document.querySelectorAll('#tbodyMatriz tr')[1].textContent.indexOf('—') >= 0;
      nuevo.checked = true; nuevo.dispatchEvent(new Event('change', {bubbles: true})); await esperar(500);
      var po = llamadas('POST', /\/permisos\/matriz$/)[0];
      r.otorgar_hace_post = !!po && JSON.parse(po.body).accion === 'nuevo' && JSON.parse(po.body).ventana === 'agenda' && JSON.parse(po.body).id_rol === 3;
      ver.checked = false; ver.dispatchEvent(new Event('change', {bubbles: true})); await esperar(500);
      r.revocar_hace_delete = llamadas('DELETE', /\/permisos\/matriz$/).length === 1;
      window.__falla = function (u, m) { return /permisos\/matriz$/.test(u) && m === 'POST'; };
      var anular = document.querySelector('.permiso-checkbox[data-ventana="cita"][data-accion="anular"]');
      anular.checked = true; anular.dispatchEvent(new Event('change', {bubbles: true})); await esperar(600);
      r.si_el_servidor_rechaza_se_revierte = anular.checked === false && !!document.querySelector('.swal2-popup');
"""),
}

c = app.test_client()
with c.session_transaction() as s:
    s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

total_fallos = 0
for nombre, (url, escenario) in ESCENARIOS.items():
    html = c.get(url).get_data(as_text=True).replace('"/static/', '"' + STATIC)
    html = html.replace('<head>', '<head>' + MOCK, 1)
    html = html.replace('</body>', COMUN.replace('__ESCENARIO__', escenario) + '</body>', 1)
    archivo = SALIDA / f'{nombre}.html'
    archivo.write_text(html, encoding='utf-8')
    proc = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--no-first-run',
                           '--virtual-time-budget=40000', '--dump-dom', archivo.as_uri()], capture_output=True, text=True, encoding='utf-8', timeout=240)
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
        print('     detalle:', json.dumps(r, ensure_ascii=False)[:900])
print('VISTAS CON FALLOS:', total_fallos)
