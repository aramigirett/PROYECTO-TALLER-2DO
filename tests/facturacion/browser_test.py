"""Prueba las vistas en un navegador real (Edge headless) con fetch simulado.
Renderiza cada vista con Flask (sesión de Administrador), reescribe las rutas /static a file:// y agrega un
script de prueba que usa el DOM y SweetAlert2 reales. Imprime un resumen por vista."""
import sys, os, json, re, subprocess, pathlib
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SALIDA = pathlib.Path(sys.argv[1])
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
STATIC = (RAIZ / 'app' / 'static').as_uri() + '/'
SALIDA.mkdir(parents=True, exist_ok=True)

VISTAS = {
    'forma-cobro': ('/referenciales/forma-cobro/forma-cobro-index', 'forma de cobro', 'id_forma_cobro'),
    'marca-tarjeta': ('/referenciales/marca-tarjeta/marca-tarjeta-index', 'marca de tarjeta', 'id_marca_tarjeta'),
    'entidad-emisora': ('/referenciales/entidad-emisora/entidad-emisora-index', 'entidad emisora', 'id_entidad_emisora'),
    'entidad-adherida': ('/referenciales/entidad-adherida/entidad-adherida-index', 'entidad adherida', 'id_entidad_adherida'),
    'tipo-item': ('/referenciales/tipo-item/tipo-item-index', 'tipo de ítem', 'id_tipo_item'),
    'item': ('/referenciales/item/item-index', 'ítem', 'id_item'),
}

