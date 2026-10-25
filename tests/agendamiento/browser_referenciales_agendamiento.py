"""Las 7 vistas de referenciales de Agendamiento (Etapa 1) en un navegador real (Edge headless) con fetch simulado.
Renderiza cada vista con Flask (sesión de Administrador), reescribe /static a file:// y agrega un script que usa el DOM, Bootstrap 5 y
SweetAlert2 reales: Estado, "Mostrar inactivos", Reactivar, Anular, modal Agregar/Editar y validaciones del formulario.
Uso: .\\.venv\\Scripts\\python.exe -I tests\\agendamiento\\browser_referenciales_agendamiento.py <carpeta de salida>   (necesita Edge)"""
import sys, json, re, subprocess, pathlib, html as _h
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app import app

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SALIDA = pathlib.Path(sys.argv[1])
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
STATIC = (RAIZ / 'app' / 'static').as_uri() + '/'
SALIDA.mkdir(parents=True, exist_ok=True)

# nombre -> (url, campo del texto principal, tipo de formulario)
VISTAS = {
    'ciudad': ('/referenciales/ciudad/ciudad-index', 'descripcion', 'simple'),
    'cargo': ('/referenciales/cargo/cargo-index', 'descripcion', 'simple'),
    'especialidad': ('/referenciales/especialidad/especialidad-index', 'nombre_especialidad', 'simple'),
    'turno': ('/referenciales/turno/turno-index', 'descripcion', 'simple'),
    'dia': ('/referenciales/dia/dia-index', 'descripcion', 'dia'),
    'consultorio': ('/referenciales/consultorio/consultorio-index', 'nombre_consultorio', 'consultorio'),
    'disponibilidad': ('/referenciales/disponibilidad/disponibilidad-index', 'medico_nombre', 'disponibilidad'),
}

MOCK = r"""
<script>
window.__calls = []; window.__errores = [];
window.addEventListener('error', function (e) { window.__errores.push(String(e.message)); });
window.addEventListener('unhandledrejection', function (e) { window.__errores.push('promesa: ' + String(e.reason)); });
// Igual que el servidor real: Flask ordena las claves alfabéticamente (la primera es 'activo', NO la clave primaria).
function fila(id, texto, activo) {
  var o = {activo: activo, descripcion: texto, nombre_especialidad: texto, nombre_consultorio: texto, medico_nombre: texto,
           direccion: 'CALLE 1', telefono: '595981123456', correo: 'a@b.com', codigo: id, id_medico: id, id_dia: 1, id_turno: 1,
           dispo_fecha: '2030-01-02', dispo_hora_inicio: '08:00:00', dispo_hora_fin: '12:00:00', dispo_cupos: 5, des_dia: 'LUNES', des_turno: 'MAÑANA',
           nombre: 'DR', apellido: 'PRUEBA', fecha_registro: '2026-10-24 10:00:00'};
  o['__PK__'] = id;
  var ordenado = {}; Object.keys(o).sort().forEach(function (k) { ordenado[k] = o[k]; });
  return ordenado;
}
var FILAS = [fila(1, 'ACTIVA UNO', true), fila(2, 'ACTIVA DOS', true), fila(3, 'INACTIVA TRES', false)];
window.fetch = function (url, opts) {
  var metodo = (opts && opts.method) || 'GET';
  window.__calls.push({url: String(url), method: metodo, body: opts && opts.body ? String(opts.body) : null});
  var cuerpo = {success: true, data: [], error: null, mensaje: 'Operación simulada.'};
  var porId = /\/api\/v1\/[a-z-]+\/(\d+)$/.exec(String(url));
  if (metodo === 'GET' && porId) { cuerpo.data = FILAS[parseInt(porId[1], 10) - 1]; }
  if (metodo === 'GET' && /\/api\/v1\/[a-z-]+(\?inactivos=1)?$/.test(url) && !/menu\/buscar/.test(url)) {
    cuerpo.data = /inactivos=1/.test(url) ? FILAS : FILAS.filter(function (f) { return f.activo; });
  }
  return Promise.resolve({ok: true, status: 200, json: function () { return Promise.resolve(cuerpo); }});
};
</script>
"""

