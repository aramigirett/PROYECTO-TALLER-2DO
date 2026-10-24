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
