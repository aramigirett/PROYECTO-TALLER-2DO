"""Mantener Menú y las páginas de error 403/404 en Tabler, en Edge headless con fetch simulado (misma técnica que tests/agendamiento/browser_*.py).
Uso: .\\.venv\\Scripts\\python.exe -I tests\\seguridad\\browser_menu.py <carpeta de salida>   (necesita Edge)"""
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
var F = function (id, p) { var o = {id_menu: id, id_menu_padre: null, clave: null, descripcion: 'MODULO ' + id, ruta: null, icono: 'fa-folder', orden: id, activo: true, visible_en_menu: true, solo_admin: false, protegida: false, modulo: 'MODULO ' + id, tipo: 'modulo'};
  for (var k in (p || {})) o[k] = p[k]; return o; };
var ACTIVAS = [F(1), F(10, {id_menu_padre: 1, clave: 'agenda', descripcion: 'Registrar Agenda', ruta: 'agenda_bp.index', icono: 'fa-calendar', tipo: 'ventana', modulo: 'MODULO 1'}),
  F(11, {id_menu_padre: 1, clave: 'menu', descripcion: 'Mantener Menú', ruta: 'menu.menuIndex', tipo: 'ventana', solo_admin: true, protegida: true, modulo: 'MODULO 1'})];
var INACT = F(12, {id_menu_padre: 1, clave: 'viejo', descripcion: 'Vieja', ruta: 'agenda_bp.index', tipo: 'ventana', activo: false, modulo: 'MODULO 1'});
window.respuesta = function (url, metodo) {
  var u = String(url);
  if (/\/menus\/rutas$/.test(u)) return {success: true, data: [{endpoint: 'agenda_bp.index', url: '/agenda'}, {endpoint: 'menu.menuIndex', url: '/menu'}], error: null};
  if (/\/menus\/\d+$/.test(u) && metodo === 'GET') { var id = parseInt(u.split('/').pop(), 10); return {success: true, data: ACTIVAS.concat([INACT]).filter(function (f) { return f.id_menu === id; })[0], error: null}; }
  if (/\/api\/v1\/menus(\?.*)?$/.test(u) && metodo === 'GET') return {success: true, data: /inactivos=1/.test(u) ? ACTIVAS.concat([INACT]) : ACTIVAS, error: null};
  return {success: true, data: {id_menu: 99}, mensaje: 'Operación simulada.', error: null};
};
window.fetch = function (url, opts) {
  var metodo = (opts && opts.method) || 'GET';
  window.__calls.push({url: String(url), method: metodo, body: (opts && opts.body) || null});
  var r = window.respuesta(url, metodo);
  if (window.__falla && window.__falla(url, metodo)) r = {success: false, error: 'Rechazado por el servidor.', campo: 'descripcion'};
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
  (async function () {
    try {
      await esperar(700);
__ESCENARIO__
      r.sin_errores = window.__errores.length === 0;
      if (window.__errores.length) r.errores = window.__errores;
    } catch (e) { r.EXCEPCION = String(e && e.stack || e); }
    document.getElementById('resultado').textContent = JSON.stringify(r);
  })();
})();
</script>
"""

MENU = r"""
      r.lista_modulos_y_ventanas = filas().length === 3 && /MODULO 1/.test(filas()[0].textContent) && /Registrar Agenda/.test(filas()[1].textContent);
      r.switch_apagado = $('chkInactivos').checked === false;
      r.protegida_sin_boton_anular = !filas()[2].querySelector('[data-accion="anular"]') && /Protegida/.test(filas()[2].textContent);
      r.normal_con_anular = !!filas()[1].querySelector('[data-accion="anular"]') && !!filas()[1].querySelector('[data-accion="editar"]');
      $('chkInactivos').checked = true; $('chkInactivos').dispatchEvent(new Event('change', {bubbles: true})); await esperar(450);
      r.inactivos_se_piden_al_servidor = llamadas('GET', /\?inactivos=1/).length === 1 && filas().length === 4;
      var inact = filas()[3];
      r.inactiva_con_reactivar = !!inact.querySelector('[data-accion="reactivar"]') && !inact.querySelector('[data-accion="editar"]');
      inact.querySelector('[data-accion="reactivar"]').click(); await confirmar();
      r.reactivar_hace_patch = llamadas('PATCH', /\/menus\/12\/reactivar$/).length === 1;
      await cerrarSwal();
      $('btnAgregar').click(); await esperar(900);
      r.modal_abre_con_combos = $('modalFormulario').classList.contains('show') && $('selModulo').options.length === 2 && $('selRuta').options.length === 3;
      enviar(); await esperar(300);
      r.vacio_no_envia = llamadas('POST', /\/api\/v1\/menus$/).length === 0 && $('txtDescripcion').classList.contains('is-invalid') && $('selModulo').classList.contains('is-invalid')
        && $('selRuta').classList.contains('is-invalid') && $('txtClave').classList.contains('is-invalid') && $('txtOrden').classList.contains('is-invalid');
      cambio($('selModulo'), '1'); cambio($('txtDescripcion'), 'Reportes'); cambio($('txtClave'), 'Mal Clave'); cambio($('selRuta'), 'agenda_bp.index'); cambio($('txtOrden'), '30'); cambio($('txtIcono'), 'fa-chart-bar');
      enviar(); await esperar(300);
      r.clave_invalida_no_envia = llamadas('POST', /\/api\/v1\/menus$/).length === 0 && $('txtClave').classList.contains('is-invalid');
      cambio($('txtClave'), 'reportes');
      enviar(); await esperar(700);
      var p = llamadas('POST', /\/api\/v1\/menus$/)[0];
      var b = p && JSON.parse(p.body);
      r.alta_envia_la_ventana = !!b && b.tipo === 'ventana' && b.clave === 'reportes' && b.id_menu_padre === 1 && b.orden === 30 && b.ruta === 'agenda_bp.index' && b.visible_en_menu === true;
      await cerrarSwal();
      filas()[2].querySelector('[data-accion="editar"]').click(); await esperar(900);
      r.editar_protegida_bloquea_modulo_y_ruta = $('selModulo').disabled && $('selRuta').disabled && $('chkAdmin').disabled && $('txtClave').disabled && $('chkAdmin').checked;
      document.querySelector('#modalFormulario [data-bs-dismiss="modal"]').click(); await esperar(600);
      window.__falla = function (u, m) { return m === 'DELETE'; };
      filas()[1].querySelector('[data-accion="anular"]').click(); await confirmar();
      r.anular_hace_delete = llamadas('DELETE', /\/menus\/10$/).length === 1;
      r.error_del_servidor_se_muestra = !!document.querySelector('.swal2-popup');
