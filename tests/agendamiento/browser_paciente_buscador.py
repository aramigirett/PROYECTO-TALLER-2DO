"""Buscador de pacientes (paciente-buscador.js) en Agregar Cita, en un navegador real (Edge headless) con fetch simulado: un solo campo de texto (sin <select>
"Seleccione…"), sugerencias en vivo, selección automática con la cédula exacta (y mostrar el nombre completo), "Paciente no encontrado", teclado, "Cambiar paciente",
error de campo obligatorio y el id que viaja al servidor. Renderiza la vista real con Flask (sesión de Administrador).
Uso: .\\.venv\\Scripts\\python.exe -I tests\\agendamiento\\browser_paciente_buscador.py <carpeta de salida>   (necesita Edge)"""
import sys, json, re, subprocess, pathlib, html as _h
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app import app

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SALIDA = pathlib.Path(sys.argv[1]); SALIDA.mkdir(parents=True, exist_ok=True)
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
STATIC = (RAIZ / 'app' / 'static').as_uri() + '/'

MOCK = r"""
<script>
window.__calls = []; window.__errores = [];
window.addEventListener('error', function (e) { window.__errores.push(String(e.message)); });
window.addEventListener('unhandledrejection', function (e) { window.__errores.push('promesa: ' + String(e.reason)); });
var PACIENTES = [
  {id_paciente: 5, nombre: 'ANA', apellido: 'PEREZ', cedula_entidad: '1234567'},
  {id_paciente: 6, nombre: 'JUAN', apellido: 'GOMEZ', cedula_entidad: '7654321'},
  {id_paciente: 7, nombre: 'PEDRO', apellido: 'RUIZ', cedula_entidad: '123456'},
  {id_paciente: 8, nombre: 'MARÍA', apellido: 'LÓPEZ', cedula_entidad: '5555555'}
];
window.fetch = function (url, opts) {
  var metodo = (opts && opts.method) || 'GET', u = String(url);
  window.__calls.push({url: u, method: metodo, body: opts && opts.body});
  var cuerpo = {success: true, data: [], error: null, mensaje: 'Operación simulada.'};
  if (/\/api\/v1\/pacientes$/.test(u)) cuerpo.data = PACIENTES;
  if (/\/api\/v1\/agenda\/cabeceras\?/.test(u)) cuerpo.data = [{id_agenda_cabecera: 1, fecha_agenda: '2030-05-01', medico_nombre: 'LUIS GOMEZ', nombre_consultorio: 'CENTRAL'}];
  if (/\/api\/v1\/estados-cita$/.test(u)) cuerpo.data = [{id_estado_cita: 1, descripcion: 'Reservado'}, {id_estado_cita: 2, descripcion: 'Confirmado'}];
  if (/\/agenda\/cabeceras\/\d+\/detalles$/.test(u)) cuerpo.data = [{id_agenda_detalle: 11, hora_inicio: '09:00', hora_fin: '12:00', cupos_disponibles: 3}];
  return Promise.resolve({ok: true, status: 200, json: function () { return Promise.resolve(cuerpo); }});
};
</script>
"""

