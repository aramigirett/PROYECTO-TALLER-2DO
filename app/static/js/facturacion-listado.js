/*
 * Helpers de los listados de referenciales de Facturación (Estándar de referenciales, punto 4):
 * columna Estado, switch "Mostrar inactivos", botones Editar / Anular / Reactivar y sus confirmaciones
 * con SweetAlert2. Las vistas pasan los permisos (puede(...)) y los textos; el servidor valida SIEMPRE.
 *
 * Escrito en ES5 (sin async/arrow) a propósito: las funciones puras se pueden ejecutar con JScript
 * para probarlas fuera del navegador. Requiere SweetAlert2 (`Swal`) solo en anular() y reactivar().
 */
(function (global) {
  'use strict';

  function escapar(t) {
    return String(t === null || t === undefined ? '' : t).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* fetch que siempre resuelve { ok, status, data } (data = null si la respuesta no es JSON, ej. un 403 en HTML). */
  function pedir(url, opciones) {
    return fetch(url, opciones).then(function (resp) {
      return resp.json().then(
        function (data) { return { ok: resp.ok, status: resp.status, data: data }; },
        function () { return { ok: resp.ok, status: resp.status, data: null }; }
      );
    });
  }

  /* URL del listado: con el switch "Mostrar inactivos" encendido pide también los anulados (requiere 'ver'). */
  function urlListado(api, chk) {
    return (chk && chk.checked) ? api + '?inactivos=1' : api;
  }

  function badgeEstado(activo) {
    return activo
      ? '<span class="badge bg-success-lt">Activo</span>'
      : '<span class="badge bg-secondary-lt">Inactivo</span>';
  }

  /* Las filas inactivas se ven atenuadas. */
  function claseFila(activo) { return activo ? '' : 'text-muted'; }

  /*
   * Botones de una fila. Activo: Editar / Anular (según permisos). Inactivo: solo Reactivar, que usa
   * el mismo permiso que editar. o = { activo, id, descripcion, puedeEditar, puedeAnular }.
   */
  function acciones(o) {
    var b = [];
    var id = escapar(o.id);
    var desc = escapar(o.descripcion);
    if (o.activo) {
      if (o.puedeEditar) {
        b.push('<button type="button" class="btn btn-sm btn-outline-primary" data-accion="editar" data-id="' + id +
               '" title="Editar"><i class="fas fa-edit"></i></button>');
      }
      if (o.puedeAnular) {
        b.push('<button type="button" class="btn btn-sm btn-outline-danger" data-accion="anular" data-id="' + id +
               '" data-desc="' + desc + '" title="Anular"><i class="fas fa-ban"></i></button>');
      }
    } else if (o.puedeEditar) {
      b.push('<button type="button" class="btn btn-sm btn-outline-success" data-accion="reactivar" data-id="' + id +
             '" data-desc="' + desc + '" title="Reactivar"><i class="fas fa-undo me-1"></i>Reactivar</button>');
    }
    return b.join('');
  }

  function recargar(o) {
    return Promise.resolve(o.recargar ? o.recargar() : null);
  }

  /* Ejecuta el pedido y muestra el resultado. Devuelve una promesa con true (hecho) o false. */
  function ejecutar(o, metodo, urlFinal, tituloError, exito) {
    return pedir(urlFinal, { method: metodo }).then(function (r) {
      var data = r.data;
      if (data && data.success) {
        return recargar(o).then(function () {
          Swal.fire(exito, data.mensaje, 'success');
          return true;
        });
      }
      var errText = (data && (data.mensaje || data.error)) || o.errorDefault;
      if (global.mostrarAvisoValidacion && data && (data.tipo || data.mensaje || data.error)) {
        global.mostrarAvisoValidacion(data);
      } else {
        Swal.fire(tituloError, errText, (data && data.tipo === 'estado') || r.status === 409 ? 'warning' : 'error');
      }
      return recargar(o).then(function () { return false; });
    }, function () {
      Swal.fire('Error', 'Ocurrió un error de conexión.', 'error');
      return false;
    });
  }

  /*
   * Confirma y anula (DELETE). o = { api, id, descripcion, titulo, exito, errorDefault, recargar }.
   * Si el servidor bloquea la baja (409, ej. "tiene ítems asignados") muestra su mensaje tal cual.
   */
  function anular(o) {
    return Swal.fire({
      title: o.titulo, text: o.descripcion, icon: 'warning', showCancelButton: true,
      confirmButtonText: 'Sí, anular', cancelButtonText: 'Cancelar', confirmButtonColor: '#d63939'
    }).then(function (c) {
      if (!c.isConfirmed) { return false; }
      return ejecutar(o, 'DELETE', o.api + '/' + o.id, 'No se pudo anular', o.exito);
    });
  }

  /* Confirma y reactiva (PATCH .../reactivar). Mismas opciones que anular(). */
  function reactivar(o) {
    return Swal.fire({
      title: o.titulo, text: o.descripcion, icon: 'question', showCancelButton: true,
      confirmButtonText: 'Sí, reactivar', cancelButtonText: 'Cancelar'
    }).then(function (c) {
      if (!c.isConfirmed) { return false; }
      return ejecutar(o, 'PATCH', o.api + '/' + o.id + '/reactivar', 'No se pudo reactivar', o.exito);
    });
  }

  global.FacturacionListado = {
    escapar: escapar, pedir: pedir, urlListado: urlListado, badgeEstado: badgeEstado, claseFila: claseFila,
    acciones: acciones, anular: anular, reactivar: reactivar
  };
})(window);
