"""Prueba las pantallas Auditoría de Cambios y Tablero de Accesos en un navegador real (Edge headless) con fetch simulado.
Renderiza cada vista con Flask (sesión de Administrador), reescribe /static a file:// y agrega un script de prueba que usa el DOM,
Bootstrap y SweetAlert2 reales. Uso: python -I tests\\seguridad\\browser_auditoria.py <carpeta de salida>. No toca la base."""
import json, pathlib, re, subprocess, sys
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from app import app

SALIDA = pathlib.Path(sys.argv[1]); SALIDA.mkdir(parents=True, exist_ok=True)
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
STATIC = (RAIZ / 'app' / 'static').as_uri() + '/'

MOCK = r"""
<script>
window.__calls = []; window.__errores = [];
window.addEventListener('error', function (e) { window.__errores.push(String(e.message)); });
window.addEventListener('unhandledrejection', function (e) { window.__errores.push('promesa: ' + String(e.reason)); });
var ALERTA = {tipo: 'REACTIVACIONES_REPETIDAS', id_usuario: 1, usuario: 'ANA PEREZ', desde: '2026-10-01', hasta: '2026-10-20', entidad: 'caja',
              id_registro: 7, accion: 'REACTIVACION', cantidad: 3, descripcion: 'El registro caja #7 se reactivó 3 veces en 30 días (umbral: 3).'};
function filaCambio(i) { return {id_auditoria_cambio: i, fecha_hora: '2026-10-2' + (i % 5) + ' 10:11:12', id_usuario: 1, usuario: 'ANA <b>PEREZ</b>', ci_ruc: '123',
  ip: '10.0.0.1', modulo: 'Módulo Facturación', entidad: 'venta_cab', entidad_etiqueta: 'Venta', id_registro: i, accion: i % 2 ? 'BAJA' : 'ALTA',
  accion_etiqueta: i % 2 ? 'Baja / Anulación' : 'Alta', detalle: 'Total: 100'}; }
window.fetch = function (url, opts) {
  url = String(url); window.__calls.push({url: url, method: (opts && opts.method) || 'GET'});
  var cuerpo = {success: true, data: [], error: null};
  if (/auditoria-cambios\/filtros/.test(url)) {
    cuerpo.data = {usuarios: [{id_usuario: 1, nombre: 'ANA PEREZ', ci_ruc: '123'}], modulos: ['Referenciales Facturación', 'Módulo Facturación', 'Módulo Seguridad'],
      entidades: [{valor: 'caja', etiqueta: 'Caja'}, {valor: 'venta_cab', etiqueta: 'Venta'}],
      acciones: [{valor: 'ALTA', etiqueta: 'Alta'}, {valor: 'BAJA', etiqueta: 'Baja / Anulación'}, {valor: 'REACTIVACION', etiqueta: 'Reactivación'}]};
  } else if (/auditoria-cambios\/alertas/.test(url)) {
    cuerpo.data = window.__sinAlertas ? [] : [ALERTA];
  } else if (/auditoria-cambios\/\d+$/.test(url)) {
    var f = filaCambio(2); f.campos = [{campo: 'Teléfono', anterior: '1', nuevo: '2'}, {campo: 'Estado', anterior: '', nuevo: '<img src=x onerror=window.__xss=1>'}];
    f.mostrar_texto = true; cuerpo.data = f;
  } else if (/auditoria-cambios\?/.test(url)) {
    cuerpo.data = [1, 2, 3].map(filaCambio); cuerpo.total = 53; cuerpo.pagina = parseInt((/pagina=(\d+)/.exec(url) || [0, 1])[1], 10); cuerpo.por_pagina = 25; cuerpo.paginas = 3;
  } else if (/auditoria\/intentos/.test(url)) {
    cuerpo.data = []; for (var i = 0; i < 60; i++) cuerpo.data.push({fecha_hora: '2026-10-24 10:00:' + (10 + i % 50), ci_ruc_ingresado: '1234' + i, accion: 'LOGIN',
      resultado: i % 2 ? 'EXITOSO' : 'CREDENCIALES_INVALIDAS', ip: '10.0.0.1', pais_detectado: null, actor_ci_ruc: null});
  }
  return Promise.resolve({ok: true, status: 200, json: function () { return Promise.resolve(cuerpo); }});
};
window.open = function (u) { window.__abierto = String(u); };
</script>
"""

