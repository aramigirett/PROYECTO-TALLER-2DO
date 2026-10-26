/* Buscador de pacientes reutilizable: UN solo campo de texto (sin lista desplegable "Seleccione…").
   - Al escribir la cédula o el nombre muestra las sugerencias EN VIVO en un dropdown debajo del campo (posición absoluta, mismo ancho que el campo, fondo blanco,
     borde y sombra, por encima del modal, con scroll). Cada sugerencia: nombre en negrita y "CI 1111111" en gris; hover, flechas arriba/abajo y Enter.
   - Si lo escrito es una cédula que coincide EXACTO con un paciente (y ninguna otra cédula empieza igual), lo selecciona solo y muestra su nombre completo.
   - Si no hay coincidencias avisa "Paciente no encontrado".
   - El texto de ayuda se oculta mientras la lista está abierta y cuando ya hay un paciente seleccionado (entonces el campo muestra el nombre y una "×" para cambiarlo).
   - El id del paciente elegido queda en un campo oculto (`oculto`), igual que antes quedaba en el <select>: el resto de la pantalla lee `oculto.value` y escucha su
     evento 'change'. El borde rojo de error (clase is-invalid puesta sobre el oculto) se refleja en el campo visible.
   Uso:
     const buscador = PacienteBuscador.crear({ input, oculto, lista, hint, pacientes: [] });   // pacientes: [{ id_paciente, nombre, apellido, cedula_entidad }]
     buscador.setPacientes(arr);  buscador.limpiar();  buscador.id();  buscador.seleccionado();
   Marcado esperado (el dropdown va DENTRO del contenedor relativo del campo, el oculto + .invalid-feedback después, y la ayuda al final; el estilo del dropdown
   lo pone este archivo, así todas las pantallas se ven igual):
     <div class="mb-3">
       <label class="form-label required" for="txtPaciente">Paciente</label>
       <div class="position-relative">
         <input type="text" class="form-control" id="txtPaciente" autocomplete="off" placeholder="Escriba la cédula o el nombre…">
         <div id="sugPaciente"></div>
       </div>
       <input type="hidden" id="selPaciente"><div class="invalid-feedback"></div>
       <div class="form-hint" id="hintPaciente" data-ayuda="Escriba la cédula o el nombre del paciente."></div>
     </div> */
