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
  /* opciones: { max: 60, ampliada: false, etiqueta: 'descripción', articulo: 'La' }
     (ampliada acepta además , % ( ) + &; etiqueta/articulo permiten usarla con otro campo, ej. 'nombre comercial' / 'El') */
  function descripcion(v, opciones) {
    var max = (opciones && opciones.max) || MAX_DESCRIPCION;
    var ampliada = !!(opciones && opciones.ampliada);
    var etiqueta = (opciones && opciones.etiqueta) || 'descripción';
    var articulo = (opciones && opciones.articulo) || 'La';
    var t = limpiar(v).toUpperCase();
    if (!t) return 'El campo ' + etiqueta + ' es obligatorio y no puede estar vacío.';
    if (t.length > max) return articulo + ' ' + etiqueta + ' no puede superar los ' + max + ' caracteres.';
    if (!(ampliada ? RE_DESCRIPCION_AMPLIADA : RE_DESCRIPCION).test(t))
      return ampliada
        ? articulo + ' ' + etiqueta + ' solo puede contener letras, números, espacios y los símbolos . - / , % ( ) + &'
        : articulo + ' ' + etiqueta + ' solo puede contener letras, números, espacios y los símbolos . - /';
    return '';
  }

  /* Presentación opcional (Insumos, Medicamentos). Espejo de validar_presentacion. */
  function presentacion(v) {
    var t = limpiar(v).toUpperCase();
    if (!t) return '';
    if (t.length > 100) return 'La presentación no puede superar los 100 caracteres.';
    if (!RE_DESCRIPCION_AMPLIADA.test(t)) return 'La presentación solo puede contener letras, números, espacios y los símbolos . - / , % ( ) + &';
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

  /* Número de cuenta bancaria: dígitos y guiones, de 5 a 30 caracteres. Espejo de validar_numero_cuenta. */
  function numeroCuenta(v) {
    var t = typeof v === 'number' ? String(v) : limpiar(v);
    return /^\d[\d\-]{4,29}$/.test(t) ? '' : 'El número de cuenta debe tener entre 5 y 30 caracteres: solo números y guiones.';
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

  /* ---- Agendamiento. Espejo de app/rutas/modulo_agendamiento/utils.py ---- */
  var DIAS_VALIDOS = ['LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO'];
  var MAX_CUPOS = 1000;
  var RE_TELEFONO_PY = /^595\d{8,9}$/;

  function sinTildes(t) {
    return t.replace(/[ÁÀ]/g, 'A').replace(/[ÉÈ]/g, 'E').replace(/[ÍÌ]/g, 'I').replace(/[ÓÒ]/g, 'O').replace(/[ÚÙÜ]/g, 'U');
  }

  /* Día de la semana: uno de los 7 nombres (se acepta con tilde). Espejo de validar_dia. */
  function dia(v) {
    var t = sinTildes(limpiar(v).toUpperCase());
    if (!t) return 'El campo día es obligatorio y no puede estar vacío.';
    for (var i = 0; i < DIAS_VALIDOS.length; i++) { if (DIAS_VALIDOS[i] === t) return ''; }
    return 'El día debe ser uno de los días de la semana: Lunes, Martes, Miércoles, Jueves, Viernes, Sábado o Domingo.';
  }

  /* Teléfono paraguayo del consultorio: 0981234567 -> 595981234567. Espejo de normalizar_telefono_py / validar_telefono_py. */
  function normalizarTelefonoPy(v) {
    if (typeof v !== 'string') return null;
    var t = v.replace(/^\s+|\s+$/g, '').replace(/ /g, '').replace(/-/g, '');
    if (!t) return null;
    if (t.charAt(0) === '+') t = t.substring(1);
    if (t.charAt(0) === '0') return '595' + t.substring(1);
    return t.indexOf('595') === 0 ? t : '595' + t;
  }

  function telefonoPy(v) {
    if (!limpiar(v)) return 'El campo teléfono es obligatorio y no puede estar vacío.';
    var t = normalizarTelefonoPy(v);
    if (!t || !RE_TELEFONO_PY.test(t)) return 'El número de teléfono no es válido. Debe ser paraguayo (ej.: 0981234567).';
    return '';
  }

  /* Hora HH:MM o HH:MM:SS. Espejo de validar_hora. */
  function hora(v, nombre) {
    var t = typeof v === 'string' ? v.replace(/^\s+|\s+$/g, '') : '';
    if (!t) return 'El campo ' + nombre + ' es obligatorio y no puede estar vacío.';
    var m = /^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$/.exec(t);
    if (!m || Number(m[1]) > 23 || Number(m[2]) > 59 || (m[3] !== undefined && Number(m[3]) > 59))
      return 'El campo ' + nombre + ' no es una hora válida (use HH:MM).';
    return '';
  }

  /* La hora de fin debe ser posterior a la de inicio (HH:MM con 2 dígitos). Espejo de validar_horario. */
  function horario(inicio, fin) {
    return fin <= inicio ? 'La hora de fin debe ser posterior a la hora de inicio.' : '';
  }

  /* Cupos: entero de 1 a 1000. Espejo de validar_cupos. */
  function cupos(v) {
    var t = typeof v === 'number' ? String(v) : (typeof v === 'string' ? v.replace(/^\s+|\s+$/g, '') : '');
    if (!/^\d+$/.test(t)) return 'Los cupos deben ser un número entero.';
    var n = Number(t);
    if (n < 1 || n > MAX_CUPOS) return 'Los cupos deben estar entre 1 y ' + MAX_CUPOS + '.';
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
    descripcion: descripcion, presentacion: presentacion, texto: texto, direccion: direccion, ubicacion: ubicacion, telefono: telefono, correo: correo,
    ciRuc: ciRuc, calcularDvRuc: calcularDvRuc, nombre: nombre,
    telefonoOpcional: telefonoOpcional, correoOpcional: correoOpcional,
    precio: precio, monto: monto, iva: iva, cantidad: cantidad, cantidadPositiva: cantidadPositiva,
    observacion: observacion, montoPositivo: montoPositivo, codigo: codigo, ultimosDigitos: ultimosDigitos, numeroCuenta: numeroCuenta, formatoGs: formatoGs,
    dia: dia, telefonoPy: telefonoPy, hora: hora, horario: horario, cupos: cupos,
    marcarCampo: marcarCampo, limpiarCampo: limpiarCampo
  };
})(window);