PRUEBA_CAMBIOS = r"""
<pre id="resultado" style="display:none"></pre>
<script>
(function () {
  var r = {}; var esperar = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };
  var $ = function (id) { return document.getElementById(id); };
  var llamadas = function (re) { return window.__calls.filter(function (c) { return re.test(c.url); }); };
  (async function () {
    try {
      await esperar(500);
      r.sin_errores = window.__errores.length === 0;
      r.filas = $('tbodyAuditoria').querySelectorAll('tr').length;
      r.fecha_formateada = /\d{2}\/\d{2}\/2026 10:11:12/.test($('tbodyAuditoria').textContent);
      r.baja_se_muestra_como_baja_anulacion = /Baja \/ Anulación/.test($('tbodyAuditoria').textContent);
      r.html_escapado = $('tbodyAuditoria').innerHTML.indexOf('<b>') < 0 && /ANA &lt;b&gt;PEREZ/.test($('tbodyAuditoria').innerHTML);
      r.info_paginas = $('infoPagina').textContent + ' | ' + $('lblPagina').textContent;
      r.por_defecto_7_dias = (function () { var d = new Date($('fHasta').value), a = new Date($('fDesde').value); return Math.round((d - a) / 86400000) === 6; })();
      r.filtros_cargados = $('fUsuario').options.length === 2 && $('fModulo').options.length === 4 && $('fEntidad').options.length === 3 && $('fAccion').options.length === 4;
      r.badge_alertas = $('badgeAlertas').textContent === '1' && /bg-danger/.test($('badgeAlertas').className);
      r.alerta_visible = /Reactivaciones repetidas/.test($('listaAlertas').textContent) && /ANA PEREZ/.test($('listaAlertas').textContent);
      r.sin_boton_modificar = !document.querySelector('[data-accion="editar"],[data-accion="anular"],[data-accion="reactivar"]');
      // pedido inicial: usa fechas y paginación
      var inicial = llamadas(/auditoria-cambios\?/)[0].url;
      r.pedido_inicial = /desde=/.test(inicial) && /hasta=/.test(inicial) && /pagina=1/.test(inicial) && /por_pagina=25/.test(inicial);
      // siguiente página
      $('btnSiguiente').click(); await esperar(200);
      r.siguiente_pide_pagina_2 = /pagina=2/.test(llamadas(/auditoria-cambios\?/).pop().url);
      // aplicar alerta
      document.querySelector('[data-alerta="0"]').click(); await esperar(300);
      var u = llamadas(/auditoria-cambios\?/).pop().url;
      r.alerta_filtra_el_listado = /entidad=caja/.test(u) && /id_registro=7/.test(u) && /accion=REACTIVACION/.test(u) && /desde=2026-10-01/.test(u) && /hasta=2026-10-20/.test(u) && /pagina=1/.test(u);
      r.alerta_muestra_chip = $('chipRegistro').style.display !== 'none' && /7/.test($('chipRegistro').textContent);
      r.alerta_no_fija_usuario = !/id_usuario=/.test(u);
      // quitar el chip
      $('quitarRegistro').click(); await esperar(300);
      r.quitar_chip_saca_id_registro = !/id_registro=/.test(llamadas(/auditoria-cambios\?/).pop().url) && $('chipRegistro').style.display === 'none';
      // desde > hasta
      $('fDesde').value = '2026-10-10'; $('fHasta').value = '2026-10-01';
      var antes = llamadas(/auditoria-cambios\?/).length;
      $('btnFiltrar').click(); await esperar(200);
      r.desde_mayor_que_hasta_bloquea = llamadas(/auditoria-cambios\?/).length === antes && $('errFiltros').style.display !== 'none';
      // exportar con filtros (y no si las fechas son inválidas)
      $('btnPdf').click(); r.exportar_invalido_no_abre = window.__abierto === undefined;
      $('btnLimpiar').click(); await esperar(300);
      $('fEntidad').value = 'caja'; $('fAccion').value = 'BAJA'; $('fUsuario').value = '1'; $('fModulo').value = 'Módulo Facturación';
      $('btnPdf').click();
      r.pdf_con_filtros = /\/exportar\?/.test(window.__abierto) && /formato=pdf/.test(window.__abierto) && /entidad=caja/.test(window.__abierto) && /accion=BAJA/.test(window.__abierto)
                          && /id_usuario=1/.test(window.__abierto) && /modulo=M%C3%B3dulo\+Facturaci%C3%B3n/.test(window.__abierto) && /desde=/.test(window.__abierto);
      // detalle
      document.querySelector('button[data-id]').click(); await esperar(600);
      var m = $('modalDetalle');
      r.modal_abierto = m.classList.contains('show');
      r.tabla_campo_anterior_nuevo = $('camposDetalle').rows.length === 2 && $('camposDetalle').rows[0].cells[1].textContent === '1' && $('camposDetalle').rows[0].cells[2].textContent === '2';
      r.sin_xss = !window.__xss && $('camposDetalle').innerHTML.indexOf('<img') < 0;
      r.texto_detalle = $('textoDetalle').style.display !== 'none';
      // sin alertas
      r.alertas_colapsables = (function () { $('cabAlertas').click(); var cerrado = $('cuerpoAlertas').style.display === 'none'; $('cabAlertas').click(); return cerrado && $('cuerpoAlertas').style.display !== 'none'; })();
      r.enlace_al_tablero_con_fechas = /auditoria-index\?desde=/.test($('lnkTablero').getAttribute('href'));
      r.sin_errores_final = window.__errores.length === 0;
    } catch (e) { r.excepcion = String(e && e.stack || e); }
    $('resultado').textContent = JSON.stringify(r);
  })();
})();
</script>
"""

