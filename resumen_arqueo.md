# Resumen — Mantener Cuenta Bancaria + Registrar Arqueo de Caja (sin commitear)

## Archivos
- SQL (idempotentes): `app/dao/modulo_facturacion/schema_cuenta_bancaria.sql` (tabla, FK en `recaudacion_depositar`, datos iniciales), `schema_arqueo.sql` (procedimiento, funciones, 3 triggers, vista); `app/dao/modulo_seguridad/schema_permisos_cuenta_bancaria.sql`, `schema_permisos_arqueo.sql`, `schema_permisos_cajero.sql` (35 filas).
- Código: `dao/modulo_facturacion/cuenta_bancaria/`, `dao/modulo_facturacion/arqueo/`, `rutas/modulo_facturacion/cuenta_bancaria/` y `arqueo/` (api, routes, vistas), `app/Services/arqueo_pdf_service.py`, `menu_catalog.py`, `app/__init__.py`, `utils.py` + `facturacion-validadores.js` (`numero_cuenta` en espejo).
- Conexiones: `EntidadEmisoraDao` (cuentas bancarias), `AperturaCajaDao` y `apertura-caja-index.html` (muestra "Con arqueo / Sin arqueo").
- Docs: `CLAUDE.md`, `tests/README.md`. Tests: `smoke_cuenta_bancaria.py`, `smoke_arqueo.py`; ajustes en `smoke_notas.py`, `smoke_permisos_cajero.py`, `run_js_validadores.js` y `comparar_js_py.py`.

## Decisiones aprobadas aplicadas
Cajero con ver, nuevo, anular y estado en Arqueo, pero **nadie arquea su propia caja** (validado en API, `sp_registrar_arqueo` y trigger; el Administrador arquea cualquier apertura salvo las suyas). Efectivo contado menor al fondo: se permite (faltante con observación), efectivo a depositar 0; si no hay nada que depositar no se genera la recaudación.

## Diferencias entre el prompt y la base (hay que sumarlas al DER)
`cuenta_bancaria` no existía (creada) y `recaudacion_depositar` no tenía `id_cuenta_bancaria` (agregada, con FK y un CHECK que la exige si está DEPOSITADA). Las otras columnas pendientes del DER: `forma_cobro.tipo`, `cobro_det.numero_referencia`, `nota_credito_debito_cab.id_apertura` y `monto_reintegro`.

## Pruebas
- `smoke_cuenta_bancaria`: 84 OK. `smoke_arqueo`: 166 OK. Paridad JS/Python: 0 diferencias de 95. Browser: arqueo 43, cuenta bancaria 19; apertura, venta, cobro, remisión, notas y las 6 vistas de referenciales siguen OK. PDF del arqueo revisado visualmente.
- Regresión: todos los `smoke_*` pasan con 0 fallos.
- Ajustes de tests por el cambio de permisos: `smoke_notas` (cuenta de filas del Cajero >= 30) y `smoke_permisos_cajero` (cuentabancaria en "solo ver").

## Pendiente
- Probar en navegador real: alta de una cuenta bancaria, un arqueo de una caja cerrada por otro usuario, marcar depositada y el PDF.
- Forma de cobro #17 "BHDJDGJ" (tipo sin definir), de Cobranzas.
- Sumar al DER las 6 columnas/tablas listadas arriba; tanda de cierre: usuario de BD sin superusuario.
