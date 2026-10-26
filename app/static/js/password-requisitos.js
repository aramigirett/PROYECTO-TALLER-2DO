/* Requisitos de contraseña EN VIVO, reutilizable: una lista bajo el campo que se marca mientras se escribe, cada requisito con ✗ rojo -> ✓ verde.
   Espejo de app/rutas/modulo_seguridad/password_policy.py (el servidor valida lo mismo): si cambia una regla, cambian las dos.
     - Mínimo 8 caracteres   - Una letra mayúscula   - Un número   - Un símbolo
   El botón de guardar queda deshabilitado hasta cumplirlos todos. Con `opcionalVacio()` verdadero (edición: dejar la contraseña vacía conserva la actual) un campo
   vacío también habilita el botón; si se escribe algo, tiene que cumplir todo.
   Uso:
     const req = PasswordRequisitos.crear({ input, lista, boton, opcionalVacio: () => !!inpId.value });
     req.cumple();      // true si el valor actual es válido (según opcionalVacio)
     req.actualizar();  // repinta la lista y el botón (llamarlo tras cambiar el valor por código, o al terminar de enviar)
   Marcado: <ul id="reqPassword" class="list-unstyled small mt-2 mb-0"></ul>  (la lista se arma sola) */
(function (global) {
  'use strict';

  var REQUISITOS = [
    { clave: 'largo', texto: 'Mínimo 8 caracteres', cumple: function (p) { return p.length >= 8; } },
    { clave: 'mayuscula', texto: 'Una letra mayúscula', cumple: function (p) { return /[A-ZÁÉÍÓÚÑ]/.test(p); } },
    { clave: 'numero', texto: 'Un número', cumple: function (p) { return /\d/.test(p); } },
    { clave: 'simbolo', texto: 'Un símbolo (! @ # $ % & *)', cumple: function (p) { return /[^\w\s]|_/.test(p); } }
  ];

  function todoCumple(p) { return REQUISITOS.every(function (r) { return r.cumple(p); }); }
  function faltantes(p) { return REQUISITOS.filter(function (r) { return !r.cumple(p); }).map(function (r) { return r.texto; }); }

  function crear(o) {
    var input = o.input, lista = o.lista, boton = o.boton;
    lista.innerHTML = REQUISITOS.map(function (r) {
      return '<li data-req="' + r.clave + '" class="text-danger"><span class="me-1" data-marca aria-hidden="true">✗</span>' + r.texto + '</li>';
    }).join('');
    lista.setAttribute('aria-live', 'polite');

    function vacioPermitido() { return typeof o.opcionalVacio === 'function' && o.opcionalVacio() && input.value === ''; }
    function cumple() { return vacioPermitido() || todoCumple(input.value); }

    function actualizar() {
      var p = input.value;
      REQUISITOS.forEach(function (r) {
        var li = lista.querySelector('[data-req="' + r.clave + '"]');
        var ok = r.cumple(p);
        li.className = ok ? 'text-success' : 'text-danger';
        li.querySelector('[data-marca]').textContent = ok ? '✓' : '✗';
      });
      if (boton) boton.disabled = !cumple();
    }

    input.addEventListener('input', actualizar);
    actualizar();
    return { cumple: cumple, actualizar: actualizar, faltantes: function () { return faltantes(input.value); } };
  }

  global.PasswordRequisitos = { crear: crear, requisitos: REQUISITOS, cumple: todoCumple };
})(window);
