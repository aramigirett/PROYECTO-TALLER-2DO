"""Requisitos de contraseña en vivo (password-requisitos.js) en Agregar / Editar Usuario, en Edge headless con fetch simulado. Compara además el componente con
password_policy.py para varias contraseñas. Uso: .\\.venv\\Scripts\\python.exe -I tests\\seguridad\\browser_password.py <carpeta de salida>   (necesita Edge)"""
import sys, json, re, subprocess, pathlib, html as _h
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app import app
from app.rutas.modulo_seguridad.password_policy import validar_password_compleja

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SALIDA = pathlib.Path(sys.argv[1]); SALIDA.mkdir(parents=True, exist_ok=True)
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
STATIC = (RAIZ / 'app' / 'static').as_uri() + '/'
CASOS = ['', 'abc', 'Abcdefg1', 'abcdefg1!', 'ABCDEFG1!', 'Abcdefgh!', 'Abcdef1!', 'Ñandú123!', 'Abc1234_', 'Abc 1234', '12345678', 'Passw0rd']
ESPERADO = {p: validar_password_compleja(p) is None for p in CASOS}

MOCK = r"""<script>
window.__errores = [];
window.addEventListener('error', function (e) { window.__errores.push(String(e.message)); });
var U = {id_usuario: 3, nombre_completo: 'ANA PEREZ', tipo_persona: 'Funcionario', id_funcionario: 4, id_rol: 2, nombre_rol: 'Recepcion', ci_ruc: '1234567', correo: 'a@b.com', activo: true, bloqueado: false};
window.fetch = function (url, opts) {
  var u = String(url), c = {success: true, data: [], error: null};
  if (/\/api\/v1\/usuarios$/.test(u)) c.data = [U];
  if (/disponibles/.test(u)) c.data = [{id_funcionario: 4, nombre_completo: 'ANA PEREZ', ci_ruc: '1234567'}];
  if (/\/api\/v1\/roles$/.test(u)) c.data = [{id_rol: 2, nombre_rol: 'Recepcion'}];
  return Promise.resolve({ok: true, status: 200, json: function () { return Promise.resolve(c); }});
};
</script>"""

PRUEBA = r"""<pre id="resultado" style="display:none"></pre><script>
(function () {
  var r = {}, $ = function (id) { return document.getElementById(id); }, esperar = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };
  var escribir = function (v) { $('txtPassword').value = v; $('txtPassword').dispatchEvent(new Event('input', {bubbles: true})); };
  var marcas = function () { return Array.prototype.map.call(document.querySelectorAll('#reqPassword li'), function (li) { return li.textContent.trim().charAt(0) + (li.classList.contains('text-success') ? 'v' : 'r'); }).join(','); };
  (async function () {
    try {
      await esperar(600);
      var CASOS = __CASOS__, ESPERADO = __ESPERADO__;
      r.coincide_con_password_policy = CASOS.every(function (p) { return PasswordRequisitos.cumple(p) === ESPERADO[p]; });
      $('btnAgregar').click(); await esperar(700);
      r.cuatro_requisitos = document.querySelectorAll('#reqPassword li').length === 4 && /8 caracteres/.test($('reqPassword').textContent) && /mayúscula/.test($('reqPassword').textContent)
                            && /número/.test($('reqPassword').textContent) && /símbolo/.test($('reqPassword').textContent);
      r.sin_texto_gris_fijo = $('hintPassword').style.display === 'none';
      r.inicio_todos_x_rojo = marcas() === '✗r,✗r,✗r,✗r' && $('btnGuardar').disabled;
      escribir('abc'); r.abc_todo_rojo = marcas() === '✗r,✗r,✗r,✗r' && $('btnGuardar').disabled;
      escribir('abcdefgh'); r.largo_ok = marcas() === '✓v,✗r,✗r,✗r' && $('btnGuardar').disabled;
      escribir('Abcdefg1'); r.falta_solo_simbolo = marcas() === '✓v,✓v,✓v,✗r' && $('btnGuardar').disabled;
      escribir('Abcdef1!'); r.todos_verdes_habilita = marcas() === '✓v,✓v,✓v,✓v' && !$('btnGuardar').disabled;
      escribir('Abcdef1'); r.vuelve_a_deshabilitar = $('btnGuardar').disabled && marcas() === '✗r,✓v,✓v,✗r';
      escribir(''); r.vacio_en_alta_deshabilitado = $('btnGuardar').disabled;
      document.querySelector('#modalFormulario .btn-close, #modalFormulario [data-bs-dismiss="modal"]').click(); await esperar(500);
      document.querySelector('[data-accion="editar"]').click(); await esperar(800);
      r.edicion_vacio_conserva_y_habilita = !$('btnGuardar').disabled && $('hintPassword').style.display !== 'none' && /vacía/.test($('hintPassword').textContent);
      escribir('abc'); r.edicion_si_escribe_debe_cumplir = $('btnGuardar').disabled;
      escribir('Abcdef1!'); r.edicion_valida_habilita = !$('btnGuardar').disabled;
      r.sin_errores_js = window.__errores.length === 0;
      if (window.__errores.length) r.errores = window.__errores;
    } catch (e) { r.EXCEPCION = String(e && e.stack || e); }
    $('resultado').textContent = JSON.stringify(r);
  })();
})();
</script>"""

c = app.test_client()
with c.session_transaction() as s:
    s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'
html = c.get('/referenciales/usuario/usuario-index').get_data(as_text=True)
prueba = PRUEBA.replace('__CASOS__', json.dumps(CASOS, ensure_ascii=False)).replace('__ESPERADO__', json.dumps(ESPERADO, ensure_ascii=False))
html = html.replace('"/static/', '"' + STATIC).replace('<head>', '<head>' + MOCK, 1).replace('</body>', prueba + '</body>', 1)
archivo = SALIDA / 'usuario-password.html'
archivo.write_text(html, encoding='utf-8')
proc = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--no-first-run', '--virtual-time-budget=30000', '--dump-dom', archivo.as_uri()],
                      capture_output=True, text=True, encoding='utf-8', timeout=120)
m = re.search(r'<pre id="resultado"[^>]*>(.*?)</pre>', proc.stdout, re.S)
if not m or not m.group(1).strip():
    print('FAIL: sin resultado'); print(proc.stderr[-300:]); sys.exit(1)
r = json.loads(_h.unescape(m.group(1)))
malos = [k for k, v in r.items() if (isinstance(v, bool) and not v) or k in ('EXCEPCION', 'errores')]
for k, v in r.items():
    if isinstance(v, bool):
        print(('OK  ' if v else 'FAIL'), k)
if malos:
    print('     detalle:', json.dumps(r, ensure_ascii=False)[:900])
print('VISTAS CON FALLOS:', len(malos))
