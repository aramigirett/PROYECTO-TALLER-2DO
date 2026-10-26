"""Montos y cantidades en un navegador real (Edge headless): formateo EN VIVO con puntos de miles mientras se escribe (sin que el cursor salte, sin letras,
comas ni decimales, con tope de dígitos), limpiar / formatear, campos creados después de cargar la página, y una pantalla real (Tipo Tratamiento, con fetch
simulado) de punta a punta: el campo se ve "1.500.000", la tabla muestra "Gs. 200.000" y lo que viaja al servidor es el entero SIN puntos.
Uso: .\\.venv\\Scripts\\python.exe -I tests\\facturacion\\browser_montos.py <carpeta de salida>   (necesita Edge)"""
import sys, json, re, subprocess, pathlib, html as _h
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app import app

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SALIDA = pathlib.Path(sys.argv[1]); SALIDA.mkdir(parents=True, exist_ok=True)
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
STATIC = (RAIZ / 'app' / 'static').as_uri() + '/'

ESCRIBIR = r"""
function escribir(el, texto) {      // simula teclear: inserta en el cursor, mueve el cursor y dispara 'input' (como el navegador)
  el.focus();
  for (var i = 0; i < texto.length; i++) {
    var s = el.selectionStart, e = el.selectionEnd;
    el.value = el.value.slice(0, s) + texto.charAt(i) + el.value.slice(e);
    el.setSelectionRange(s + 1, s + 1);
    el.dispatchEvent(new Event('input', {bubbles: true}));
  }
}
function borrarAtras(el) {           // Backspace en el cursor
  var s = el.selectionStart, e = el.selectionEnd;
  if (s === e) { s = Math.max(0, s - 1); }
  el.value = el.value.slice(0, s) + el.value.slice(e);
  el.setSelectionRange(s, s);
  el.dispatchEvent(new Event('input', {bubbles: true}));
}
function pegar(el, texto) {          // pegar reemplaza todo
  el.focus(); el.value = texto; el.setSelectionRange(texto.length, texto.length);
  el.dispatchEvent(new Event('input', {bubbles: true}));
}
function cursorEn(el, p) { el.focus(); el.setSelectionRange(p, p); }
"""

