/*
 * Validadores clínicos de Consultorio (Ficha Médica). Espejo de app/rutas/modulo_consultorio/validadores_clinicos.py: el servidor
 * valida SIEMPRE; esto solo avisa antes de enviar y muestra el IMC en vivo. Si cambia una regla o un rango, cambiar los dos archivos
 * y la restricción de la base (chk_ficha_rangos / chk_ficha_presion).
 *
 * Escrito en ES5 a propósito: se ejecuta con JScript (tests/consultorio/comparar_ficha_js_py.py) para comprobar que da lo mismo que Python.
 */
(function (global) {
  'use strict';

  var MAX_TEXTO = 2000;
  var CAMPOS_TEXTO = {
    examen_fisico_general: 'El examen físico general',
    examen_bucal: 'El examen bucal',
    observaciones_medico: 'Las observaciones del médico'
  };
  var CAMPOS_DATO = ['presion_arterial', 'temperatura', 'frecuencia_cardiaca', 'frecuencia_respiratoria', 'peso', 'talla',
                     'examen_fisico_general', 'examen_bucal', 'observaciones_medico'];

  var RE_NUMERO = /^\d+([.,]\d+)?$/;
  var RE_ENTERO = /^\d+$/;
  var RE_PRESION = /^(\d{2,3})\s*\/\s*(\d{2,3})$/;
  var RE_CONTROL = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/;

  function vacio(v) { return v === null || v === undefined || (typeof v === 'string' && v.replace(/^\s+|\s+$/g, '') === ''); }
  function recortar(v) { return String(v).replace(/^\s+|\s+$/g, ''); }

  function decimales(texto) {
    var i = texto.search(/[.,]/);
    return i < 0 ? 0 : texto.length - i - 1;
  }

  /* '' si es válido o el mensaje */
  function decimal(v, minimo, maximo, mensaje) {
    if (vacio(v)) return '';
    var t = recortar(v);
    if (!RE_NUMERO.test(t) || decimales(t) > 2) return mensaje;
    var n = parseFloat(t.replace(',', '.'));
    return (n >= minimo && n <= maximo) ? '' : mensaje;
  }

  function entero(v, minimo, maximo, mensaje) {
    if (vacio(v)) return '';
    var t = recortar(v);
    if (!RE_ENTERO.test(t)) return mensaje;
    var n = parseInt(t, 10);
    return (n >= minimo && n <= maximo) ? '' : mensaje;
  }

  function temperatura(v) { return decimal(v, 30, 45, 'La temperatura debe ser un número entre 30 y 45 (°C), con hasta 2 decimales.'); }
  function frecuenciaCardiaca(v) { return entero(v, 20, 250, 'La frecuencia cardíaca debe ser un número entero entre 20 y 250 (lpm).'); }
  function frecuenciaRespiratoria(v) { return entero(v, 5, 80, 'La frecuencia respiratoria debe ser un número entero entre 5 y 80 (rpm).'); }
  function peso(v) { return decimal(v, 1, 500, 'El peso debe ser un número entre 1 y 500 (kg), con hasta 2 decimales.'); }
  function talla(v) { return decimal(v, 30, 250, 'La talla debe ser un número entre 30 y 250 (cm), con hasta 2 decimales.'); }

  function presion(v) {
    if (vacio(v)) return '';
    var m = RE_PRESION.exec(recortar(v));
    if (!m) return 'La presión arterial debe tener el formato sistólica/diastólica (ej.: 120/80).';
    var sis = parseInt(m[1], 10), dia = parseInt(m[2], 10);
    if (sis < 50 || sis > 300) return 'La presión sistólica debe estar entre 50 y 300 mmHg.';
    if (dia < 30 || dia > 200) return 'La presión diastólica debe estar entre 30 y 200 mmHg.';
    if (sis <= dia) return 'La presión sistólica debe ser mayor que la diastólica.';
    return '';
  }

  function textoClinico(v, campo) {
    if (vacio(v)) return '';
    var t = recortar(v);
    if (t.length > MAX_TEXTO) return CAMPOS_TEXTO[campo] + ' no puede superar los ' + MAX_TEXTO + ' caracteres.';
    if (RE_CONTROL.test(t)) return CAMPOS_TEXTO[campo] + ' contiene caracteres no permitidos.';
    return '';
  }

  /* IMC = peso / (talla en metros)^2, 2 decimales; '' si falta el peso, la talla o alguno es inválido. */
  function imc(pesoKg, tallaCm) {
    if (vacio(pesoKg) || vacio(tallaCm) || peso(pesoKg) || talla(tallaCm)) return '';
    var p = parseFloat(recortar(pesoKg).replace(',', '.'));
    var m = parseFloat(recortar(tallaCm).replace(',', '.')) / 100;
    var r = Math.round((p / (m * m)) * 100 + 1e-9) / 100;
    return r.toFixed(2);
  }

  /* Valida la ficha completa. Devuelve { campo: mensaje } con el primer error por campo (vacío = válida). */
  function ficha(d) {
    var errores = {};
    var reglas = {
      presion_arterial: presion, temperatura: temperatura, frecuencia_cardiaca: frecuenciaCardiaca,
      frecuencia_respiratoria: frecuenciaRespiratoria, peso: peso, talla: talla
    };
    var k, msg, hayError = false, hayDato = false;
    for (k in reglas) {
      if (reglas.hasOwnProperty(k)) {
        msg = reglas[k](d[k]);
        if (msg) { errores[k] = msg; hayError = true; }
      }
    }
    for (k in CAMPOS_TEXTO) {
      if (CAMPOS_TEXTO.hasOwnProperty(k)) {
        msg = textoClinico(d[k], k);
        if (msg) { errores[k] = msg; hayError = true; }
      }
    }
    for (var i = 0; i < CAMPOS_DATO.length; i++) { if (!vacio(d[CAMPOS_DATO[i]])) hayDato = true; }
    if (!hayError && !hayDato) errores.ficha = 'La ficha debe tener al menos un dato.';
    return errores;
  }

  global.ConsultorioValidadores = {
    presion: presion, temperatura: temperatura, frecuenciaCardiaca: frecuenciaCardiaca,
    frecuenciaRespiratoria: frecuenciaRespiratoria, peso: peso, talla: talla, textoClinico: textoClinico, imc: imc, ficha: ficha
  };
})(window);
