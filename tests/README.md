# Tests

Scripts de verificación (sin pytest): cada uno imprime líneas `OK` / `FAIL` y cierra con `FALLOS: ninguno`
(o la lista de lo que falló). Se corren **desde la raíz del proyecto** con el Python del entorno virtual.

```powershell
# uno solo
.\.venv\Scripts\python.exe -I tests\facturacion\smoke_caja.py

# todos los smoke_*.py
Get-ChildItem tests -Recurse -Filter smoke_*.py | ForEach-Object { "== $($_.Name)"; .\.venv\Scripts\python.exe -I $_.FullName 2>$null | Select-String 'FAIL|FALLOS' }
```

## Qué hay

| Carpeta | Script | Cubre |
|---|---|---|
| `facturacion/` | `smoke_marca_tarjeta`, `smoke_entidades` (emisora + adherida), `smoke_items` (tipo ítems + ítems), `smoke_caja`, `smoke_deposito`, `smoke_cliente` | CRUD de cada referencial, validaciones, bloqueos de baja, auditoría y permisos |
| `facturacion/` | `smoke_apertura_caja` | Apertura y Cierre de Caja: los dos bloqueos de apertura doble (aplicación y base), anular, cerrar, visibilidad por rol, filtros, permisos por acción, auditoría y la baja de Caja bloqueada. **Usa usuarios reales (Administrador, Cajero y Recepción) con sesiones simuladas y aborta si alguno tiene una caja abierta de verdad** |
| `facturacion/` | `smoke_pedido_cliente` | Registrar Pedido Cliente: esquema, alta con importes calculados por el servidor (aunque el navegador mande otros), stock (insuficiente, ítems sin stock, descuento y reposición), anular (también FACTURADO), listado compartido y filtros, detalle, PDF, auditoría, permisos, bloqueos de baja de Ítems y Cliente y **concurrencia** (última unidad, 20 pedidos con ítems en orden cruzado, anulaciones simultáneas). Usa usuarios reales con sesiones simuladas y datos `ZZ` que borra por ID |
| `facturacion/` | `smoke_ventas` | Registrar Ventas y Cuentas a Cobrar: empresa/timbrado, `sp_siguiente_numero_factura` (numeración, vigencia, rango, concurrencia), triggers (cuenta creada/anulada, auditoría inmutable), vista `v_estado_cuenta_cliente`, venta sin caja abierta, pedido facturado dos veces (incluida la concurrencia), anulación (pedido a PENDIENTE, número no reutilizado, caja cerrada) y permisos; **etapa 2:** PDF de la factura (2 páginas, número, RUC, total, marca ANULADA), venta de tratamiento (incluida la doble facturación concurrente y facturar-vs-cancelar), anulación con y sin la casilla del pedido, bloqueo en Consultorio y la decisión sobre `ItemDao`. **Desactiva el timbrado real y usa uno `ZZ` (998-998), y lo restaura en el `finally`: no correrlo con el sistema en uso.** Aborta si el Cajero tiene una caja abierta de verdad |
| `facturacion/` | `smoke_numero_letras` | Número a letras (`app/Services/numero_letras.py`): 0, 1, 15, 100, 101, 1.000, 1.000.000, 21.500.000, 999.999.999.999 y más; sin base de datos |
| `facturacion/` | `_limpieza.py` | Helper `borrar_auditoria(cur, entidad, ids)`: los tests borran su auditoría saltando el trigger `trg_auditoria_inmutable` solo en su conexión (`session_replication_role = replica`) |
| `facturacion/` | `smoke_permisos_cajero` | Matriz de permisos del Cajero contra la regla y el catálogo del menú (falla si un movimiento nuevo de Facturación no está en `schema_permisos_cajero.sql`), y su comportamiento real con la sesión de un Cajero (200/400/403 por endpoint y por vista, menú). **Solo lectura** |
| `facturacion/` | `smoke_reactivar` | Estado / "Mostrar inactivos" / Reactivar de Forma de Cobro, Marca, Emisora, Adherida, Tipo Ítems e Ítems + protocolo `EN_USO` de Forma de Cobro |
| `facturacion/` | `browser_test.py` | Las 6 vistas con `facturacion-listado.js` en **Edge headless** (DOM y SweetAlert2 reales, `fetch` simulado) |
| `facturacion/` | `run_js_validadores.js` + `comparar_js_py.py` | Que `facturacion-validadores.js` dé lo mismo que `utils.py` |
| `agendamiento/` | `smoke_consultorio`, `smoke_paciente` | Regresión de Consultorio y Paciente (incluye los bloqueos por cajas y por cliente) |
| `consultorio/` | `smoke_tipo_tratamiento` | Tipo Tratamiento con precio e IVA: alta, modificación, precio e IVA inválidos, datos iniciales (relajado), las dos migraciones idempotentes (en una base temporal que crea y borra, en ambos órdenes) y regresión de Gestionar Tratamientos. El resto del módulo Consultorio todavía no tiene tests |

## Navegador y espejo JS

```powershell
# las vistas en Edge (la ruta de msedge.exe está en la constante EDGE del script); la salida va fuera del repo
.\.venv\Scripts\python.exe -I tests\facturacion\browser_test.py $env:TEMP\oc_vistas_html

# validadores JS vs Python (usa cscript/JScript de Windows, no hace falta Node)
$js = (Resolve-Path app\static\js\facturacion-validadores.js).Path
cscript //nologo //E:jscript tests\facturacion\run_js_validadores.js "$js" "44444401-7|80012345-0|80012345-6|1234|12345" "$env:TEMP\salida_js.txt"
.\.venv\Scripts\python.exe -I tests\facturacion\comparar_js_py.py "$env:TEMP\salida_js.txt"
```

## Antes de correrlos

- **Usan la base real** (`odontosisbd`, la de `app/conexion/Conexion.py`) con el esquema ya aplicado. No hay base de pruebas.
- Crean registros con prefijo `ZZ` y **borran solo lo que crearon** (nunca por entidad completa). También quitan y
  vuelven a poner permisos de un rol que no es Administrador; si un test se corta a la mitad, re-correr el SQL
  `schema_permisos_*.sql` correspondiente (es idempotente) los restaura.
- Algunos chequean los **datos iniciales** (nombres de los seeds): fallan si se editaron a mano desde la pantalla.
- No modifican ni borran datos reales; las tablas de auditoría conservan lo que se hizo desde el navegador.
- Forma de Cobro se cubre dentro de `smoke_reactivar.py` (no hay un script CRUD aparte).
