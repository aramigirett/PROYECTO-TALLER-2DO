/*
 * Validadores de formularios del módulo Facturación (descripción, dirección,
 * teléfono, correo). Espejo de app/rutas/modulo_facturacion/utils.py: el servidor
 * valida SIEMPRE; esto solo avisa antes de enviar. Si cambia una regla, cambiar
 * los dos archivos.
 */
(function (global) {
  'use strict';

  var MAX_DESCRIPCION = 60, MAX_DIRECCION = 150, MAX_CORREO = 100, MAX_UBICACION = 100, MAX_NOMBRE = 80, MAX_OBSERVACION = 200;
  var MAX_PRECIO = 999999999999, MAX_CANTIDAD = 2147483647;

  var RE_DESCRIPCION = /^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .\-\/]*$/;
  var RE_DESCRIPCION_AMPLIADA = /^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .\-\/,%()+&]*$/;
  var RE_NOMBRE = /^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .,\-&'\/()]*$/;
  var RE_CEDULA = /^\d{5,10}$/;
  var RE_RUC = /^(\d{5,10})-(\d)$/;
  var RE_CONTROL = /[\x00-\x1f\x7f]/;
  var RE_CELULAR = /^09\d{8}$/;
  var RE_LINEA_BAJA = /^0[2-8]\d{7,8}$/;
  var RE_TEL_ESCRITURA = /^[0-9 \-]+$/;
  var MSJ_TEL_INVALIDO = 'Ingrese un celular (09XX XXX XXX) o una línea baja con código de área (021 XXX XXXX).';
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

  /* Teléfono nacional. Espejo de app/Services/telefono.py: se guarda solo con dígitos y el 0 inicial; celular 09XX XXX XXX o línea baja
     con código de área (021 XXX XXXX), escrito con o sin espacios. */
  function normalizarTelefono(v) {
    if (typeof v !== 'string') return null;
    var t = v.replace(/^\s+|\s+$/g, '');
    if (!t || !RE_TEL_ESCRITURA.test(t)) return null;
    t = t.replace(/[ \-]/g, '');
    return (RE_CELULAR.test(t) || RE_LINEA_BAJA.test(t)) ? t : null;
  }

  function telefono(v) {
    if (typeof v !== 'string' || !v.replace(/^\s+|\s+$/g, '')) return 'El campo teléfono es obligatorio y no puede estar vacío.';
    return normalizarTelefono(v) ? '' : MSJ_TEL_INVALIDO;
  }

  /* Para mostrar: celular '0984 818 035', línea baja '021 339 8423'. Un valor que no cumple el formato se devuelve tal cual. */
  function formatearTelefono(v) {
    if (v === null || v === undefined) return '';
    var t = String(v).replace(/^\s+|\s+$/g, '');
    if (RE_CELULAR.test(t)) return t.substring(0, 4) + ' ' + t.substring(4, 7) + ' ' + t.substring(7);
    if (RE_LINEA_BAJA.test(t)) { var r = t.substring(3); return t.substring(0, 3) + ' ' + r.substring(0, 3) + ' ' + r.substring(3); }
    return t;
  }

  /* Número para WhatsApp: celular 0984818035 -> 595984818035; una línea baja no sirve (null). */
  function aWhatsapp(v) {
    var t = normalizarTelefono(v);
    return t && RE_CELULAR.test(t) ? '595' + t.substring(1) : null;
  }

  function correo(v) {
    var t = limpiar(v).toLowerCase();
    if (!t) return 'El campo correo es obligatorio y no puede estar vacío.';
    if (t.length > MAX_CORREO) return 'El correo no puede superar los ' + MAX_CORREO + ' caracteres.';
    if (!RE_CORREO.test(t)) return 'El correo no tiene un formato válido.';
    return '';
  }

  /* ---- Montos y cantidades: UNA sola función para mostrar y otra para limpiar (espejo de app/Services/formato.py) ----
     Guaraníes sin decimales, punto como separador de miles: 100000 -> "100.000". Las cantidades (stock, unidades) usan lo mismo. */
  function agruparMiles(digitos) { return String(digitos).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }

  /* Para MOSTRAR un valor numérico (o un texto numérico del servidor): 100000 -> "100.000"; null / '' -> ''. Un texto que ya viene agrupado
     ("100.000") se devuelve igual, para no leerlo como el decimal 100. */
  function formatearMonto(n) {
    if (n === null || n === undefined || (typeof n === 'string' && !n.replace(/^\s+|\s+$/g, ''))) return '';
    if (typeof n === 'string' && /^-?\d{1,3}(\.\d{3})+$/.test(n.replace(/^\s+|\s+$/g, ''))) return n.replace(/^\s+|\s+$/g, '');
    var x = Number(n);
    if (isNaN(x)) return String(n);
    x = Math.round(x);
    return (x < 0 ? '-' : '') + agruparMiles(Math.abs(x));
  }

  /* Para ENVIAR al servidor: deja solo los dígitos ("100.000" -> "100000"), sin ceros a la izquierda ("007" -> "7", "000" -> "0"); vacío -> ''. */
  function limpiarMonto(v) {
    var d = String(v === null || v === undefined ? '' : v).replace(/\D/g, '');
    if (!d) return '';
    d = d.replace(/^0+/, '');
    return d === '' ? '0' : d;
  }

  /* Valor de un campo para validar o enviar: los de monto / cantidad (data-monto, data-cantidad) sin puntos; los demás, tal cual. */
  function valorCampo(el) {
    if (!el) return '';
    return (el.hasAttribute && (el.hasAttribute('data-monto') || el.hasAttribute('data-cantidad'))) ? limpiarMonto(el.value) : el.value;
  }

  function formatoNumero(n) { return agruparMiles(n); }

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
  function formatoGs(n) { return 'Gs. ' + formatearMonto(n); }

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

  /* Fecha de nacimiento AAAA-MM-DD: obligatoria, real, no futura y desde 1900. Espejo de validar_fecha_nacimiento. */
  function fechaNacimiento(v) {
    var t = typeof v === 'string' ? v.replace(/^\s+|\s+$/g, '') : '';
    if (!t) return 'El campo fecha de nacimiento es obligatorio y no puede estar vacío.';
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(t);
    var y = m ? Number(m[1]) : 0, mo = m ? Number(m[2]) : 0, d = m ? Number(m[3]) : 0;
    var f = new Date(y, mo - 1, d);
    if (!m || f.getFullYear() !== y || f.getMonth() !== mo - 1 || f.getDate() !== d) return 'El campo fecha de nacimiento no es una fecha válida.';
    var hoy = new Date(); hoy = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
    if (f > hoy) return 'La fecha de nacimiento no puede ser futura.';
    if (y < 1900) return 'La fecha de nacimiento no es válida.';
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
    descripcion: descripcion, presentacion: presentacion, texto: texto, direccion: direccion, ubicacion: ubicacion, telefono: telefono, formatearMonto: formatearMonto, limpiarMonto: limpiarMonto, valorCampo: valorCampo, normalizarTelefono: normalizarTelefono, formatearTelefono: formatearTelefono, aWhatsapp: aWhatsapp, correo: correo,
    ciRuc: ciRuc, calcularDvRuc: calcularDvRuc, nombre: nombre,
    telefonoOpcional: telefonoOpcional, correoOpcional: correoOpcional,
    precio: precio, monto: monto, iva: iva, cantidad: cantidad, cantidadPositiva: cantidadPositiva,
    observacion: observacion, montoPositivo: montoPositivo, codigo: codigo, ultimosDigitos: ultimosDigitos, numeroCuenta: numeroCuenta, formatoGs: formatoGs,
    fechaNacimiento: fechaNacimiento, dia: dia, hora: hora, horario: horario, cupos: cupos,
    marcarCampo: marcarCampo, limpiarCampo: limpiarCampo
  };

  /* Los campos de teléfono (data-telefono) se dejan formateados al salir de ellos, si el número es válido ("0984818035" -> "0984 818 035"). */
  /* Campos de monto / cantidad (data-monto, data-cantidad): solo dígitos, formateados EN VIVO con puntos de miles mientras se escribe, sin que el cursor
     salte (se conserva cuántos dígitos quedan a su izquierda). Sin letras, comas ni decimales; máximo de dígitos en data-max-digits (12 en montos,
     10 en cantidades). No usar maxlength en estos campos: contaría los puntos. Se engancha en la fase de captura para que los demás manejadores
     del campo ya vean el valor formateado; los dinámicos (creados después) funcionan igual. */
  function formatearEnVivo(el) {
    var max = parseInt(el.getAttribute('data-max-digits') || (el.hasAttribute('data-cantidad') ? '10' : '12'), 10);
    var antes = el.value;
    var pos = typeof el.selectionStart === 'number' ? el.selectionStart : antes.length;
    var izquierda = (antes.slice(0, pos).match(/\d/g) || []).length;
    var crudo = antes.replace(/\D/g, '');
    var limpio = crudo.replace(/^0+(?=\d)/, '');
    izquierda = Math.max(0, izquierda - (crudo.length - limpio.length));
    if (limpio.length > max) limpio = limpio.slice(0, max);
    izquierda = Math.min(izquierda, limpio.length);
    var formato = agruparMiles(limpio);
    if (formato === antes) return;
    el.value = formato;
    var p = 0, vistos = 0;
    while (p < formato.length && vistos < izquierda) { if (/\d/.test(formato.charAt(p))) vistos++; p++; }
    if (typeof el.setSelectionRange === 'function' && document.activeElement === el) { try { el.setSelectionRange(p, p); } catch (e) { /* tipo sin selección */ } }
  }
  if (typeof document !== 'undefined' && document.addEventListener) document.addEventListener('input', function (e) {
    var el = e.target;
    if (el && el.hasAttribute && el.tagName === 'INPUT' && (el.hasAttribute('data-monto') || el.hasAttribute('data-cantidad')) && !e.isComposing) formatearEnVivo(el);
  }, true);

  if (typeof document !== 'undefined' && document.addEventListener) document.addEventListener('blur', function (e) {
    var el = e.target;
    if (!el || !el.hasAttribute || !el.hasAttribute('data-telefono')) return;
    var t = normalizarTelefono(el.value);
    if (t) el.value = formatearTelefono(t);
  }, true);
})(window);