MOCK = r"""
<script>
window.__calls = []; window.__errores = [];
window.addEventListener('error', function (e) { window.__errores.push(String(e.message)); });
window.addEventListener('unhandledrejection', function (e) { window.__errores.push('promesa: ' + String(e.reason)); });
function fila(id, desc, activo) {
  var o = {activo: activo, descripcion: desc, direccion: 'Dir 1', telefono: '021 111222', correo: 'a@b.com',
           entidad_emisora: 'BANCO', marca_tarjeta: 'VISA', tipo_item: 'TIPO', deposito: 'DEP',
           precio_unitario: 15000, iva: 10, cantidad_disponible: 3, controla_stock: true};
  ['id_forma_cobro','id_marca_tarjeta','id_entidad_emisora','id_entidad_adherida','id_tipo_item','id_item'].forEach(function (k) { o[k] = id; });
  return o;
}
var FILAS = [fila(1, 'ACTIVA UNO', true), fila(2, 'ACTIVA DOS', true), fila(3, 'INACTIVA TRES', false)];
window.fetch = function (url, opts) {
  var metodo = (opts && opts.method) || 'GET';
  window.__calls.push({url: String(url), method: metodo});
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
  (async function () {
    try {
      await esperar(600);
      var chk = document.getElementById('chkInactivos');
      r.sin_errores_al_cargar = window.__errores.length === 0;
      r.helper_cargado = !!window.FacturacionListado;
      r.switch_existe_y_apagado = !!chk && chk.checked === false;
      r.etiqueta_switch = (chk.parentElement.textContent || '').trim();
      r.filas_activas = filas().length;
      r.sin_boton_reactivar_si_apagado = filas().every(function (f) { return !f.querySelector('[data-accion="reactivar"]'); });
      r.badges_activos = filas().every(function (f) { return /Activo/.test(f.textContent) && !/Inactivo/.test(f.textContent); });
      r.activas_con_editar_y_anular = filas().every(function (f) { return f.querySelector('[data-accion="editar"]') && f.querySelector('[data-accion="anular"]'); });
      r.encabezado_estado = /Estado/.test(document.querySelector('table thead').textContent);
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

      // Reactivar: confirma con SweetAlert2 y hace el PATCH
      btnReac.click(); await esperar(400);
      var popup = document.querySelector('.swal2-popup');
      r.reactivar_pide_confirmacion = !!popup && /Reactivar/.test(popup.textContent) && /INACTIVA TRES/.test(popup.textContent);
      r.sin_patch_antes_de_confirmar = llamadas('PATCH', /reactivar$/).length === 0;
      // cancelar no hace nada
      var cancelar = document.querySelector('.swal2-cancel'); if (cancelar) cancelar.click(); await esperar(400);
      r.cancelar_no_hace_patch = llamadas('PATCH', /reactivar$/).length === 0;
      btnReac = filas().filter(function (f) { return /INACTIVA TRES/.test(f.textContent); })[0].querySelector('[data-accion="reactivar"]');
      btnReac.click(); await esperar(400);
      var ok = document.querySelector('.swal2-confirm'); if (ok) ok.click(); await esperar(600);
      var patch = llamadas('PATCH', /\/3\/reactivar$/);
      r.reactivar_hace_patch_al_id_correcto = patch.length === 1;
      r.recarga_la_lista_tras_reactivar = llamadas('GET', /\?inactivos=1$/).length >= 2;
      var exito = document.querySelector('.swal2-popup');
      r.muestra_exito = !!exito && /Reactivad/.test(exito.textContent) && /Operación simulada/.test(exito.textContent);
      var cerrar = document.querySelector('.swal2-confirm'); if (cerrar) cerrar.click(); await esperar(400);

      // Anular una activa: confirma y hace el DELETE
      var activa = filas().filter(function (f) { return /ACTIVA UNO/.test(f.textContent); })[0];
      activa.querySelector('[data-accion="anular"]').click(); await esperar(400);
      popup = document.querySelector('.swal2-popup');
      r.anular_pide_confirmacion = !!popup && /Anular/.test(popup.textContent);
      ok = document.querySelector('.swal2-confirm'); if (ok) ok.click(); await esperar(600);
      r.anular_hace_delete = llamadas('DELETE', /\/1$/).length === 1;
      exito = document.querySelector('.swal2-popup');
      r.anular_muestra_exito = !!exito && /Anulad/.test(exito.textContent);
      // Agregar y Editar siguen funcionando (usan pedir/escapar del helper)
      var modalEl = document.getElementById('modalFormulario');
      var btnAgregar = document.getElementById('btnAgregar');
      btnAgregar.click(); await esperar(900);
      r.agregar_abre_modal = modalEl.classList.contains('show');
      r.agregar_titulo = /Agregar/.test(document.getElementById('modalTitle').textContent);
      r.agregar_combos_cargados = Array.prototype.slice.call(modalEl.querySelectorAll('select')).every(function (sel) { return sel.options.length > 1; });
      modalEl.querySelector('[data-bs-dismiss="modal"]').click(); await esperar(700);
      r.modal_se_cierra = !modalEl.classList.contains('show');
      var dos = filas().filter(function (f) { return /ACTIVA DOS/.test(f.textContent); })[0];
      dos.querySelector('[data-accion="editar"]').click(); await esperar(900);
      r.editar_abre_modal = modalEl.classList.contains('show');
      r.editar_titulo = /Editar/.test(document.getElementById('modalTitle').textContent);
      r.editar_precarga_la_descripcion = document.getElementById('txtDescripcion').value === 'ACTIVA DOS';
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
for nombre, (url, sust, idk) in VISTAS.items():
    html = c.get(url).get_data(as_text=True)
    html = html.replace('"/static/', '"' + STATIC)
    html = html.replace('<head>', '<head>' + MOCK, 1)
    html = html.replace('</body>', PRUEBA + '</body>', 1)
    archivo = SALIDA / f'{nombre}.html'
    archivo.write_text(html, encoding='utf-8')
    proc = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--no-first-run',
                           '--virtual-time-budget=20000', '--dump-dom', archivo.as_uri()],
                          capture_output=True, text=True, encoding='utf-8', timeout=120)
    m = re.search(r'<pre id="resultado"[^>]*>(.*?)</pre>', proc.stdout, re.S)
    if not m or not m.group(1).strip():
        print(f'FAIL {nombre}: la página no produjo resultado (¿error de sintaxis?)'); total_fallos += 1
        print(proc.stderr[-400:]); continue
    import html as _h
    r = json.loads(_h.unescape(m.group(1)))
    esperado_true = [k for k, v in r.items() if isinstance(v, bool)]
    malos = [k for k in esperado_true if not r[k]]
    if 'EXCEPCION' in r:
        malos.append('EXCEPCION')
    esperado = {'filas_activas': 2, 'filas_con_inactivos': 3}
    malos += [k for k, v in esperado.items() if r.get(k) != v]
    print(('OK  ' if not malos else 'FAIL'), nombre, '| checks:', len(esperado_true), '| etiqueta:', r.get('etiqueta_switch'), '| filas', r.get('filas_activas'), '->', r.get('filas_con_inactivos'))
    if malos:
        total_fallos += 1
        print('     fallan:', malos)
        print('     detalle:', json.dumps(r, ensure_ascii=False)[:900])
print('VISTAS CON FALLOS:', total_fallos)