(function (global) {
  'use strict';

  var MAX_SUGERENCIAS = 8;
  var ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  function escapar(t) { return String(t === null || t === undefined ? '' : t).replace(/[&<>"']/g, function (c) { return ESCAPES[c]; }); }
  function sinTildes(t) { return String(t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
  function soloDigitos(t) { return String(t || '').replace(/\D/g, ''); }
  function nombreCompleto(p) { return (p.nombre + ' ' + p.apellido).replace(/\s+/g, ' ').trim(); }

  function crear(o) {
    var input = o.input, oculto = o.oculto, lista = o.lista, hint = o.hint;
    var pacientes = o.pacientes || [], elegido = null, activo = -1, sugeridos = [], error = '';

    // Dropdown de Tabler: absoluto justo debajo del campo, del mismo ancho, blanco, con borde y sombra, sobre el modal y con scroll.
    lista.className = 'list-group position-absolute start-0 end-0 bg-white border rounded shadow';
    lista.style.cssText = 'top: calc(100% + 2px); z-index: 2000; max-height: 260px; overflow-y: auto; display: none; background-color: #fff;';
    lista.setAttribute('role', 'listbox');

    // "×" para cambiar el paciente ya elegido (dentro del contenedor relativo del campo).
    var quitar = document.createElement('button');
    quitar.type = 'button';
    quitar.className = 'btn-close position-absolute top-50 end-0 translate-middle-y me-2';
    quitar.style.display = 'none';
    quitar.setAttribute('aria-label', 'Cambiar paciente');
    quitar.title = 'Cambiar paciente';
    input.parentElement.appendChild(quitar);

    function abierta() { return lista.style.display !== 'none'; }

    // Ayuda: solo con el campo vacío y la lista cerrada; el error ("Paciente no encontrado") se muestra siempre que no haya lista abierta ni selección.
    function actualizarAyuda() {
      if (!hint) return;
      var texto = '', clase = 'form-hint';
      if (!elegido && !abierta()) {
        if (error) { texto = error; clase += ' text-danger'; }
        else if (!input.value.trim()) texto = hint.getAttribute('data-ayuda') || '';
      }
      hint.textContent = texto;
      hint.className = clase;
      hint.style.display = texto ? '' : 'none';
    }
    function cerrar() { lista.style.display = 'none'; lista.innerHTML = ''; activo = -1; sugeridos = []; actualizarAyuda(); }
    function avisarCambio() {
      ['input', 'change'].forEach(function (t) { oculto.dispatchEvent(new Event(t, { bubbles: true })); });
    }

    function seleccionar(p) {
      elegido = p; error = '';
      oculto.value = String(p.id_paciente);
      input.value = nombreCompleto(p);
      input.readOnly = true;                       // elegido: para cambiarlo se usa la "×" (así no se mezcla el nombre con lo que se siga escribiendo)
      input.classList.add('pe-5');
      quitar.style.display = '';
      cerrar();
      avisarCambio();
    }

    function limpiar() {
      var habia = !!elegido || oculto.value !== '';
      elegido = null; error = ''; oculto.value = ''; input.value = ''; input.readOnly = false; input.classList.remove('pe-5'); quitar.style.display = 'none';
      cerrar();
      if (habia) avisarCambio();
    }

    function coincidencias(q) {
      var texto = sinTildes(q), digitos = soloDigitos(q), soloNumeros = /^[\d.\-\s]+$/.test(q) && digitos.length > 0;
      var r = pacientes.filter(function (p) {
        if (soloNumeros) return soloDigitos(p.cedula_entidad).indexOf(digitos) >= 0;
        return sinTildes(nombreCompleto(p) + ' ' + p.cedula_entidad).indexOf(texto) >= 0;
      });
      if (soloNumeros) r.sort(function (a, b) {          // la cédula exacta primero
        return (soloDigitos(b.cedula_entidad) === digitos ? 1 : 0) - (soloDigitos(a.cedula_entidad) === digitos ? 1 : 0);
      });
      return r;
    }

    // Una fila clara por sugerencia: nombre en negrita a la izquierda y "CI 1111111" en gris a la derecha. La activa (flechas) se resalta.
    function pintar() {
      lista.innerHTML = sugeridos.map(function (p, i) {
        return '<button type="button" role="option" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center gap-3 py-2' + (i === activo ? ' active' : '') +
               '" data-i="' + i + '"><span class="fw-bold text-truncate">' + escapar(nombreCompleto(p)) + '</span>' +
               '<span class="small text-nowrap' + (i === activo ? '' : ' text-secondary') + '">CI ' + escapar(p.cedula_entidad) + '</span></button>';
      }).join('');
      lista.style.display = sugeridos.length ? 'block' : 'none';
      var act = lista.querySelector('.active');
      if (act && act.scrollIntoView) act.scrollIntoView({ block: 'nearest' });
      actualizarAyuda();
    }

    function alEscribir() {
      if (elegido) return;                              // readOnly: no llega acá, por si acaso
      var q = input.value.trim();
      error = '';
      if (oculto.value !== '') { oculto.value = ''; avisarCambio(); }
      if (!q) { cerrar(); return; }
      var digitos = soloDigitos(q);
      if (/^[\d.\-\s]+$/.test(q) && digitos.length >= 5) {
        var exactos = pacientes.filter(function (p) { return soloDigitos(p.cedula_entidad) === digitos; });
        var otras = pacientes.filter(function (p) { var d = soloDigitos(p.cedula_entidad); return d !== digitos && d.indexOf(digitos) === 0; });
        if (exactos.length === 1 && !otras.length) { seleccionar(exactos[0]); return; }      // cédula exacta y sin ambigüedad: se elige sola
      }
      sugeridos = coincidencias(q).slice(0, MAX_SUGERENCIAS);
      activo = sugeridos.length ? 0 : -1;
      if (!sugeridos.length && q.length >= 2) error = 'Paciente no encontrado';
      pintar();
    }

    input.addEventListener('input', alEscribir);
    input.addEventListener('keydown', function (e) {
      if (!abierta() || !sugeridos.length) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); activo = (activo + 1) % sugeridos.length; pintar(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); activo = (activo - 1 + sugeridos.length) % sugeridos.length; pintar(); }
      else if (e.key === 'Enter') { e.preventDefault(); seleccionar(sugeridos[Math.max(activo, 0)]); }
      else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cerrar(); }
    });
    lista.addEventListener('mousedown', function (e) { e.preventDefault(); });          // no le saca el foco al campo antes del clic
    lista.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-i]');
      if (b) seleccionar(sugeridos[Number(b.getAttribute('data-i'))]);
    });
    quitar.addEventListener('click', function () { limpiar(); input.focus(); });
    document.addEventListener('click', function (e) { if (abierta() && !lista.contains(e.target) && e.target !== input) cerrar(); });

    // El error (is-invalid) se pone sobre el campo oculto, que no se ve: se refleja en el visible.
    if (typeof MutationObserver === 'function') {
      new MutationObserver(function () { input.classList.toggle('is-invalid', oculto.classList.contains('is-invalid')); })
        .observe(oculto, { attributes: true, attributeFilter: ['class'] });
    }

    actualizarAyuda();
    return {
      setPacientes: function (arr) { pacientes = arr || []; },
      limpiar: limpiar,
      id: function () { return oculto.value; },
      seleccionado: function () { return elegido; },
      seleccionar: seleccionar
    };
  }

  global.PacienteBuscador = { crear: crear };
})(window);
