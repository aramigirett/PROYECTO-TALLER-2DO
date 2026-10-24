# Resumen — Registrar Nota de Remisión (sin commitear)

## Archivos
- SQL (idempotentes, sin tocar tablas): `app/dao/modulo_facturacion/schema_remision.sql` (función, 4 triggers, vista), `app/dao/modulo_seguridad/schema_permisos_remision.sql`, `schema_permisos_cajero.sql` (27 filas).
- Código: `dao/modulo_facturacion/remision/RemisionDao.py`, `rutas/modulo_facturacion/remision/` (api, routes, `remision-index.html`), `app/Services/remision_pdf_service.py`, `menu_catalog.py`, `app/__init__.py`, `facturacion-validadores.js` (solo exporta `texto`).
- Conexiones: `VentaDao` (anular venta con remisiones EMITIDAS), `DepositoDao` (baja con remisiones EMITIDAS).
- Docs: `CLAUDE.md`, `tests/README.md`. Tests: `tests/facturacion/smoke_remision.py`, adaptación de `smoke_*` no necesaria.

## Decisiones aprobadas aplicadas
Depósito elegido a mano (solo activos) y la remisión solo incluye ítems de ese depósito (validado también en el trigger); servicios no aparecen; motivo fijo VENTA; Cajero con ver, nuevo y anular.

## Pruebas
- `smoke_remision`: 158 OK, 0 fallos. Browser (`remision-index`, `fetch` simulado): 46 comprobaciones OK. PDF revisado visualmente.
- Regresión: todos los `smoke_*` pasan salvo los 3 que abortan por diseño porque el Administrador tiene una caja REAL abierta (apertura 125): `smoke_apertura_caja`, `smoke_ventas` y `smoke_cobranzas`. Cerrar esa caja y correrlos.

## Diferencias entre el prompt y la base
La cabecera tiene campos obligatorios no mencionados (depósito, fecha de traslado, dirección de llegada, responsable) y `uq_remision_det_item` impide repetir un ítem en una remisión.

## Pendiente
- Probar en navegador real el guardado de una remisión y el PDF.
- Cerrar la caja real 125 y correr los 3 tests que abortan.
- Forma de cobro #17 "BHDJDGJ" (tipo sin definir), de Cobranzas.
- Nota de Crédito/Débito y Arqueo de Caja.
