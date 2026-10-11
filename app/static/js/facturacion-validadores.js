/*
 * Validadores de formularios del módulo Facturación (descripción, dirección,
 * teléfono, correo). Espejo de app/rutas/modulo_facturacion/utils.py: el servidor
 * valida SIEMPRE; esto solo avisa antes de enviar. Si cambia una regla, cambiar
 * los dos archivos.
 */
(function (global) {
  'use strict';

  var MAX_DESCRIPCION = 60, MAX_DIRECCION = 150, MAX_CORREO = 100;
  var TEL_MIN_LARGO = 6, TEL_MAX_LARGO = 20, TEL_MIN_DIGITOS = 6;

  var RE_DESCRIPCION = /^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .\-\/]*$/;
  var RE_CONTROL = /[\x00-\x1f\x7f]/;
  var RE_TELEFONO = /^\+?[0-9][0-9 \-]*$/;
  var RE_CORREO = /^[a-z0-9._%+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)*\.[a-z]{2,}$/;

  function limpiar(v) {
    return typeof v === 'string' ? v.replace(/\s+/g, ' ').trim() : '';
  }

  /* Cada validador devuelve '' si es válido o el mensaje de error. */
  function descripcion(v) {
    var t = limpiar(v).toUpperCase();
    if (!t) return 'El campo descripción es obligatorio y no puede estar vacío.';
    if (t.length > MAX_DESCRIPCION) return 'La descripción no puede superar los ' + MAX_DESCRIPCION + ' caracteres.';
    if (!RE_DESCRIPCION.test(t)) return 'La descripción solo puede contener letras, números, espacios y los símbolos . - /';
    return '';
  }

  function texto(v, nombre, max) {
    var t = limpiar(v);
    if (!t) return 'El campo ' + nombre + ' es obligatorio y no puede estar vacío.';
    if (t.length > max) return 'El campo ' + nombre + ' no puede superar los ' + max + ' caracteres.';
    if (RE_CONTROL.test(t)) return 'El campo ' + nombre + ' contiene caracteres no permitidos.';
    return '';
  }

  function direccion(v) { return texto(v, 'dirección', MAX_DIRECCION); }

  function telefono(v) {
    var t = limpiar(v);
    if (!t) return 'El campo teléfono es obligatorio y no puede estar vacío.';
    if (!RE_TELEFONO.test(t)) return 'El teléfono solo puede contener dígitos, espacios, guiones y un + inicial.';
    if (t.length < TEL_MIN_LARGO || t.length > TEL_MAX_LARGO)
      return 'El teléfono debe tener entre ' + TEL_MIN_LARGO + ' y ' + TEL_MAX_LARGO + ' caracteres.';
    if ((t.match(/[0-9]/g) || []).length < TEL_MIN_DIGITOS)
      return 'El teléfono debe tener al menos ' + TEL_MIN_DIGITOS + ' dígitos.';
    return '';
  }

  function correo(v) {
    var t = limpiar(v).toLowerCase();
    if (!t) return 'El campo correo es obligatorio y no puede estar vacío.';
    if (t.length > MAX_CORREO) return 'El correo no puede superar los ' + MAX_CORREO + ' caracteres.';
    if (!RE_CORREO.test(t)) return 'El correo no tiene un formato válido.';
    return '';
  }

  /* ---- Ayudas de interfaz (Tabler/Bootstrap 5): .invalid-feedback hermano del input ---- */
  function marcarCampo(input, mensaje) {
    if (!input) return;
    input.classList.add('is-invalid');
    var fb = input.parentElement.querySelector('.invalid-feedback');
    if (fb) fb.textContent = mensaje;
  }

  function limpiarCampo(input) {
    if (!input) return;
    input.classList.remove('is-invalid');
    var fb = input.parentElement.querySelector('.invalid-feedback');
    if (fb) fb.textContent = '';
  }

  global.FacturacionValidadores = {
    descripcion: descripcion, direccion: direccion, telefono: telefono, correo: correo,
    marcarCampo: marcarCampo, limpiarCampo: limpiarCampo
  };
})(window);