PRUEBA = r"""
<pre id="resultado" style="display:none"></pre>
<script>
(function () {
  var r = {}; var esperar = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };
  var $ = function (id) { return document.getElementById(id); };
  var escribir = function (v) { var el = $('txtPaciente'); el.readOnly = false; el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); };
  var items = function () { return Array.prototype.slice.call($('sugPaciente').querySelectorAll('button')); };
  var tecla = function (k) { $('txtPaciente').dispatchEvent(new KeyboardEvent('keydown', {key: k, bubbles: true, cancelable: true})); };
  var cambiar = function () { var b = $('txtPaciente').parentElement.querySelector('.btn-close'); if (b && b.style.display !== 'none') b.click(); };
  var oculta = function (el) { return getComputedStyle(el).display === 'none' || el.textContent === ''; };
  (async function () {
    try {
      await esperar(600);
      $('btnAgregar').click(); await esperar(800);
      r.sin_select_de_paciente = !document.querySelector('select#selPaciente') && !!$('txtPaciente') && $('txtPaciente').tagName === 'INPUT' && !/Seleccione/.test($('txtPaciente').closest('.mb-3').innerHTML);
      r.un_solo_campo_visible = $('txtPaciente').closest('.mb-3').querySelectorAll('input:not([type=hidden]), select').length === 1;

      r.ayuda_inicial_visible = /Escriba la cédula/.test($('hintPaciente').textContent) && !oculta($('hintPaciente'));
      escribir('ana'); await esperar(50);
      r.ayuda_oculta_mientras_hay_lista = oculta($('hintPaciente'));
      r.sugerencias_en_vivo_por_nombre = items().length === 1 && /ANA PEREZ/.test(items()[0].textContent) && /CI 1234567/.test(items()[0].textContent) && $('sugPaciente').style.display !== 'none';
      r.sin_seleccion_mientras_escribe = $('selPaciente').value === '';
      items()[0].dispatchEvent(new MouseEvent('click', {bubbles: true})); await esperar(50);
      r.clic_selecciona = $('selPaciente').value === '5' && $('txtPaciente').value === 'ANA PEREZ' && $('txtPaciente').readOnly && $('sugPaciente').style.display === 'none';
      r.elegido_sin_ayuda_y_con_x = oculta($('hintPaciente')) && $('txtPaciente').parentElement.querySelector('.btn-close').style.display !== 'none';
      cambiar(); await esperar(50);
      r.x_oculta_al_cambiar_y_vuelve_la_ayuda = $('txtPaciente').parentElement.querySelector('.btn-close').style.display === 'none' && !oculta($('hintPaciente'));
      r.cambiar_limpia = $('selPaciente').value === '' && $('txtPaciente').value === '' && !$('txtPaciente').readOnly;

      escribir('7654321'); await esperar(50);
      r.cedula_exacta_selecciona_sola = $('selPaciente').value === '6' && $('txtPaciente').value === 'JUAN GOMEZ' && $('txtPaciente').readOnly;
      cambiar(); await esperar(30);
      escribir('1.234.567'); await esperar(50);
      r.cedula_con_puntos = $('selPaciente').value === '5' && $('txtPaciente').value === 'ANA PEREZ';
      cambiar(); await esperar(30);

      escribir('123456'); await esperar(50);
      r.cedula_ambigua_no_se_elige_sola = $('selPaciente').value === '' && items().length === 2 && /PEDRO RUIZ/.test(items()[0].textContent) && /ANA PEREZ/.test(items()[1].textContent);
      var L = $('sugPaciente'), I = $('txtPaciente'), lr = L.getBoundingClientRect(), ir = I.getBoundingClientRect(), cs = getComputedStyle(L);
      r.dropdown_absoluto_bajo_el_campo = cs.position === 'absolute' && lr.top >= ir.bottom - 1 && Math.abs(lr.left - ir.left) <= 1;
      r.dropdown_mismo_ancho_que_el_campo = Math.abs(lr.width - ir.width) <= 2;
      r.dropdown_fondo_blanco_borde_y_sombra = /^(rgba?\(255, 255, 255(, 1)?\)|color\(srgb 1 1 1\))$/.test(cs.backgroundColor) && parseFloat(cs.borderTopWidth) >= 1 && cs.boxShadow !== 'none';
      r.dropdown_sobre_el_modal_con_scroll = parseInt(cs.zIndex, 10) > 1055 && cs.maxHeight === '260px' && cs.overflowY === 'auto';
      r.no_tapa_a_la_ayuda = oculta($('hintPaciente')) && !(lr.top < $('hintPaciente').getBoundingClientRect().bottom && lr.bottom > $('hintPaciente').getBoundingClientRect().top && !oculta($('hintPaciente')));
      var fila2 = items()[1], n2 = fila2.children[0], c2 = fila2.children[1];
      r.fila_nombre_negrita_ci_gris = parseInt(getComputedStyle(n2).fontWeight, 10) >= 600 && /^CI 1234567$/.test(c2.textContent) && getComputedStyle(c2).color !== getComputedStyle(n2).color;
      r.fila_con_hover_de_tabler = fila2.classList.contains('list-group-item-action') && !fila2.classList.contains('active') && items()[0].classList.contains('active');
      tecla('ArrowDown'); await esperar(30);
      r.flecha_abajo_mueve_la_fila_activa = items()[1].classList.contains('active') && !items()[0].classList.contains('active');
      tecla('ArrowUp'); await esperar(30);
      r.flecha_arriba_vuelve = items()[0].classList.contains('active');
      tecla('Enter'); await esperar(50);
      r.enter_elige_la_primera = $('selPaciente').value === '7' && $('txtPaciente').value === 'PEDRO RUIZ';
      cambiar(); await esperar(30);
      escribir('1234567'); await esperar(50);
      r.cedula_larga_si_es_unica = $('selPaciente').value === '5';
      cambiar(); await esperar(30);

      escribir('zzz'); await esperar(50);
      r.no_encontrado_por_nombre = /Paciente no encontrado/.test($('hintPaciente').textContent) && !oculta($('hintPaciente')) && $('sugPaciente').style.display === 'none' && $('selPaciente').value === '';
      escribir('99999999'); await esperar(50);
      r.no_encontrado_por_cedula = /Paciente no encontrado/.test($('hintPaciente').textContent) && $('selPaciente').value === '';
      escribir('maria'); await esperar(50);
      r.sin_distinguir_tildes_ni_mayusculas = items().length === 1 && /MARÍA LÓPEZ/.test(items()[0].textContent) && !/no encontrado/.test($('hintPaciente').textContent);
      escribir(''); await esperar(30);
      r.vaciar_limpia_todo = $('sugPaciente').style.display === 'none' && !/no encontrado/.test($('hintPaciente').textContent) && $('selPaciente').value === '';

      escribir('p'); await esperar(50);
      escribir('e'); await esperar(50);
      r.flechas_y_enter = (function () { tecla('ArrowDown'); return true; })() && (tecla('Enter'), true);
      await esperar(50);
      r.flechas_y_enter = r.flechas_y_enter && ['5', '6', '7', '8'].indexOf($('selPaciente').value) >= 0 && $('txtPaciente').readOnly;
      cambiar(); await esperar(30);
      escribir('ana'); await esperar(30); tecla('Escape'); await esperar(30);
      r.escape_cierra = $('sugPaciente').style.display === 'none' && $('selPaciente').value === '';

      var cambios = 0; $('selPaciente').addEventListener('change', function () { cambios++; });
      escribir('7654321'); await esperar(50);
      r.avisa_el_cambio_a_la_pantalla = cambios >= 1;

      // envío sin paciente: error sobre el campo visible; con paciente: viaja el id
      cambiar(); await esperar(30);
      $('formulario').requestSubmit(); await esperar(300);
      r.sin_paciente_marca_el_campo_visible = $('txtPaciente').classList.contains('is-invalid') && /paciente es obligatorio/.test($('txtPaciente').closest('.mb-3').querySelector('.invalid-feedback').textContent);
      escribir('1234567'); await esperar(300);
      r.al_elegir_se_quita_el_error = !$('txtPaciente').classList.contains('is-invalid');
      var sel = $('selAgenda'); sel.value = '1'; sel.dispatchEvent(new Event('change', {bubbles: true})); await esperar(400);
      $('selHorario').value = '11'; $('selHorario').dispatchEvent(new Event('change', {bubbles: true}));
      $('txtHora').value = '09:30'; $('txtMotivo').value = 'Control'; $('selEstado').value = '1';
      $('formulario').requestSubmit(); await esperar(500);
      var p = window.__calls.filter(function (c) { return c.method === 'POST' && /\/api\/v1\/citas$/.test(c.url); })[0];
      r.la_cita_lleva_el_id_del_paciente = !!p && JSON.parse(p.body).id_paciente === 5;
      r.sin_errores_js = window.__errores.length === 0;
      if (window.__errores.length) r.errores = window.__errores;
    } catch (e) { r.EXCEPCION = String(e && e.stack || e); }
    $('resultado').textContent = JSON.stringify(r);
  })();
})();
</script>
"""

