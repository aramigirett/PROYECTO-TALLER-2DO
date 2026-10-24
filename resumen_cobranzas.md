# Resumen — Registrar Cobranzas por Forma de Cobro (sin commitear)

## Archivos
- SQL: `app/dao/modulo_facturacion/schema_cobranzas_columnas.sql`, `schema_cobranzas.sql` (parche en `schema_objetos_bd.sql`); `app/dao/modulo_seguridad/schema_permisos_id_menu.sql`, `schema_permisos_cobranzas.sql`, `schema_permisos_cajero.sql`.
- Código: `dao/modulo_facturacion/cobro/CobroDao.py`, `rutas/modulo_facturacion/cobro/` (api, routes, `cobro-index.html`), `app/Services/recibo_pdf_service.py`, `menu_catalog.py`, `app/__init__.py`, validadores (`utils.py` + `facturacion-validadores.js`).
- Conexiones: Forma de Cobro (tipo), Marca, Adherida, Emisora, Venta (¿Cobrar ahora?, bloqueo de anular), Apertura de Caja (recaudado y cierre).
- Docs: `CLAUDE.md`, `tests/README.md`.

## Tests
- `smoke_cobranzas.py`: 222 OK, 0 fallos. Regresión: todos los smoke pasan salvo `smoke_apertura_caja` y `smoke_ventas`, que ABORTAN por diseño porque el Cajero real (usuario 8) tiene la apertura 115 abierta: cerrarla y volver a correrlos.
- `smoke_reactivar` adaptado (envía `tipo`). Browser: forma-cobro, apertura (3 escenarios), venta (2) y cobro (con_caja, sin_caja, precarga) OK.

## Cambios respecto del plan
- Descubrimiento: la migración del DER volvió obligatorio `permisos.id_menu` y rompía PermisoDao/seeds/tests; solución sin tocar tablas: trigger `trg_permisos_resolver_menu` + fila `cobro` en `menu`.
- Las 2 columnas nuevas (`forma_cobro.tipo`, `cobro_det.numero_referencia`) deben agregarse al DER.

## Pendiente
- Forma de cobro `#17 "BHDJDGJ"`: sin tipo deducible. Asignarle tipo (o darla de baja) y re-correr `schema_cobranzas_columnas.sql` para aplicar NOT NULL.
- Cerrar la caja real 115 y correr `smoke_apertura_caja` y `smoke_ventas`.
- Probar en navegador real el guardado de un cobro.
- Nota de Crédito, Arqueo de Caja, usuario de BD sin superusuario.
