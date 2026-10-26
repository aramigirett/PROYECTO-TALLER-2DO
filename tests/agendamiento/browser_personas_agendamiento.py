"""Las 3 vistas de personas de Agendamiento (Etapa 2: Paciente, Médico y Funcionario) en un navegador real (Edge headless) con fetch simulado.
Renderiza cada vista con Flask (sesión de Administrador), reescribe /static a file:// y agrega un script que usa el DOM, Bootstrap 5 y
SweetAlert2 reales: Estado, "Mostrar inactivos", Reactivar, Anular, modal Agregar/Editar y validaciones del formulario.
Uso: .\\.venv\\Scripts\\python.exe -I tests\\agendamiento\\browser_personas_agendamiento.py <carpeta de salida>   (necesita Edge)"""
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
    'paciente': ('/referenciales/paciente/paciente-index', 'nombre', 'paciente'),
    'medico': ('/referenciales/medico/medico-index', 'nombre', 'medico'),
    'funcionario': ('/referenciales/funcionario/funcionario-index', 'nombre', 'funcionario'),
}

MOCK = r"""
<script>
window.__calls = []; window.__errores = [];
window.addEventListener('error', function (e) { window.__errores.push(String(e.message)); });
window.addEventListener('unhandledrejection', function (e) { window.__errores.push('promesa: ' + String(e.reason)); });
// Igual que el servidor real: Flask ordena las claves alfabéticamente (la primera es 'activo', NO la clave primaria).
function fila(id, texto, activo) {
  var o = {activo: activo, descripcion: texto, nombre_especialidad: texto, nombre: texto, apellido: 'PRUEBA', cedula: '1234567', cedula_entidad: '1234567',
           telefono: '0981123456', telefono_emergencia: '0981000333', direccion: 'CALLE 1', correo: 'a@b.com', fecha_nacimiento: '1990-05-05',
           num_registro: 'MP-1', id_ciudad: id, id_especialidad: id, id_cargo: id, ciudades: 'ASUNCIÓN', especialidades: 'ORTODONCIA', cargo: 'RECEPCIONISTA',
           fecha_registro: '2026-10-24 10:00:00'};
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

      // ---- modal Agregar / Editar ----
      var modalEl = document.getElementById('modalFormulario');
      var envios = function () { return window.__calls.filter(function (c) { return c.method === 'POST'; }).length; };
      var enviar = function () { document.getElementById('formulario').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true})); };
      var fb = function (el) { var f = el.parentElement.querySelector('.invalid-feedback'); return f ? f.textContent : ''; };
      var cambio = function (el, v) { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); };
      var $ = function (id) { return document.getElementById(id); };
      var doc = TIPO === 'paciente' ? 'cedula_entidad' : 'cedula';
      document.getElementById('btnAgregar').click(); await esperar(1000);
      r.agregar_abre_modal = modalEl.classList.contains('show');
      r.agregar_titulo = /Agregar/.test($('modalTitle').textContent);
      r.combos_cargados = Array.prototype.slice.call(modalEl.querySelectorAll('select')).every(function (s) { return s.options.length > 1; });
      r.fecha_nacimiento_con_max_hoy = /^\d{4}-\d{2}-\d{2}$/.test($('txtNacimiento').max);
      enviar(); await esperar(300);
      r.vacio_no_envia = envios() === 0;
      r.vacio_marca_todos_los_campos = Array.prototype.slice.call(modalEl.querySelectorAll('input.form-control, select.form-select')).filter(function (e) { return e.type !== 'hidden'; })
        .every(function (e) { return e.classList.contains('is-invalid'); });
      cambio($('txtNombre'), 'Ana'); cambio($('txtApellido'), 'Pérez'); cambio($('txtCedula'), '12');
      cambio($('txtNacimiento'), '2999-01-01'); cambio($('txtTelefono'), '0981123456'); cambio($('txtDireccion'), 'Calle 1'); cambio($('txtCorreo'), 'malo');
      if ($('txtEmergencia')) cambio($('txtEmergencia'), '0981000333');
      if ($('txtRegistro')) cambio($('txtRegistro'), 'mp-1');
      Array.prototype.slice.call(modalEl.querySelectorAll('select')).forEach(function (s) { cambio(s, s.options[1].value); });
      enviar(); await esperar(300);
      r.cedula_corta_no_envia = envios() === 0 && /5 a 10|CI\/RUC|cédula/i.test(fb($('txtCedula')));
      r.nacimiento_futuro_no_envia = /futura/.test(fb($('txtNacimiento')));
      r.correo_invalido_no_envia = /formato/.test(fb($('txtCorreo')));
      cambio($('txtCedula'), '1234567'); cambio($('txtNacimiento'), '1990-05-05'); cambio($('txtCorreo'), 'ana@test.invalid');
      enviar(); await esperar(600);
      r.valido_envia_un_post = envios() === 1;
      var post = window.__calls.filter(function (c) { return c.method === 'POST'; })[0];
      var cuerpo = post ? JSON.parse(post.body) : {};
      r.post_lleva_los_campos = cuerpo.nombre === 'Ana' && cuerpo[doc] === '1234567' && cuerpo.fecha_nacimiento === '1990-05-05' && cuerpo.telefono === '0981123456' && cuerpo.correo === 'ana@test.invalid';
      r.post_no_lleva_fecha_de_alta = cuerpo.fecha_registro === undefined;
      exito = document.querySelector('.swal2-popup');
      r.alta_muestra_exito = !!exito && /Agregad/.test(exito.textContent);
      cerrar = document.querySelector('.swal2-confirm'); if (cerrar) cerrar.click(); await esperar(700);
      r.modal_se_cierra_al_guardar = !modalEl.classList.contains('show');

      // ---- Editar ----
      var dos = filas().filter(function (f) { return /ACTIVA DOS/.test(f.textContent); })[0];
      dos.querySelector('[data-accion="editar"]').click(); await esperar(1000);
      r.editar_abre_modal = modalEl.classList.contains('show');
      r.editar_titulo = /Editar/.test($('modalTitle').textContent);
      r.editar_precarga = $('txtNombre').value === 'ACTIVA DOS' && $('txtCedula').value === '1234567' && $('txtNacimiento').value === '1990-05-05' && $('txtTelefono').value === '0981 123 456';
      r.editar_precarga_combos = Array.prototype.slice.call(modalEl.querySelectorAll('select')).every(function (s) { return s.value === '2'; });
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
    pk = re.search(r"const PK = '([a-z_]+)'", html).group(1)
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