c = app.test_client()
with c.session_transaction() as s:
    s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'
html = c.get('/referenciales/cita/cita-index').get_data(as_text=True)
html = html.replace('"/static/', '"' + STATIC).replace('<head>', '<head>' + MOCK, 1).replace('</body>', PRUEBA + '</body>', 1)
archivo = SALIDA / 'paciente-buscador-cita.html'
archivo.write_text(html, encoding='utf-8')
proc = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--no-first-run', '--virtual-time-budget=30000', '--dump-dom', archivo.as_uri()],
                      capture_output=True, text=True, encoding='utf-8', timeout=120)
m = re.search(r'<pre id="resultado"[^>]*>(.*?)</pre>', proc.stdout, re.S)
if not m or not m.group(1).strip():
    print('FAIL: la página no produjo resultado'); print(proc.stderr[-400:]); print('VISTAS CON FALLOS: 1'); sys.exit(1)
r = json.loads(_h.unescape(m.group(1)))
malos = [k for k, v in r.items() if (isinstance(v, bool) and not v) or k in ('EXCEPCION', 'errores')]
for k, v in r.items():
    if isinstance(v, bool):
        print(('OK  ' if v else 'FAIL'), k)
if malos:
    print('     detalle:', json.dumps(r, ensure_ascii=False)[:1200])
print('VISTAS CON FALLOS:', len(malos))
