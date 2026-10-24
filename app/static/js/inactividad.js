/*
 * Cierre de sesión por inactividad — lado cliente.
 *
 * El SERVIDOR decide cuándo vence la sesión (ver app/rutas/modulo_seguridad/sesion_seguridad.py); este script solo:
 *   1. avisa con un modal y cuenta regresiva cuando faltan `aviso` segundos,
 *   2. renueva la sesión con "Seguir conectado" (POST /sesion/extender),
 *   3. redirige al login cuando el servidor confirma que venció.
 * Sirve igual en base.html (SB Admin 2 / Bootstrap 4) y base_tabler.html (Tabler / Bootstrap 5): el modal es propio
 * (HTML + CSS inyectado) y no depende de ninguna versión de Bootstrap ni de jQuery. ES5 para poder probarlo con Node.
 *
 * Configuración (atributos data- de la etiqueta <script>, que salen de SESSION_INACTIVIDAD_MINUTOS / _AVISO_SEGUNDOS del .env):
 *   data-limite, data-aviso (segundos), data-url-estado, data-url-extender, data-url-expirar, data-url-logout
 */
(function (raiz) {
    'use strict';

    var EVENTOS_ACTIVIDAD = ['mousedown', 'keydown', 'touchstart', 'scroll', 'mousemove'];
    var INTERVALO_AVISO_SERVIDOR_MS = 60000;   // como mucho un aviso de actividad por minuto

    function formatear(segundos) {
        var m = Math.floor(segundos / 60), s = segundos % 60;
        return m + ':' + (s < 10 ? '0' : '') + s;
    }

    /* cfg: {limite, aviso, urlEstado, urlExtender, urlExpirar, urlLogout}
       env: {ahora(), setInterval(fn, ms), fetchJson(url, metodo) -> Promise<{ok, status, datos}>, ir(url), modal} */
    function crear(cfg, env) {
        var estado = {
            deadline: env.ahora() + cfg.limite * 1000,
            visible: false,
            sincronizando: false,
            ultimoAviso: env.ahora()
        };

        function restante() {
            return Math.ceil((estado.deadline - env.ahora()) / 1000);
        }

        function irAlLogin(datos) {
            env.ir((datos && datos.redirigir) || cfg.urlExpirar);
        }

        function mostrar() {
            estado.visible = true;
            env.modal.mostrar(formatear(Math.max(0, restante())));
        }

        function ocultar() {
            estado.visible = false;
            env.modal.ocultar();
        }

        /* Pregunta al servidor cuánto le queda a la sesión (no la renueva) y se alinea con esa respuesta. */
        function sincronizar() {
            if (estado.sincronizando) { return; }
            estado.sincronizando = true;
            env.fetchJson(cfg.urlEstado, 'GET').then(function (r) {
                estado.sincronizando = false;
                if (r.status === 401) { irAlLogin(r.datos); return; }
                if (r.ok && r.datos && typeof r.datos.restante === 'number') {
                    estado.deadline = env.ahora() + r.datos.restante * 1000;
                }
                if (restante() <= 0) { env.ir(cfg.urlExpirar); }
                else if (restante() <= cfg.aviso) { mostrar(); }
                else if (estado.visible) { ocultar(); }   // otra pestaña mantuvo viva la sesión
            }, function () {
                // Sin red no se puede confirmar: se avisa igual y se sigue contando con el reloj local
                estado.sincronizando = false;
                if (restante() <= 0) { env.ir(cfg.urlExpirar); } else { mostrar(); }
            });
        }

        function tick() {
            var r = restante();
            if (estado.visible) {
                if (r <= 0) { sincronizar(); } else { env.modal.actualizar(formatear(r)); }
            } else if (r <= cfg.aviso) {
                sincronizar();
            }
        }

        /* "Seguir conectado" */
        function seguirConectado() {
            env.fetchJson(cfg.urlExtender, 'POST').then(function (r) {
                if (r.status === 401) { irAlLogin(r.datos); return; }
                estado.deadline = env.ahora() + ((r.datos && r.datos.restante) || cfg.limite) * 1000;
                estado.ultimoAviso = env.ahora();
                ocultar();
            }, function () {
                env.modal.error('No se pudo contactar al servidor. Intentá de nuevo.');
            });
        }

        /* Actividad del usuario: reinicia el reloj local y, a lo sumo una vez por minuto, avisa al servidor.
           Con el modal abierto se ignora: solo el botón mantiene la sesión. */
        function actividad() {
            if (estado.visible) { return; }
            var ahora = env.ahora();
            estado.deadline = ahora + cfg.limite * 1000;
            if (ahora - estado.ultimoAviso >= INTERVALO_AVISO_SERVIDOR_MS) {
                estado.ultimoAviso = ahora;
                env.fetchJson(cfg.urlExtender, 'POST').then(function (r) {
                    if (r.status === 401) { irAlLogin(r.datos); }
                }, function () { /* un aviso perdido no es grave: al llegar el aviso se re-sincroniza con el servidor */ });
            }
        }

        env.modal.alSeguir(seguirConectado);
        env.setInterval(tick, 1000);
        return { tick: tick, actividad: actividad, seguirConectado: seguirConectado, estado: estado, restante: restante };
    }

    /* ---- Navegador ---- */
    var CSS =
        '#oc-inact-overlay{position:fixed;top:0;right:0;bottom:0;left:0;background:rgba(10,20,40,.6);z-index:20000;display:none;' +
        'align-items:center;justify-content:center;font-family:inherit}' +
        '#oc-inact-overlay.oc-inact-on{display:flex}' +
        '#oc-inact-box{background:#fff;color:#1f2d3d;border-radius:12px;max-width:420px;width:calc(100% - 32px);' +
        'padding:24px;box-shadow:0 12px 40px rgba(0,0,0,.35);text-align:center}' +
        '#oc-inact-box h5{margin:0 0 8px;font-size:1.15rem;font-weight:700}' +
        '#oc-inact-box p{margin:0 0 6px;font-size:.95rem}' +
        '#oc-inact-cuenta{font-size:2.2rem;font-weight:700;color:#c0392b;margin:8px 0 16px;font-variant-numeric:tabular-nums}' +
        '#oc-inact-error{color:#c0392b;font-size:.85rem;min-height:1.1em;margin-bottom:8px}' +
        '#oc-inact-box .oc-inact-btn{border:0;border-radius:8px;padding:10px 18px;font-size:.95rem;font-weight:600;cursor:pointer;margin:0 4px}' +
        '#oc-inact-seguir{background:#1a73c7;color:#fff}' +
        '#oc-inact-salir{background:#e6eaef;color:#1f2d3d;text-decoration:none;display:inline-block}';

    function modalNavegador(doc, urlLogout) {
        var estilo = doc.createElement('style');
        estilo.appendChild(doc.createTextNode(CSS));
        doc.head.appendChild(estilo);

        var overlay = doc.createElement('div');
        overlay.id = 'oc-inact-overlay';
        overlay.setAttribute('role', 'alertdialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-labelledby', 'oc-inact-titulo');
        overlay.innerHTML =
            '<div id="oc-inact-box">' +
            '<h5 id="oc-inact-titulo">¿Sigues ahí?</h5>' +
            '<p>Tu sesión se cerrará por inactividad en</p>' +
            '<div id="oc-inact-cuenta" aria-live="polite"></div>' +
            '<div id="oc-inact-error"></div>' +
            '<button type="button" class="oc-inact-btn" id="oc-inact-seguir">Seguir conectado</button>' +
            '<a class="oc-inact-btn" id="oc-inact-salir" href="' + urlLogout + '">Cerrar sesión</a>' +
            '</div>';
        doc.body.appendChild(overlay);

        var cuenta = doc.getElementById('oc-inact-cuenta');
        var error = doc.getElementById('oc-inact-error');
        var boton = doc.getElementById('oc-inact-seguir');
        return {
            mostrar: function (texto) {
                cuenta.textContent = texto; error.textContent = '';
                overlay.className = 'oc-inact-on';
                try { boton.focus(); } catch (e) { /* sin foco no pasa nada */ }
            },
            ocultar: function () { overlay.className = ''; },
            actualizar: function (texto) { cuenta.textContent = texto; },
            error: function (texto) { error.textContent = texto; },
            alSeguir: function (fn) { boton.addEventListener('click', fn); }
        };
    }

    function fetchJson(ventana, url, metodo) {
        return ventana.fetch(url, { method: metodo, credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
            .then(function (resp) {
                return resp.json().then(function (d) { return d; }, function () { return null; })
                    .then(function (datos) { return { ok: resp.ok, status: resp.status, datos: datos }; });
            });
    }

    function iniciar(ventana, doc) {
        var tag = doc.currentScript || doc.querySelector('script[data-limite][src*="inactividad"]');
        if (!tag) { return null; }
        var cfg = {
            limite: parseInt(tag.getAttribute('data-limite'), 10),
            aviso: parseInt(tag.getAttribute('data-aviso'), 10),
            urlEstado: tag.getAttribute('data-url-estado'),
            urlExtender: tag.getAttribute('data-url-extender'),
            urlExpirar: tag.getAttribute('data-url-expirar'),
            urlLogout: tag.getAttribute('data-url-logout')
        };
        if (!(cfg.limite > 0) || !(cfg.aviso > 0)) { return null; }

        function arrancar() {
            var env = {
                ahora: function () { return new Date().getTime(); },
                setInterval: function (fn, ms) { return ventana.setInterval(fn, ms); },
                fetchJson: function (url, metodo) { return fetchJson(ventana, url, metodo); },
                ir: function (url) { ventana.location.href = url; },
                modal: modalNavegador(doc, cfg.urlLogout)
            };
            var control = crear(cfg, env);
            EVENTOS_ACTIVIDAD.forEach(function (nombre) {
                doc.addEventListener(nombre, control.actividad, { passive: true, capture: true });
            });
        }
        if (doc.readyState === 'loading') { doc.addEventListener('DOMContentLoaded', arrancar); } else { arrancar(); }
        return true;
    }

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { crear: crear, formatear: formatear };
    } else if (raiz && raiz.document) {
        raiz.OcInactividad = { crear: crear, formatear: formatear };   // para las pruebas en el navegador
        iniciar(raiz, raiz.document);
    }
})(typeof window !== 'undefined' ? window : null);