PAGINA_SUELTA = f"""<!doctype html><html><head><meta charset="utf-8"></head><body>
<input id="a" data-monto><input id="c" data-cantidad><input id="otro">
<pre id="resultado" style="display:none"></pre>
<script src="{STATIC}js/facturacion-validadores.js"></script>
<script>{ESCRIBIR}
var V = window.FacturacionValidadores, r = {{}};
try {{
  var a = document.getElementById('a'), c = document.getElementById('c');
  escribir(a, '100000');
  r.formatea_en_vivo = a.value === '100.000';
  r.cursor_al_final = a.selectionStart === a.value.length;
  escribir(a, 'abc,.-+ '); r.sin_letras_comas_ni_decimales = a.value === '100.000' && a.selectionStart === a.value.length;
  a.value = ''; escribir(a, '1,5'); r.coma_no_cuenta = a.value === '15';
  pegar(a, '1.234.567'); r.pegar_con_puntos = a.value === '1.234.567';
  pegar(a, 'Gs. 2500000 abc'); r.pegar_con_basura = a.value === '2.500.000';
  pegar(a, '1500000'); cursorEn(a, 1); escribir(a, '5');
  r.insertar_en_medio_valor = a.value === '15.500.000';
  r.insertar_en_medio_cursor = a.selectionStart === 2;      // justo después del 5 recién escrito ("15|.500.000")
  pegar(a, '1234'); cursorEn(a, 1); escribir(a, '9'); r.insertar_en_medio_sin_salto = a.value === '19.234' && a.selectionStart === 2;
  pegar(a, '1234'); cursorEn(a, 3); borrarAtras(a); r.borrar_en_medio = a.value === '134' && a.selectionStart === 1;
  pegar(a, '1234567'); cursorEn(a, 5); borrarAtras(a); r.borrar_cerca_del_punto = a.value === '123.567' && a.selectionStart === 3;
  pegar(a, '100000'); cursorEn(a, 5); borrarAtras(a); r.borrar_el_punto_no_cambia_nada_raro = a.value === '10.000' || a.value === '100.000';
  a.value = '0'; cursorEn(a, 1); escribir(a, '5'); r.cero_inicial_se_va = a.value === '5';
  pegar(a, '000'); r.solo_ceros_queda_un_cero = a.value === '0';
  pegar(a, '0012345'); r.ceros_a_la_izquierda = a.value === '12.345';
  pegar(a, '9999999999999'); r.tope_12_digitos = a.value === '999.999.999.999';
  a.value = ''; escribir(a, '9999999999999'); r.tope_al_teclear = a.value === '999.999.999.999' && a.selectionStart === a.value.length;
  pegar(c, '12345678901'); r.cantidad_tope_10 = c.value === '1.234.567.890';
  pegar(c, '1500'); r.cantidad_con_miles = c.value === '1.500';
  var otro = document.getElementById('otro'); escribir(otro, '12345'); r.campo_sin_atributo_no_se_toca = otro.value === '12345';
  var nuevo = document.createElement('input'); nuevo.setAttribute('data-monto', ''); document.body.appendChild(nuevo);
  escribir(nuevo, '2500000'); r.campo_creado_despues_tambien = nuevo.value === '2.500.000';
  var viejo = document.createElement('input'); viejo.setAttribute('data-monto', ''); viejo.setAttribute('data-max-digits', '4'); document.body.appendChild(viejo);
  escribir(viejo, '123456'); r.tope_propio_data_max_digits = viejo.value === '1.234';
  r.limpiar = V.limpiarMonto('100.000') === '100000' && V.limpiarMonto('Gs. 1.500') === '1500' && V.limpiarMonto('') === '' && V.limpiarMonto('abc') === ''
              && V.limpiarMonto('007') === '7' && V.limpiarMonto('000') === '0' && V.limpiarMonto(null) === '' && V.limpiarMonto('1,5') === '15';
  r.formatear = V.formatearMonto(100000) === '100.000' && V.formatearMonto(0) === '0' && V.formatearMonto(999) === '999' && V.formatearMonto(1000) === '1.000'
                && V.formatearMonto(999999999999) === '999.999.999.999' && V.formatearMonto(-1500) === '-1.500' && V.formatearMonto('') === '' && V.formatearMonto(null) === ''
                && V.formatearMonto(undefined) === '' && V.formatearMonto('15000') === '15.000' && V.formatearMonto('100.000') === '100.000' && V.formatearMonto(1234.6) === '1.235';
  r.formatoGs = V.formatoGs(1500000) === 'Gs. 1.500.000' && V.formatoGs(0) === 'Gs. 0';
  r.valorCampo = V.valorCampo(a) === V.limpiarMonto(a.value) && V.valorCampo(otro) === otro.value && V.valorCampo(null) === '';
  a.value = '1.500'; r.valorCampo_sin_puntos = V.valorCampo(a) === '1500';
}} catch (e) {{ r.EXCEPCION = String(e && e.stack || e); }}
document.getElementById('resultado').textContent = JSON.stringify(r);
</script></body></html>"""

MOCK = r"""
<script>
window.__posts = []; window.__errores = [];
window.addEventListener('error', function (e) { window.__errores.push(String(e.message)); });
window.addEventListener('unhandledrejection', function (e) { window.__errores.push('promesa: ' + String(e.reason)); });
window.fetch = function (url, opts) {
  var metodo = (opts && opts.method) || 'GET';
  var cuerpo = {success: true, data: [], error: null, mensaje: 'Operación simulada.'};
  if (metodo === 'POST' || metodo === 'PUT') window.__posts.push({url: String(url), method: metodo, body: JSON.parse(opts.body)});
  var fila = {id_tipo_tratamiento: 1, descripcion: 'LIMPIEZA', precio: 200000, iva: 10, activo: true};
  if (metodo === 'GET' && /\/api\/v1\/tipos-tratamiento\/1$/.test(url)) cuerpo.data = fila;
  else if (metodo === 'GET' && /\/api\/v1\/tipos-tratamiento/.test(url)) cuerpo.data = [fila];
  return Promise.resolve({ok: true, status: 200, json: function () { return Promise.resolve(cuerpo); }});
};
</script>"""