"""

ESCENARIOS = {'menu': ('Administrador', '/referenciales/menu/menu-index', MENU)}


def sesion(rol):
    c = app.test_client()
    if rol:
        with c.session_transaction() as s:
            s['id_usuario'] = 1; s['id_rol'] = 1 if rol == 'Administrador' else 2; s['nombre_rol'] = rol
    return c


total_fallos = 0
for nombre, (rol, url, escenario) in ESCENARIOS.items():
    html = sesion(rol).get(url).get_data(as_text=True).replace('"/static/', '"' + STATIC)
    html = html.replace('<head>', '<head>' + MOCK, 1).replace('</body>', COMUN.replace('__ESCENARIO__', escenario) + '</body>', 1)
    archivo = SALIDA / f'{nombre}.html'
    archivo.write_text(html, encoding='utf-8')
    proc = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--no-first-run', '--virtual-time-budget=40000', '--dump-dom', archivo.as_uri()],
                          capture_output=True, text=True, encoding='utf-8', timeout=240)
    m = re.search(r'<pre id="resultado"[^>]*>(.*?)</pre>', proc.stdout, re.S)
    if not m or not m.group(1).strip():
        print(f'FAIL {nombre}: la página no produjo resultado'); total_fallos += 1; print(proc.stderr[-400:]); continue
    r = json.loads(_h.unescape(m.group(1)))
    bools = [k for k, v in r.items() if isinstance(v, bool)]
    malos = [k for k in bools if not r[k]] + (['EXCEPCION'] if 'EXCEPCION' in r else [])
    print(('OK  ' if not malos else 'FAIL'), nombre, '| checks:', len(bools))
    if malos:
        total_fallos += 1; print('     fallan:', malos); print('     detalle:', json.dumps(r, ensure_ascii=False)[:900])

# páginas de error: Tabler, sin SB Admin y sin referencias rotas a /static
for nombre, (rol, url, codigo) in {'403 (Medico)': ('Medico', '/referenciales/menu/menu-index', 403), '404 (Administrador)': ('Administrador', '/no-existe', 404),
                                   '404 (sin sesión)': (None, '/no-existe', 404)}.items():
    resp = sesion(rol).get(url); h = resp.get_data(as_text=True)
    huerfanos = [f for f in re.findall(r'(?:href|src)="/static/([^"?]+)', h) if not (RAIZ / 'app' / 'static' / f).exists()]
    ok = resp.status_code == codigo and 'empty-header' in h and 'sb-admin' not in h and 'tabler.min.css' in h and not huerfanos
    print(('OK  ' if ok else 'FAIL'), f'página de error {nombre}', '' if ok else (resp.status_code, huerfanos))
    total_fallos += 0 if ok else 1
print('VISTAS CON FALLOS:', total_fallos)
sys.exit(1 if total_fallos else 0)
