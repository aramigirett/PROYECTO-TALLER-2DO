# Resumen — Registrar Notas de Crédito y Débito (sin commitear)

## Archivos
- SQL (idempotentes): `app/dao/modulo_facturacion/schema_notas_columnas.sql` (2 columnas nuevas), `schema_notas.sql` (función, 5 triggers, `fn_total_reintegros`, funciones y 3 vistas actualizadas); `app/dao/modulo_seguridad/schema_permisos_notas.sql`, `schema_permisos_cajero.sql` (30 filas).
- Código: `dao/modulo_facturacion/nota_credito_debito/NotaCreditoDebitoDao.py`, `rutas/modulo_facturacion/nota_credito_debito/` (api, routes, `nota-index.html`), `app/Services/nota_pdf_service.py`, `factura_pdf_service.py` (parametrizado, sin cambiar la factura), `menu_catalog.py`, `app/__init__.py`.
- Conexiones: `VentaDao` (anular venta con notas), `AperturaCajaDao` (movimientos y reintegros en el cierre), `apertura_caja_api.py` y `apertura-caja-index.html` (reintegros en el cierre).
- Docs: `CLAUDE.md`, `tests/README.md`. Tests: `tests/facturacion/smoke_notas.py`; ajustes en `smoke_cobranzas.py` y `smoke_remision.py`.

## Decisiones aprobadas aplicadas
`id_apertura` (INT NOT NULL, FK) y `monto_reintegro` (NUMERIC(12,0) NOT NULL DEFAULT 0) en `nota_credito_debito_cab` (hay que sumarlas al DER junto con `forma_cobro.tipo` y `cobro_det.numero_referencia`); reintegro bloqueado sin efectivo: "No hay efectivo suficiente en la caja para el reintegro (disponible Gs. N)."

## Pruebas
- `smoke_notas`: 205 OK, 0 fallos. Browser (`nota-index`, `fetch` simulado): con_caja 54 y sin_caja 20 comprobaciones OK. PDF revisado visualmente.
- Regresión: todos los `smoke_*` pasan salvo `smoke_apertura_caja` y `smoke_ventas`, que ABORTAN por diseño porque el Administrador tiene una caja REAL abierta (apertura 125). Cerrarla y correrlos. Los browser de apertura, venta, cobro, remisión y las 6 vistas de referenciales siguen OK.
- `smoke_cobranzas` ya no depende de la caja del Administrador (cobra con un usuario libre).

## Diferencias entre el prompt y la base
`nota_credito_debito_cab` no tenía `id_apertura` ni reintegro (agregados con migración). `v_libro_ventas` venía del DER y nadie la usaba: ahora incluye las notas.

## Pendiente
- Probar en navegador real el alta y la anulación de una nota y su PDF.
- Cerrar la caja real 125 y correr `smoke_apertura_caja` y `smoke_ventas`.
- Forma de cobro #17 "BHDJDGJ" (tipo sin definir), de Cobranzas.
- Arqueo de Caja y usuario de BD sin superusuario.