PRUEBA = r"""
<pre id="resultado" style="display:none"></pre>
<script>
(function () {
  var r = {}; var esperar = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };
  var tbody = function () { return document.querySelector('table tbody'); };
  var filas = function () { return Array.prototype.slice.call(tbody().querySelectorAll('tr')); };
  var llamadas = function (m, re) { return window.__calls.filter(function (c) { return c.method === m && re.test(c.url); }); };
  var TIPO = '__TIPO__';
  (async function () {
    try {
      await esperar(600);
      var chk = document.getElementById('chkInactivos');
      r.sin_errores_al_cargar = window.__errores.length === 0;
      r.helper_cargado = !!window.FacturacionListado && !!window.FacturacionValidadores;
      r.switch_existe_y_apagado = !!chk && chk.checked === false;
      r.etiqueta_switch = (chk.parentElement.textContent || '').trim();
      r.filas_activas = filas().length;
      r.sin_boton_reactivar_si_apagado = filas().every(function (f) { return !f.querySelector('[data-accion="reactivar"]'); });
      r.badges_activos = filas().every(function (f) { return /Activo/.test(f.textContent) && !/Inactivo/.test(f.textContent); });
      r.activas_con_editar_y_anular = filas().every(function (f) { return f.querySelector('[data-accion="editar"]') && f.querySelector('[data-accion="anular"]'); });
      r.encabezado_estado = /Estado/.test(document.querySelector('table thead').textContent);
      r.sin_columna_codigo = !/C[óo]digo/.test(document.querySelector('table thead').textContent);
      r.pide_solo_activos = llamadas('GET', /\/api\/v1\/[a-z-]+$/).length >= 1 && llamadas('GET', /inactivos=1/).length === 0;

      chk.checked = true; chk.dispatchEvent(new Event('change', {bubbles: true}));
      await esperar(400);
      r.pide_inactivos_al_encender = llamadas('GET', /\?inactivos=1$/).length === 1;
      r.filas_con_inactivos = filas().length;
      var inactiva = filas().filter(function (f) { return /INACTIVA TRES/.test(f.textContent); })[0];
      r.fila_inactiva_atenuada = !!inactiva && inactiva.classList.contains('text-muted');
      r.badge_inactivo = !!inactiva && /Inactivo/.test(inactiva.textContent) && !!inactiva.querySelector('.badge.bg-secondary-lt');
      var btnReac = inactiva && inactiva.querySelector('[data-accion="reactivar"]');
      r.boton_reactivar_en_inactiva = !!btnReac && /Reactivar/.test(btnReac.textContent);
      r.inactiva_sin_editar_ni_anular = !!inactiva && !inactiva.querySelector('[data-accion="editar"]') && !inactiva.querySelector('[data-accion="anular"]');

      btnReac.click(); await esperar(400);
      var popup = document.querySelector('.swal2-popup');
      r.reactivar_pide_confirmacion = !!popup && /Reactivar/.test(popup.textContent) && /INACTIVA TRES/.test(popup.textContent);
      r.sin_patch_antes_de_confirmar = llamadas('PATCH', /reactivar$/).length === 0;
      var cancelar = document.querySelector('.swal2-cancel'); if (cancelar) cancelar.click(); await esperar(400);
      r.cancelar_no_hace_patch = llamadas('PATCH', /reactivar$/).length === 0;
      btnReac = filas().filter(function (f) { return /INACTIVA TRES/.test(f.textContent); })[0].querySelector('[data-accion="reactivar"]');
      btnReac.click(); await esperar(400);
      var ok = document.querySelector('.swal2-confirm'); if (ok) ok.click(); await esperar(600);
      r.ninguna_url_con_id_no_numerico = window.__calls.every(function (c) { return !/\/api\/v1\/[a-z-]+\/(true|false|null|undefined)(\/|$)/.test(c.url); });
      r.reactivar_hace_patch_al_id_correcto = llamadas('PATCH', /\/3\/reactivar$/).length === 1;
      r.recarga_la_lista_tras_reactivar = llamadas('GET', /\?inactivos=1$/).length >= 2;
      var exito = document.querySelector('.swal2-popup');
      r.muestra_exito = !!exito && /Reactivad/.test(exito.textContent) && /Operación simulada/.test(exito.textContent);
      var cerrar = document.querySelector('.swal2-confirm'); if (cerrar) cerrar.click(); await esperar(400);

      var activa = filas().filter(function (f) { return /ACTIVA UNO/.test(f.textContent); })[0];
      activa.querySelector('[data-accion="anular"]').click(); await esperar(400);
      popup = document.querySelector('.swal2-popup');
      r.anular_pide_confirmacion = !!popup && /Anular/.test(popup.textContent);
      ok = document.querySelector('.swal2-confirm'); if (ok) ok.click(); await esperar(600);
      r.anular_hace_delete = llamadas('DELETE', /\/1$/).length === 1;
      exito = document.querySelector('.swal2-popup');
      r.anular_muestra_exito = !!exito && /Anulad/.test(exito.textContent);
      cerrar = document.querySelector('.swal2-confirm'); if (cerrar) cerrar.click(); await esperar(400);

      // ---- modal Agregar / Editar (según el tipo de formulario) ----
      var modalEl = document.getElementById('modalFormulario');
      var envios = function () { return window.__calls.filter(function (c) { return c.method === 'POST'; }).length; };
      var enviar = function () { document.getElementById('formulario').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true})); };
      var fb = function (el) { var f = el.parentElement.querySelector('.invalid-feedback'); return f ? f.textContent : ''; };
      var cambio = function (el, v) { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); };
      document.getElementById('btnAgregar').click(); await esperar(900);
      r.agregar_abre_modal = modalEl.classList.contains('show');
      r.agregar_titulo = /Agregar/.test(document.getElementById('modalTitle').textContent);
      enviar(); await esperar(300);
      r.vacio_no_envia = envios() === 0;
      if (TIPO === 'simple' || TIPO === 'dia') {
        var clave = document.getElementById('txtClave');
        r.vacio_marca_el_campo = clave.classList.contains('is-invalid') && /obligatorio/.test(fb(clave));
        if (TIPO === 'simple') {
          cambio(clave, 'abc<>'); enviar(); await esperar(300);
          r.simbolo_invalido_no_envia = envios() === 0 && /solo puede contener/.test(fb(clave));
          cambio(clave, 'zz ñandú-1/2');
        } else {
          r.tiene_los_7_dias = clave.options.length === 8;
          cambio(clave, 'MARTES');
        }
      } else if (TIPO === 'consultorio') {
        var ids = ['txtNombre', 'txtDireccion', 'txtTelefono', 'txtCorreo'];
        r.vacio_marca_los_4 = ids.every(function (i) { return document.getElementById(i).classList.contains('is-invalid'); });
        cambio(document.getElementById('txtNombre'), 'zz consultorio');
        cambio(document.getElementById('txtDireccion'), 'Calle Falsa 123');
        cambio(document.getElementById('txtTelefono'), '123');
        cambio(document.getElementById('txtCorreo'), 'malo');
        enviar(); await esperar(300);
        r.telefono_y_correo_invalidos_no_envian = envios() === 0 && /paraguayo/.test(fb(document.getElementById('txtTelefono'))) && /formato/.test(fb(document.getElementById('txtCorreo')));
        cambio(document.getElementById('txtTelefono'), '0981 234 567');
        cambio(document.getElementById('txtCorreo'), 'zz@test.invalid');
      } else {
        var sm = document.getElementById('selMedico');
        r.combos_cargados = document.getElementById('selDia').options.length > 1 && sm.options.length > 1;
        r.vacio_marca_obligatorios = sm.classList.contains('is-invalid') && document.getElementById('txtFecha').classList.contains('is-invalid');
        cambio(sm, sm.options[1].value); cambio(document.getElementById('selDia'), document.getElementById('selDia').options[1].value);
        cambio(document.getElementById('selTurno'), document.getElementById('selTurno').options[1].value);
        cambio(document.getElementById('txtFecha'), '2030-01-02');
        cambio(document.getElementById('txtInicio'), '12:00'); cambio(document.getElementById('txtFin'), '08:00'); cambio(document.getElementById('txtCupos'), '5');
        enviar(); await esperar(300);
        r.fin_antes_del_inicio_no_envia = envios() === 0 && /posterior/.test(fb(document.getElementById('txtFin')));
        cambio(document.getElementById('txtInicio'), '08:00'); cambio(document.getElementById('txtFin'), '12:00');
      }
      enviar(); await esperar(600);
      r.valido_envia_un_post = envios() === 1;
      var post = window.__calls.filter(function (c) { return c.method === 'POST'; })[0];
      var cuerpo = post ? JSON.parse(post.body) : {};
      if (TIPO === 'simple') r.post_lleva_la_clave = cuerpo['__CLAVE__'] === 'zz ñandú-1/2';
      if (TIPO === 'dia') r.post_lleva_el_dia = cuerpo['__CLAVE__'] === 'MARTES';
      if (TIPO === 'consultorio') r.post_lleva_los_4_campos = cuerpo.nombre_consultorio === 'zz consultorio' && cuerpo.telefono === '0981 234 567' && !!cuerpo.correo && !!cuerpo.direccion;
      if (TIPO === 'disponibilidad') r.post_lleva_horario = cuerpo.dispo_hora_inicio === '08:00' && cuerpo.dispo_hora_fin === '12:00' && cuerpo.dispo_cupos === '5' && cuerpo.dispo_fecha === '2030-01-02';
      exito = document.querySelector('.swal2-popup');
      r.alta_muestra_exito = !!exito && /Agregad/.test(exito.textContent);
      cerrar = document.querySelector('.swal2-confirm'); if (cerrar) cerrar.click(); await esperar(700);
      r.modal_se_cierra_al_guardar = !modalEl.classList.contains('show');

      // ---- Editar ----
      var dos = filas().filter(function (f) { return /ACTIVA DOS/.test(f.textContent); })[0];
      dos.querySelector('[data-accion="editar"]').click(); await esperar(900);
      r.editar_abre_modal = modalEl.classList.contains('show');
      r.editar_titulo = /Editar/.test(document.getElementById('modalTitle').textContent);
      if (TIPO === 'simple') r.editar_precarga_la_clave = document.getElementById('txtClave').value === 'ACTIVA DOS';
      if (TIPO === 'consultorio') r.editar_precarga = document.getElementById('txtNombre').value === 'ACTIVA DOS' && document.getElementById('txtTelefono').value === '595981123456';
      if (TIPO === 'disponibilidad') r.editar_precarga = document.getElementById('txtFecha').value === '2030-01-02' && document.getElementById('txtInicio').value === '08:00' && document.getElementById('txtCupos').value === '5';
      modalEl.querySelector('[data-bs-dismiss="modal"]').click(); await esperar(700);
      r.sin_errores_al_final = window.__errores.length === 0;
      if (window.__errores.length) r.errores = window.__errores;
    } catch (e) {
      r.EXCEPCION = String(e && e.stack || e);
    }
    document.getElementById('resultado').textContent = JSON.stringify(r);
  })();
})();
</script>
"""

