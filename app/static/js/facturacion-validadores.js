/*
 * Validadores de formularios del módulo Facturación (descripción, dirección,
 * teléfono, correo). Espejo de app/rutas/modulo_facturacion/utils.py: el servidor
 * valida SIEMPRE; esto solo avisa antes de enviar. Si cambia una regla, cambiar
 * los dos archivos.
 */
(function (global) {
  'use strict';

  var MAX_DESCRIPCION = 60, MAX_DIRECCION = 150, MAX_CORREO = 100, MAX_UBICACION = 100, MAX_NOMBRE = 80, MAX_OBSERVACION = 200;
  var TEL_MIN_LARGO = 6, TEL_MAX_LARGO = 20, TEL_MIN_DIGITOS = 6;
  var MAX_PRECIO = 999999999999, MAX_CANTIDAD = 2147483647;

  var RE_DESCRIPCION = /^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .\-\/]*$/;
  var RE_DESCRIPCION_AMPLIADA = /^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .\-\/,%()+&]*$/;
  var RE_NOMBRE = /^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .,\-&'\/()]*$/;
  var RE_CEDULA = /^\d{5,10}$/;
  var RE_RUC = /^(\d{5,10})-(\d)$/;
  var RE_CONTROL = /[\x00-\x1f\x7f]/;
  var RE_TELEFONO = /^\+?[0-9][0-9 \-]*$/;
  var RE_CORREO = /^[a-z0-9._%+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)*\.[a-z]{2,}$/;

  function limpiar(v) {
    return typeof v === 'string' ? v.replace(/\s+/g, ' ').trim() : '';
  }

  /* Cada validador devuelve '' si es válido o el mensaje de error. */
  /* opciones: { max: 60, ampliada: false } (ampliada acepta además , % ( ) + &) */
  function descripcion(v, opciones) {
    var max = (opciones && opciones.max) || MAX_DESCRIPCION;
    var ampliada = !!(opciones && opciones.ampliada);
    var t = limpiar(v).toUpperCase();
    if (!t) return 'El campo descripción es obligatorio y no puede estar vacío.';
    if (t.length > max) return 'La descripción no puede superar los ' + max + ' caracteres.';
    if (!(ampliada ? RE_DESCRIPCION_AMPLIADA : RE_DESCRIPCION).test(t))
      return ampliada
        ? 'La descripción solo puede contener letras, números, espacios y los símbolos . - / , % ( ) + &'
        : 'La descripción solo puede contener letras, números, espacios y los símbolos . - /';
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
  function ubicacion(v) { return texto(v, 'ubicación', MAX_UBICACION); }

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

  function formatoNumero(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  function esVacio(v) { return v === null || v === undefined || String(v).trim() === ''; }

  function precio(v) {
    if (esVacio(v)) return 'El campo precio es obligatorio y no puede estar vacío.';
    var t = String(v).trim();
    if (!/^-?\d+$/.test(t)) return 'El precio debe ser un número entero (guaraníes, sin decimales).';
    var n = parseInt(t, 10);
    if (n <= 0) return 'El precio debe ser mayor a 0.';
    if (n > MAX_PRECIO) return 'El precio no puede superar ' + formatoNumero(MAX_PRECIO) + '.';
    return '';
  }

  /* Monto en guaraníes: entero >= 0 (puede ser 0). Espejo de validar_monto. */
  function monto(v) {
    if (esVacio(v)) return 'El campo monto es obligatorio y no puede estar vacío.';
    var t = String(v).trim();
    if (!/^-?\d+$/.test(t)) return 'El monto debe ser un número entero (guaraníes, sin decimales).';
    var n = parseInt(t, 10);
    if (n < 0) return 'El monto no puede ser negativo.';
    if (n > MAX_PRECIO) return 'El monto no puede superar ' + formatoNumero(MAX_PRECIO) + '.';
    return '';
  }

  function iva(v) {
    var t = String(v === null || v === undefined ? '' : v).trim();
    return (t === '0' || t === '5' || t === '10') ? '' : 'El IVA debe ser Exenta (0), 5% o 10%.';
  }

  function cantidad(v) {
    if (esVacio(v)) return 'El campo cantidad es obligatorio (use 0 si no hay stock).';
    var t = String(v).trim();
    if (!/^-?\d+$/.test(t)) return 'La cantidad debe ser un número entero.';
    var n = parseInt(t, 10);
    if (n < 0) return 'La cantidad no puede ser negativa.';
    if (n > MAX_CANTIDAD) return 'La cantidad no puede superar ' + formatoNumero(MAX_CANTIDAD) + '.';
    return '';
  }

  /* 15000 -> "Gs. 15.000" */
  function formatoGs(n) { return 'Gs. ' + formatoNumero(Math.round(Number(n))); }

  /* Dígito verificador del RUC paraguayo (SET): módulo 11, base máxima 11 (espejo de calcular_dv_ruc). */
  function calcularDvRuc(base, baseMax) {
    baseMax = baseMax || 11;
    var k = 2, total = 0, s = String(base);
    for (var i = s.length - 1; i >= 0; i--) {
      if (k > baseMax) k = 2;
      total += parseInt(s.charAt(i), 10) * k;
      k++;
    }
    var resto = total % 11;
    return resto > 1 ? 11 - resto : 0;
  }

  /* Cédula (5 a 10 dígitos, sin verificador) o RUC con verificador (ej. 80012345-0). */
  function ciRuc(v) {
    var t = limpiar(v);
    if (!t) return 'El campo CI/RUC es obligatorio y no puede estar vacío.';
    if (/^\d+$/.test(t)) return RE_CEDULA.test(t) ? '' : 'La cédula debe tener entre 5 y 10 dígitos.';
    var m = RE_RUC.exec(t);
    if (!m) return 'La CI/RUC no es válida: use una cédula (5 a 10 dígitos) o un RUC con verificador (ej. 80012345-0).';
    if (parseInt(m[2], 10) !== calcularDvRuc(m[1])) return 'El dígito verificador del RUC no es válido.';
    return '';
  }

  /* Nombre / razón social (obligatorio) o apellido (opcional, requerido=false). */
  function nombre(v, etiqueta, requerido) {
    var t = limpiar(v).toUpperCase();
    if (!t) return requerido === false ? '' : 'El campo ' + etiqueta + ' es obligatorio y no puede estar vacío.';
    if (t.length > MAX_NOMBRE) return 'El campo ' + etiqueta + ' no puede superar los ' + MAX_NOMBRE + ' caracteres.';
    if (!RE_NOMBRE.test(t)) return "El campo " + etiqueta + " solo puede contener letras, números, espacios y los símbolos . , - & ' / ( )";
    return '';
  }

  function telefonoOpcional(v) { return limpiar(v) ? telefono(v) : ''; }
  function correoOpcional(v) { return limpiar(v) ? correo(v) : ''; }

  /* Cantidad de un renglón de pedido: entero > 0, un único mensaje. Espejo de validar_cantidad_positiva. */
  function cantidadPositiva(v) {
    var t = esVacio(v) ? '' : String(v).trim();
    if (!/^-?\d+$/.test(t) || parseInt(t, 10) <= 0) return 'La cantidad debe ser un número entero mayor a 0.';
    if (parseInt(t, 10) > MAX_CANTIDAD) return 'La cantidad no puede superar ' + formatoNumero(MAX_CANTIDAD) + '.';
    return '';
  }

  /* Monto de una forma de cobro: entero > 0, un único mensaje. Espejo de validar_monto_positivo. */
  function montoPositivo(v) {
    var t = esVacio(v) ? '' : String(v).trim();
    if (!/^-?\d+$/.test(t) || parseInt(t, 10) <= 0) return 'El monto debe ser un número entero mayor a 0.';
    if (parseInt(t, 10) > MAX_PRECIO) return 'El monto no puede superar ' + formatoNumero(MAX_PRECIO) + '.';
    return '';
  }

  /* Código o número tipeado (referencia, autorización, N.º de cheque). Espejo de validar_codigo. */
  var RE_CODIGO = /^[A-Z0-9][A-Z0-9 ._\/\-]*$/;
  function codigo(v, nombre, max, obligatorio) {
    var t = limpiar(v).toUpperCase();
    if (!t) return obligatorio === false ? '' : 'El campo ' + nombre + ' es obligatorio y no puede estar vacío.';
    if (t.length > max) return 'El campo ' + nombre + ' no puede superar los ' + max + ' caracteres.';
    if (!RE_CODIGO.test(t)) return 'El campo ' + nombre + ' solo puede contener letras, números, espacios y los símbolos . _ / -';
    return '';
  }

  /* Últimos 4 dígitos de la tarjeta. Espejo de validar_ultimos_digitos. */
  function ultimosDigitos(v) {
    return /^\d{4}$/.test(String(v === null || v === undefined ? '' : v).trim()) ? '' : 'Los últimos dígitos de la tarjeta deben ser 4 números.';
  }

  /* Observación opcional de hasta 200 caracteres. Espejo de validar_observacion. */
  function observacion(v) {
    var t = limpiar(v);
    if (!t) return '';
    if (t.length > MAX_OBSERVACION) return 'La observación no puede superar los ' + MAX_OBSERVACION + ' caracteres.';
    if (RE_CONTROL.test(t)) return 'La observación contiene caracteres no permitidos.';
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
    descripcion: descripcion, direccion: direccion, ubicacion: ubicacion, telefono: telefono, correo: correo,
    ciRuc: ciRuc, calcularDvRuc: calcularDvRuc, nombre: nombre,
    telefonoOpcional: telefonoOpcional, correoOpcional: correoOpcional,
    precio: precio, monto: monto, iva: iva, cantidad: cantidad, cantidadPositiva: cantidadPositiva,
    observacion: observacion, montoPositivo: montoPositivo, codigo: codigo, ultimosDigitos: ultimosDigitos, formatoGs: formatoGs,
    marcarCampo: marcarCampo, limpiarCampo: limpiarCampo
  };
})(window);
