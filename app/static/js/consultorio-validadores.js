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

  /* ───────── Etapa 4: Diagnóstico y Odontograma (espejo de validar_pieza_fdi / validar_superficie / validar_diagnostico) ───────── */
  var MSG_PIEZA = 'La pieza dental debe ser un número FDI válido (permanentes 11–18, 21–28, 31–38, 41–48; temporales 51–55, 61–65, 71–75, 81–85).';
  var SUPERFICIES = ['O', 'V', 'L', 'M', 'D', 'T'];
  var MAX_DESCRIPCION_DX = 1000, MAX_OBSERVACIONES_DX = 2000;

  function piezaValida(n) {
    var cuadrante = Math.floor(n / 10), diente = n % 10;
    if (cuadrante >= 1 && cuadrante <= 4) return diente >= 1 && diente <= 8;
    if (cuadrante >= 5 && cuadrante <= 8) return diente >= 1 && diente <= 5;
    return false;
  }

  /* '' si es válida (o vacía y no obligatoria) o el mensaje */
  function piezaFdi(v, obligatoria) {
    if (vacio(v)) return obligatoria ? MSG_PIEZA : '';
    var t = recortar(v);
    if (!RE_ENTERO.test(t)) return MSG_PIEZA;
    return piezaValida(parseInt(t, 10)) ? '' : MSG_PIEZA;
  }

  function superficie(v) {
    var t = (typeof v === 'string') ? recortar(v).toUpperCase() : '';
    for (var i = 0; i < SUPERFICIES.length; i++) { if (SUPERFICIES[i] === t) return ''; }
    return 'La superficie debe ser O (oclusal / incisal), V (vestibular), L (lingual / palatina), M (mesial), D (distal) o T (pieza completa).';
  }

  /* Valida el diagnóstico completo: { campo: mensaje } con el primer error por campo. `d.sintomas` es una lista de ids. */
  function diagnostico(d) {
    var errores = {};
    if (vacio(d.id_tipo_diagnostico)) errores.id_tipo_diagnostico = 'El tipo de diagnóstico es obligatorio.';
    else if (!RE_ENTERO.test(recortar(d.id_tipo_diagnostico)) || parseInt(recortar(d.id_tipo_diagnostico), 10) <= 0) errores.id_tipo_diagnostico = 'El tipo de diagnóstico no es válido.';
    if (!d.sintomas || !d.sintomas.length) errores.sintomas = 'Debe elegir al menos un síntoma.';
    if (vacio(d.descripcion_diagnostico) || typeof d.descripcion_diagnostico !== 'string') errores.descripcion_diagnostico = 'La descripción del diagnóstico es obligatoria.';
    else if (recortar(d.descripcion_diagnostico).length > MAX_DESCRIPCION_DX) errores.descripcion_diagnostico = 'La descripción no puede superar los ' + MAX_DESCRIPCION_DX + ' caracteres.';
    else if (RE_CONTROL.test(recortar(d.descripcion_diagnostico))) errores.descripcion_diagnostico = 'La descripción contiene caracteres no permitidos.';
    var pieza = piezaFdi(d.pieza_dental, false);
    if (pieza) errores.pieza_dental = pieza;
    if (!vacio(d.observaciones)) {
      if (recortar(d.observaciones).length > MAX_OBSERVACIONES_DX) errores.observaciones = 'Las observaciones no pueden superar los ' + MAX_OBSERVACIONES_DX + ' caracteres.';
      else if (RE_CONTROL.test(recortar(d.observaciones))) errores.observaciones = 'Las observaciones contienen caracteres no permitidos.';
    }
    return errores;
  }

  /* ───────── Etapa 5: Tratamiento y Sesiones (espejo de validar_tratamiento / validar_sesion) ───────── */
  var MAX_DESCRIPCION_TRAT = 1000, MAX_DESCRIPCION_SESION = 1000, MAX_OBSERVACIONES_SESION = 2000;
  var CANT_MIN = 1, CANT_MAX = 999;
  var RE_FECHA = /^(\d{4})-(\d{2})-(\d{2})$/;

  function fechaIsoValida(v) {
    if (typeof v !== 'string') return false;
    var m = RE_FECHA.exec(recortar(v));
    if (!m) return false;
    var a = parseInt(m[1], 10), me = parseInt(m[2], 10), d = parseInt(m[3], 10);
    var f = new Date(Date.UTC(a, me - 1, d));
    return f.getUTCFullYear() === a && f.getUTCMonth() === me - 1 && f.getUTCDate() === d;
  }

  /* entero positivo o null (un booleano no vale) */
  function idPositivo(v) {
    if (typeof v === 'boolean') return null;
    var t = recortar(v);
    return (RE_ENTERO.test(t) && parseInt(t, 10) > 0) ? parseInt(t, 10) : null;
  }

  /* '' si es válido o el mensaje. `hoy` es AAAA-MM-DD. */
  function textoLargo(v, maximo, obligatorio, msgVacio, msgLargo, msgControl) {
    if (vacio(v)) return obligatorio ? msgVacio : '';
    if (typeof v !== 'string') return msgVacio;
    var t = recortar(v);
    if (t.length > maximo) return msgLargo;
    if (RE_CONTROL.test(t)) return msgControl;
    return '';
  }

  function tratamiento(d, hoy) {
    var errores = {};
    if (vacio(d.id_tipo_tratamiento)) errores.id_tipo_tratamiento = 'El tipo de tratamiento es obligatorio.';
    else if (idPositivo(d.id_tipo_tratamiento) === null) errores.id_tipo_tratamiento = 'El tipo de tratamiento no es válido.';
    var e = textoLargo(d.descripcion_tratamiento, MAX_DESCRIPCION_TRAT, true, 'La descripción del tratamiento es obligatoria.',
                       'La descripción no puede superar los ' + MAX_DESCRIPCION_TRAT + ' caracteres.', 'La descripción contiene caracteres no permitidos.');
    if (e) errores.descripcion_tratamiento = e;
    if (!vacio(d.fecha_tratamiento)) {
      if (!fechaIsoValida(d.fecha_tratamiento)) errores.fecha_tratamiento = 'La fecha del tratamiento no es válida (AAAA-MM-DD).';
      else if (recortar(d.fecha_tratamiento) > hoy) errores.fecha_tratamiento = 'La fecha del tratamiento no puede ser futura.';
    }
    if (!vacio(d.id_diagnostico) && idPositivo(d.id_diagnostico) === null) errores.id_diagnostico = 'El diagnóstico no es válido.';
    return errores;
  }

  /* Valida la sesión completa: { campo: mensaje }. `d.procedimientos` es una lista de ids; `d.insumos`, una lista de { id_insumo, cantidad }. */
  function sesion(d, hoy) {
    var errores = {}, i;
    if (!d.procedimientos || !d.procedimientos.length) errores.procedimientos = 'Debe elegir al menos un procedimiento.';
    else {
      for (i = 0; i < d.procedimientos.length; i++) {
        if (idPositivo(d.procedimientos[i]) === null) { errores.procedimientos = 'Los procedimientos deben enviarse como una lista de IDs.'; break; }
      }
    }
    var e = textoLargo(d.descripcion_procedimiento, MAX_DESCRIPCION_SESION, true, 'La descripción de la sesión es obligatoria.',
                       'La descripción no puede superar los ' + MAX_DESCRIPCION_SESION + ' caracteres.', 'La descripción contiene caracteres no permitidos.');
    if (e) errores.descripcion_procedimiento = e;
    e = textoLargo(d.observaciones, MAX_OBSERVACIONES_SESION, false, 'Las observaciones deben ser un texto.',
                   'Las observaciones no pueden superar los ' + MAX_OBSERVACIONES_SESION + ' caracteres.', 'Las observaciones contienen caracteres no permitidos.');
    if (e) errores.observaciones = e;
    if (!vacio(d.proxima_cita)) {
      if (!fechaIsoValida(d.proxima_cita)) errores.proxima_cita = 'La próxima cita no es válida (AAAA-MM-DD).';
      else if (recortar(d.proxima_cita) < hoy) errores.proxima_cita = 'La próxima cita no puede ser anterior a hoy.';
    }
    var insumos = (d.insumos === null || d.insumos === undefined) ? [] : d.insumos;
    if (Object.prototype.toString.call(insumos) !== '[object Array]') errores.insumos = 'Los insumos deben enviarse como una lista.';
    else {
      var vistos = {};
      for (i = 0; i < insumos.length; i++) {
        var it = insumos[i];
        if (!it || typeof it !== 'object' || idPositivo(it.id_insumo) === null) { errores.insumos = 'Cada insumo necesita su tipo de insumo.'; break; }
        var n = idPositivo(it.cantidad);
        if (n === null || n < CANT_MIN || n > CANT_MAX) { errores.insumos = 'La cantidad de cada insumo debe ser un número entero de ' + CANT_MIN + ' a ' + CANT_MAX + '.'; break; }
        var clave = 'i' + idPositivo(it.id_insumo);
        if (vistos[clave]) { errores.insumos = 'No repita el mismo insumo: sume las cantidades en un solo renglón.'; break; }
        vistos[clave] = true;
      }
    }
    return errores;
  }

  /* ───────── Etapa 6: Receta y Órdenes (espejo de validar_receta / validar_orden_estudio / validar_orden_analisis) ───────── */
  var MAX_INDICACIONES_RECETA = 2000, MAX_TEXTO_MEDICAMENTO = 100, MAX_MOTIVO_ORDEN = 1000, MAX_INDICACIONES_ORDEN = 2000;

  function vinculos(d, errores) {
    if (!vacio(d.id_diagnostico) && idPositivo(d.id_diagnostico) === null) errores.id_diagnostico = 'El diagnóstico no es válido.';
    if (!vacio(d.id_tratamiento) && idPositivo(d.id_tratamiento) === null) errores.id_tratamiento = 'El tratamiento no es válido.';
  }

  /* Valida la receta completa: { campo: mensaje }. `d.medicamentos` es una lista de { id_medicamento, dosis, frecuencia, duracion }. */
  function receta(d) {
    var errores = {}, i;
    var e = textoLargo(d.indicaciones_generales, MAX_INDICACIONES_RECETA, true, 'Las indicaciones generales son obligatorias.',
                       'Las indicaciones generales no pueden superar los ' + MAX_INDICACIONES_RECETA + ' caracteres.', 'Las indicaciones generales contienen caracteres no permitidos.');
    if (e) errores.indicaciones_generales = e;
    var meds = d.medicamentos;
    if (Object.prototype.toString.call(meds) !== '[object Array]' || !meds.length) errores.medicamentos = 'Debe agregar al menos un medicamento.';
    else {
      var vistos = {}, campos = ['dosis', 'frecuencia', 'duracion'];
      for (i = 0; i < meds.length && !errores.medicamentos; i++) {
        var it = meds[i];
        if (!it || typeof it !== 'object' || idPositivo(it.id_medicamento) === null) { errores.medicamentos = 'Cada medicamento necesita su medicamento.'; break; }
        for (var k = 0; k < campos.length; k++) {
          var valor = it[campos[k]];
          if (vacio(valor) || typeof valor !== 'string') { errores.medicamentos = 'Cada medicamento debe tener dosis, frecuencia y duración.'; break; }
          valor = recortar(valor);
          if (valor.length > MAX_TEXTO_MEDICAMENTO) { errores.medicamentos = 'La dosis, la frecuencia y la duración no pueden superar los ' + MAX_TEXTO_MEDICAMENTO + ' caracteres.'; break; }
          if (RE_CONTROL.test(valor)) { errores.medicamentos = 'La dosis, la frecuencia y la duración contienen caracteres no permitidos.'; break; }
        }
        if (errores.medicamentos) break;
        var clave = 'm' + idPositivo(it.id_medicamento);
        if (vistos[clave]) { errores.medicamentos = 'No repita el mismo medicamento.'; break; }
        vistos[clave] = true;
      }
    }
    vinculos(d, errores);
    return errores;
  }

  function orden(d, campoTipo, etiquetaTipo) {
    var errores = {};
    if (vacio(d[campoTipo])) errores[campoTipo] = 'El ' + etiquetaTipo + ' es obligatorio.';
    else if (idPositivo(d[campoTipo]) === null) errores[campoTipo] = 'El ' + etiquetaTipo + ' no es válido.';
    var e = textoLargo(d.motivo_orden, MAX_MOTIVO_ORDEN, true, 'El motivo de la orden es obligatorio.',
                       'El motivo no puede superar los ' + MAX_MOTIVO_ORDEN + ' caracteres.', 'El motivo contiene caracteres no permitidos.');
    if (e) errores.motivo_orden = e;
    e = textoLargo(d.indicaciones, MAX_INDICACIONES_ORDEN, false, 'Las indicaciones deben ser un texto.',
                   'Las indicaciones no pueden superar los ' + MAX_INDICACIONES_ORDEN + ' caracteres.', 'Las indicaciones contienen caracteres no permitidos.');
    if (e) errores.indicaciones = e;
    vinculos(d, errores);
    return errores;
  }
  function ordenEstudio(d) { return orden(d, 'id_tipo_estudio', 'tipo de estudio'); }
  function ordenAnalisis(d) { return orden(d, 'id_tipo_analisis', 'tipo de análisis'); }

  global.ConsultorioValidadores = {
    presion: presion, temperatura: temperatura, frecuenciaCardiaca: frecuenciaCardiaca,
    frecuenciaRespiratoria: frecuenciaRespiratoria, peso: peso, talla: talla, textoClinico: textoClinico, imc: imc, ficha: ficha,
    piezaFdi: piezaFdi, piezaValida: piezaValida, superficie: superficie, diagnostico: diagnostico,
    tratamiento: tratamiento, sesion: sesion,
    receta: receta, ordenEstudio: ordenEstudio, ordenAnalisis: ordenAnalisis
  };
})(window);