c = app.test_client()
with c.session_transaction() as s:
    s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

total_fallos = 0
for nombre, (url, clave, tipo) in VISTAS.items():
    html = c.get(url).get_data(as_text=True)
    html = html.replace('"/static/', '"' + STATIC)
    m_pk = re.search(r"const PK = '([a-z_]+)'", html)
    pk = m_pk.group(1) if m_pk else {'consultorio': 'codigo', 'disponibilidad': 'id_disponibilidad'}[nombre]
    html = html.replace('<head>', '<head>' + MOCK.replace('__PK__', pk), 1)
    prueba = PRUEBA.replace('__TIPO__', tipo).replace('__CLAVE__', clave)
    html = html.replace('</body>', prueba + '</body>', 1)
    archivo = SALIDA / f'{nombre}.html'
    archivo.write_text(html, encoding='utf-8')
    proc = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--no-first-run',
                           '--virtual-time-budget=30000', '--dump-dom', archivo.as_uri()],
                          capture_output=True, text=True, encoding='utf-8', timeout=180)
    m = re.search(r'<pre id="resultado"[^>]*>(.*?)</pre>', proc.stdout, re.S)
    if not m or not m.group(1).strip():
        print(f'FAIL {nombre}: la página no produjo resultado (¿error de sintaxis?)'); total_fallos += 1
        print(proc.stderr[-400:]); continue
    r = json.loads(_h.unescape(m.group(1)))
    bools = [k for k, v in r.items() if isinstance(v, bool)]
    malos = [k for k in bools if not r[k]]
    if 'EXCEPCION' in r:
        malos.append('EXCEPCION')
    malos += [k for k, v in {'filas_activas': 2, 'filas_con_inactivos': 3}.items() if r.get(k) != v]
    print(('OK  ' if not malos else 'FAIL'), nombre, '| checks:', len(bools), '| etiqueta:', r.get('etiqueta_switch'), '| filas', r.get('filas_activas'), '->', r.get('filas_con_inactivos'))
    if malos:
        total_fallos += 1
        print('     fallan:', malos)
        print('     detalle:', json.dumps(r, ensure_ascii=False)[:1200])
print('VISTAS CON FALLOS:', total_fallos)