PRUEBA_TABLERO = r"""
<pre id="resultado" style="display:none"></pre>
<script>
(function () {
  var r = {}; var esperar = function (ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); };
  var $ = function (id) { return document.getElementById(id); };
  var llamadas = function (re) { return window.__calls.filter(function (c) { return re.test(c.url); }); };
  (async function () {
    try {
      await esperar(500);
      r.sin_errores = window.__errores.length === 0;
      r.pagina_de_25 = $('tbodyIntentos').querySelectorAll('tr').length === 25 && /Página 1 de 3/.test($('lblPagina').textContent);
      r.badges = $('tbodyIntentos').querySelectorAll('.badge.bg-success-lt').length > 0 && $('tbodyIntentos').querySelectorAll('.badge.bg-danger-lt').length > 0;
      $('btnSiguiente').click(); $('btnSiguiente').click();
      r.ultima_pagina = /Página 3 de 3/.test($('lblPagina').textContent) && $('tbodyIntentos').querySelectorAll('tr').length === 10 && $('btnSiguiente').disabled;
      $('fDesde').value = '2026-10-10'; $('fHasta').value = '2026-10-01'; $('btnPdf').click();
      r.fechas_invalidas_no_exportan = window.__abierto === undefined && $('errFiltros').style.display !== 'none';
      $('fDesde').value = '2026-10-01'; $('fHasta').value = '2026-10-24'; $('fResultado').value = 'EXITOSO'; $('fResultado').dispatchEvent(new Event('change')); await esperar(200); $('btnPdf').click();
      r.pdf_con_filtros = /intentos\/exportar\?/.test(window.__abierto) && /formato=pdf/.test(window.__abierto) && /desde=2026-10-01/.test(window.__abierto) && /hasta=2026-10-24/.test(window.__abierto) && /resultado=EXITOSO/.test(window.__abierto);
      r.enlace_cruzado_con_fechas = /auditoria-cambios-index\?desde=2026-10-01&hasta=2026-10-24/.test($('lnkCambios').getAttribute('href'));
      $('btnLimpiar').click(); await esperar(300);
      r.limpiar = $('fDesde').value === '' && $('fResultado').value === '';
      r.sin_errores_final = window.__errores.length === 0;
    } catch (e) { r.excepcion = String(e && e.stack || e); }
    $('resultado').textContent = JSON.stringify(r);
  })();
})();
</script>
"""

VISTAS = {
    'auditoria-cambios': ('/referenciales/auditoria-cambios/auditoria-cambios-index', PRUEBA_CAMBIOS),
    'tablero-accesos': ('/referenciales/auditoria/auditoria-index', PRUEBA_TABLERO),
}

fallos = 0
c = app.test_client()
with c.session_transaction() as s:
    s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'
for nombre, (url, prueba) in VISTAS.items():
    html = c.get(url).get_data(as_text=True)
    html = html.replace('"/static/', '"' + STATIC).replace('<head>', '<head>' + MOCK, 1).replace('</body>', prueba + '</body>', 1)
    archivo = SALIDA / f'{nombre}.html'
    archivo.write_text(html, encoding='utf-8')
    proc = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--no-first-run',
                           '--virtual-time-budget=20000', '--dump-dom', archivo.as_uri()],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    m = re.search(r'<pre id="resultado"[^>]*>(.*?)</pre>', proc.stdout, re.S)
    if not m or not m.group(1).strip():
        print(f'FAIL {nombre}: la página no produjo resultado (¿error de sintaxis?)'); fallos += 1
        continue
    r = json.loads(re.sub(r'&quot;', '"', m.group(1)).replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>'))
    malos = [k for k, v in r.items() if v is not True and k not in ('filas', 'info_paginas')]
    for k, v in r.items():
        print(('OK  ' if v is True or k in ('filas', 'info_paginas') else 'FAIL'), nombre, k, '' if v is True else v)
    fallos += len(malos)
print('FALLOS:', 'ninguno' if not fallos else fallos)
