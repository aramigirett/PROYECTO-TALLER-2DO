/* Pantalla Informes: pestañas sin recarga, filtros, KPIs, gráficos (ApexCharts) y tablas de 10 filas con buscador.
   Cada pestaña se pide por AJAX a /api/informes/<pestaña> al abrirla y al presionar Aplicar. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var POR_PAGINA = 10;
  var FILTROS_POR_PESTANA = { resumen: ['medico'], agendamiento: ['medico'], consultorio: ['medico'], facturacion: ['condicion'], auditoria: [] };
  var SIN_EXPORTACION = { resumen: true };
  var ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  var pestana = 'resumen', graficos = [], tablas = {}, pedido = 0;

  function escapar(t) {
    return String(t === null || t === undefined ? '' : t).replace(/[&<>"']/g, function (c) { return ESCAPES[c]; });
  }
  function dosDigitos(n) { return (n < 10 ? '0' : '') + n; }
  function iso(d) { return d.getFullYear() + '-' + dosDigitos(d.getMonth() + 1) + '-' + dosDigitos(d.getDate()); }
  var V = window.FacturacionValidadores;     // formatearMonto: la función única de montos y cantidades (puntos de miles, sin decimales)
  function fmtNum(v) {
    var n = Number(v);
    if (Math.round(n) === n) return V.formatearMonto(n);
    var d = String(Math.round(n * 100) / 100).split('.');      // decimales (promedios, porcentajes): coma decimal
    return V.formatearMonto(d[0]) + ',' + d[1];
  }
  function formatear(v, tipo) {
    if (v === null || v === undefined || v === '') { return ''; }
    if (tipo === 'gs') { return 'Gs. ' + fmtNum(v); }
    if (tipo === 'pct') { return fmtNum(v) + ' %'; }
    if (tipo === 'num') { return fmtNum(v); }
    return String(v);
  }

  // ───────────────────────── filtros ─────────────────────────
  function fechasPorDefecto() {
    var hoy = new Date();
    $('fDesde').value = iso(new Date(hoy.getFullYear(), hoy.getMonth(), 1));
    $('fHasta').value = iso(hoy);
  }
  function validarFiltros() {
    var msg = '', campo = '', tipo = '';
    if (!$('fDesde').value) { msg = 'El campo "Desde" es obligatorio.'; campo = 'fDesde'; tipo = 'obligatorio'; }
    else if (!$('fHasta').value) { msg = 'El campo "Hasta" es obligatorio.'; campo = 'fHasta'; tipo = 'obligatorio'; }
    else if ($('fDesde').value > $('fHasta').value) { msg = 'La fecha "Desde" no puede ser posterior a "Hasta".'; campo = 'fDesde'; tipo = 'rango'; }
    $('errFiltros').textContent = msg;
    $('errFiltros').style.display = msg ? '' : 'none';
    if (msg && window.mostrarAvisoValidacion) {
      window.mostrarAvisoValidacion({ tipo: tipo, campo: campo, mensaje: msg });
    }
    return !msg;
  }
  function parametros() {
    var p = ['desde=' + encodeURIComponent($('fDesde').value), 'hasta=' + encodeURIComponent($('fHasta').value)];
    var aplican = FILTROS_POR_PESTANA[pestana];
    if (aplican.indexOf('medico') >= 0 && $('fMedico').value) { p.push('id_medico=' + encodeURIComponent($('fMedico').value)); }
    if (aplican.indexOf('condicion') >= 0 && $('fCondicion').value) { p.push('condicion=' + encodeURIComponent($('fCondicion').value)); }
    return p.join('&');
  }
  function ajustarControles() {
    var aplican = FILTROS_POR_PESTANA[pestana];
    $('grpMedico').style.display = aplican.indexOf('medico') >= 0 ? '' : 'none';
    $('grpCondicion').style.display = aplican.indexOf('condicion') >= 0 ? '' : 'none';
    var exporta = !SIN_EXPORTACION[pestana];
    $('btnPdf').style.display = exporta ? '' : 'none';
    $('btnExcel').style.display = exporta ? '' : 'none';
  }

  // ───────────────────────── render ─────────────────────────
  function destruirGraficos() {
    graficos.forEach(function (g) { try { g.destroy(); } catch (e) { /* ya destruido */ } });
    graficos = [];
  }
  function tarjetas(kpis) {
    if (!kpis || !kpis.length) { return ''; }
    return '<div class="row g-3 mb-3">' + kpis.map(function (k) {
      return '<div class="col-6 col-md-4 col-xl"><div class="card border shadow-sm rounded-3 h-100"><div class="card-body py-3">' +
             '<div class="text-muted small text-uppercase fw-semibold">' + escapar(k.titulo) + '</div>' +
             '<div class="fs-2 fw-bold mt-1">' + escapar(formatear(k.valor, k.formato)) + '</div></div></div></div>';
    }).join('') + '</div>';
  }
  function contenedorGrafico(g) {
    return '<div class="col-12 col-xl-' + (g.tipo === 'donut' ? '5' : '7') + '"><div class="card border shadow-sm rounded-3 h-100">' +
           '<div class="card-header bg-white py-3"><h3 class="card-title mb-0">' + escapar(g.titulo) + '</h3></div>' +
           '<div class="card-body"><div id="graf_' + escapar(g.id) + '"></div></div></div></div>';
  }
  function dibujarGrafico(g) {
    var el = $('graf_' + g.id);
    if (!el) { return; }
    var vacio = !g.series.length || g.series.every(function (s) { return !s.datos.length; });
    if (vacio) { el.innerHTML = '<div class="text-muted text-center py-4">Sin datos en el período.</div>'; return; }
    var opciones = { chart: { height: 300, toolbar: { show: false }, fontFamily: 'inherit' }, dataLabels: { enabled: false },
                     noData: { text: 'Sin datos' }, legend: { position: 'bottom' } };
    if (g.tipo === 'donut') {
      opciones.chart.type = 'donut'; opciones.series = g.series[0].datos; opciones.labels = g.categorias;
    } else {
      opciones.chart.type = g.tipo === 'line' ? 'line' : 'bar';
      opciones.series = g.series.map(function (s) { return { name: s.nombre, data: s.datos }; });
      opciones.xaxis = { categories: g.categorias, labels: { rotate: -45 } };
      opciones.stroke = { width: g.tipo === 'line' ? 3 : 0, curve: 'smooth' };
      opciones.plotOptions = { bar: { borderRadius: 3 } };
      opciones.yaxis = { labels: { formatter: function (v) { return fmtNum(Math.round(v)); } } };
    }
    var chart = new ApexCharts(el, opciones);
    chart.render();
    graficos.push(chart);
  }

  function cuerpoTabla(t) {
    var st = tablas[t.id];
    var q = st.q.trim().toLowerCase();
    st.visibles = !q ? t.filas : t.filas.filter(function (f) {
      return t.columnas.some(function (c) { return String(f[c.campo] === null || f[c.campo] === undefined ? '' : f[c.campo]).toLowerCase().indexOf(q) >= 0; });
    });
    var paginas = Math.max(1, Math.ceil(st.visibles.length / POR_PAGINA));
    st.pagina = Math.min(st.pagina, paginas);
    var ini = (st.pagina - 1) * POR_PAGINA;
    var filas = st.visibles.slice(ini, ini + POR_PAGINA);
    var html = filas.length ? filas.map(function (f) {
      return '<tr>' + t.columnas.map(function (c, i) {
        return '<td class="' + (i === 0 ? 'ps-3 ' : '') + (c.tipo === 'texto' ? '' : 'text-end') + '">' + escapar(formatear(f[c.campo], c.tipo)) + '</td>';
      }).join('') + '</tr>';
    }).join('') : '<tr><td colspan="' + t.columnas.length + '" class="text-center text-muted py-4">Sin resultados.</td></tr>';
    $('tb_' + t.id).innerHTML = html;
    $('pie_' + t.id).textContent = st.visibles.length + ' registro(s) — página ' + st.pagina + ' de ' + paginas;
    $('ant_' + t.id).disabled = st.pagina <= 1;
    $('sig_' + t.id).disabled = st.pagina >= paginas;
  }
  function contenedorTabla(t) {
    return '<div class="card border shadow-sm rounded-3 mb-3"><div class="card-header bg-white py-3 d-flex flex-wrap align-items-center justify-content-between gap-2">' +
           '<h3 class="card-title mb-0">' + escapar(t.titulo) + '</h3>' +
           '<input type="search" class="form-control form-control-sm w-auto" style="min-width:220px" placeholder="Buscar…" id="bus_' + escapar(t.id) + '" aria-label="Buscar en ' + escapar(t.titulo) + '"></div>' +
           '<div class="table-responsive"><table class="table table-vcenter table-hover card-table mb-0"><thead class="bg-light text-muted small text-uppercase"><tr>' +
           t.columnas.map(function (c, i) { return '<th class="py-3 ' + (i === 0 ? 'ps-3 ' : '') + (c.tipo === 'texto' ? '' : 'text-end') + '">' + escapar(c.titulo) + '</th>'; }).join('') +
           '</tr></thead><tbody id="tb_' + escapar(t.id) + '"></tbody></table></div>' +
           '<div class="card-footer bg-white d-flex flex-wrap align-items-center justify-content-between gap-2"><span class="small text-muted" id="pie_' + escapar(t.id) + '"></span>' +
           '<div class="btn-group btn-group-sm"><button type="button" class="btn btn-outline-secondary" id="ant_' + escapar(t.id) + '">Anterior</button>' +
           '<button type="button" class="btn btn-outline-secondary" id="sig_' + escapar(t.id) + '">Siguiente</button></div></div></div>';
  }
  function enlazarTabla(t) {
    tablas[t.id] = { q: '', pagina: 1, visibles: [] };
    $('bus_' + t.id).addEventListener('input', function (e) { tablas[t.id].q = e.target.value; tablas[t.id].pagina = 1; cuerpoTabla(t); });
    $('ant_' + t.id).addEventListener('click', function () { tablas[t.id].pagina--; cuerpoTabla(t); });
    $('sig_' + t.id).addEventListener('click', function () { tablas[t.id].pagina++; cuerpoTabla(t); });
    cuerpoTabla(t);
  }
  function dibujar(datos) {
    destruirGraficos();
    tablas = {};
    var html = tarjetas(datos.kpis);
    if (datos.graficos && datos.graficos.length) { html += '<div class="row g-3 mb-3">' + datos.graficos.map(contenedorGrafico).join('') + '</div>'; }
    (datos.tablas || []).forEach(function (t) { html += contenedorTabla(t); });
    $('panel').innerHTML = html;
    (datos.graficos || []).forEach(dibujarGrafico);
    (datos.tablas || []).forEach(enlazarTabla);
  }

  // ───────────────────────── carga ─────────────────────────
  function cargar() {
    if (!validarFiltros()) { return; }
    var mio = ++pedido;
    destruirGraficos();
    $('panel').innerHTML = '<div class="text-muted py-4 text-center"><span class="spinner-border spinner-border-sm me-2"></span>Cargando…</div>';
    fetch('/api/informes/' + pestana + '?' + parametros(), { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (mio !== pedido) { return; }
        if (!res.ok || !res.j.success) { throw new Error(res.j.error || 'No se pudo cargar el informe.'); }
        dibujar(res.j.data);
      })
      .catch(function (e) {
        if (mio !== pedido) { return; }
        $('panel').innerHTML = '<div class="alert alert-danger">' + escapar(e.message) + '</div>';
      });
  }
  function exportar(formato) {
    if (!validarFiltros() || SIN_EXPORTACION[pestana]) { return; }
    window.open('/api/informes/' + pestana + '/exportar?formato=' + formato + '&' + parametros(), '_blank');
  }

  function cambiarPestana(nueva) {
    pestana = nueva;
    Array.prototype.forEach.call(document.querySelectorAll('#pestanas .nav-link'), function (a) {
      a.classList.toggle('active', a.getAttribute('data-pestana') === nueva);
    });
    ajustarControles();
    cargar();
  }

  function init() {
    fechasPorDefecto();
    fetch('/api/informes/medicos', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (j) {
      if (j && j.success) {
        $('fMedico').insertAdjacentHTML('beforeend', j.data.map(function (m) { return '<option value="' + escapar(m.id_medico) + '">' + escapar(m.nombre) + '</option>'; }).join(''));
      }
    }).catch(function () { /* el filtro queda solo con "Todos" */ });
    Array.prototype.forEach.call(document.querySelectorAll('#pestanas .nav-link'), function (a) {
      a.addEventListener('click', function (e) { e.preventDefault(); cambiarPestana(a.getAttribute('data-pestana')); });
    });
    $('btnAplicar').addEventListener('click', cargar);
    $('btnPdf').addEventListener('click', function () { exportar('pdf'); });
    $('btnExcel').addEventListener('click', function () { exportar('xlsx'); });
    cambiarPestana('resumen');
  }
  init();
}());