PRUEBA_PAGINA = r"""
<pre id="resultado" style="display:none"></pre>
<script>""" + ESCRIBIR + r"""
(function () {
  var r = {}; var esperar = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };
  (async function () {
    try {
      await esperar(600);
      r.tabla_muestra_gs = /Gs\. 200\.000/.test(document.querySelector('table tbody').textContent);
      document.getElementById('btnAgregar').click(); await esperar(500);
      var precio = document.getElementById('txt_precio'), desc = document.getElementById('txtClave');
      r.campo_sin_maxlength = !precio.hasAttribute('maxlength') && precio.hasAttribute('data-monto');
      desc.value = 'Endodoncia'; desc.dispatchEvent(new Event('input', {bubbles: true}));
      escribir(precio, '1500000');
      r.campo_formateado = precio.value === '1.500.000';
      escribir(precio, 'x'); r.letra_ignorada = precio.value === '1.500.000';
      document.getElementById('formulario').requestSubmit(); await esperar(600);
      var p = window.__posts[0];
      r.se_envio = !!p;
      r.envia_entero_sin_puntos = !!p && p.body.precio === '1500000';
      r.sin_errores_de_validacion = !document.getElementById('txt_precio').classList.contains('is-invalid');
      // editar: el valor del registro viene formateado en el campo
      var btn = document.querySelector('[data-accion="editar"]');
      if (btn) { btn.click(); await esperar(500); r.editar_precarga_formateada = document.getElementById('txt_precio').value === '200.000'; }
      else { r.editar_precarga_formateada = 'sin botón editar'; }
      // validación: monto vacío o cero se rechaza igual
      precio.value = ''; precio.dispatchEvent(new Event('input', {bubbles: true}));
      document.getElementById('formulario').requestSubmit(); await esperar(300);
      r.vacio_se_rechaza = document.getElementById('txt_precio').classList.contains('is-invalid');
      escribir(precio, '0'); document.getElementById('formulario').requestSubmit(); await esperar(300);
      r.cero_se_rechaza_en_precio = document.getElementById('txt_precio').classList.contains('is-invalid') && window.__posts.length === 1;
      r.sin_errores_js = window.__errores.length === 0;
      if (window.__errores.length) r.errores = window.__errores;
    } catch (e) { r.EXCEPCION = String(e && e.stack || e); }
    document.getElementById('resultado').textContent = JSON.stringify(r);
  })();
})();
</script>"""


def correr(nombre, html):
    archivo = SALIDA / f'{nombre}.html'
    archivo.write_text(html, encoding='utf-8')
    proc = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--no-first-run',
                           '--virtual-time-budget=20000', '--dump-dom', archivo.as_uri()], capture_output=True, text=True, encoding='utf-8', timeout=120)
    m = re.search(r'<pre id="resultado"[^>]*>(.*?)</pre>', proc.stdout, re.S)
    if not m or not m.group(1).strip():
        print(f'FAIL {nombre}: la página no produjo resultado'); print(proc.stderr[-400:]); return None
    return json.loads(_h.unescape(m.group(1)))


fallos = 0
for nombre, html in (('montos-suelto', PAGINA_SUELTA),):
    r = correr(nombre, html)
    if r is None:
        fallos += 1; continue
    malos = [k for k, v in r.items() if (isinstance(v, bool) and not v) or k == 'EXCEPCION']
    for k, v in r.items():
        if isinstance(v, bool):
            print(('OK  ' if v else 'FAIL'), nombre, k)
    if 'EXCEPCION' in r:
        print('FAIL', nombre, r['EXCEPCION'])
    fallos += len(malos)

c = app.test_client()
with c.session_transaction() as s:
    s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'
html = c.get('/referenciales/tipo-tratamiento/tipo-tratamiento-index').get_data(as_text=True)
html = html.replace('"/static/', '"' + STATIC).replace('<head>', '<head>' + MOCK, 1).replace('</body>', PRUEBA_PAGINA + '</body>', 1)
r = correr('montos-tipo-tratamiento', html)
if r is None:
    fallos += 1
else:
    for k, v in r.items():
        if isinstance(v, bool):
            print(('OK  ' if v else 'FAIL'), 'tipo-tratamiento', k)
    malos = [k for k, v in r.items() if (isinstance(v, bool) and not v) or k in ('EXCEPCION', 'errores')]
    if malos:
        print('     detalle:', json.dumps(r, ensure_ascii=False)[:900])
    fallos += len(malos)
print('VISTAS CON FALLOS:', fallos)
