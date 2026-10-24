# Migración 02 — resumen (APLICADA, sin commitear)

Rama `migracion-02` (desde `main`, que se avanzó por fast-forward a `finalizando`; ese `main` local no está pusheado).
Script: `migraciones/02_migracion_requiere_codigo.sql` (reescrito idempotente y con los backfills aprobados; el original quedó en
`02_migracion_requiere_codigo.original.sql`).

## Qué se hizo
1. Backup `odontosisbd_20261024_193151.dump` (`scripts/backup_db.py`).
2. La migración se probó en una copia restaurada de ese backup (`odontosisbd_mig02_test`, ya eliminada): dos corridas seguidas, sin errores.
3. Se aplicó a `odontosisbd` con postgres. `permisos` conserva sus 339 filas; `odontoclinic_app` conserva SELECT/INSERT/UPDATE/DELETE
   en `diagnosticos`, `odontograma`, `diagnostico_sintoma`, `permisos` y `estado_dental`. Auditoría y `trg_auditoria_inmutable` intactos.

| Tabla | Cambio |
|---|---|
| `diagnosticos` | + `id_consulta_cab` (NOT NULL, FK RESTRICT, índice); − `id_consulta_detalle`; − `sintomas` (ahora `diagnostico_sintoma`) |
| `odontograma` | + `id_consulta_cab` (NOT NULL, FK RESTRICT); − `id_funcionario`; único parcial `ux_odontograma_consulta_vigente WHERE estado <> 'Inactivo'` (la tabla no tiene `activo`) |
| `consultas_cab` | `id_funcionario` NOT NULL (consultas 6 y 17 → funcionario 3) |
| `estado_dental` | `estado` → `activo` NOT NULL DEFAULT true |
| `permisos` | − `ventana` (y el trigger `trg_permisos_resolver_menu`); se identifica por `id_menu` |

Datos borrados (aprobado): diagnósticos 2 y 10 y odontogramas 8 y 9 (más sus 5 detalles).

## Código ajustado (mismo cambio)
- Permisos: `PermisoDao` (JOIN a `menu`), 18 seeds `schema_permisos_*.sql`, `schema_permisos_cajero.sql`; `schema_permisos_id_menu.sql` y `schema_permisos_matriz.sql` quedaron obsoletos/históricos.
- Diagnóstico: `DiagnosticoDao`, `diagnostico_api.py`, template (selector de síntomas con casillas, la consulta viene de la URL), y los cruces de `ConsultaDao`, `RecetaDao`, `OrdenEstudioDao`, `OrdenAnalisisDao`, `JustificativoMedicoDao`, `TratamientoDao`; `SintomaDao.estaEnUso` mira `diagnostico_sintoma`.
- Odontograma: `OdontogramaDao`, `odontograma_api.py` (alta por `id_consulta_cab`, 409 si ya hay uno, `precarga/<consulta>`, `validar-consulta/<consulta>`), template (selector de consulta, `?consulta=`, precarga), tarjeta "Odontograma" en Registrar Consulta.
- Consulta: el funcionario sale de la sesión (`id_funcionario_sesion()`); si no es funcionario → 403 "Solo un funcionario puede registrar consultas."
- Tests: 14 archivos adaptados a `id_menu`, `smoke_cobranzas` (ya no hay trigger), y nuevo `tests/consultorio/smoke_migracion02.py`. CLAUDE.md y tests/README.md actualizados.

## Pruebas
- `smoke_migracion02`: todo OK (Administrador abre las 53 pantallas; Cajero recibe 403 por URL directa en Diagnóstico/Odontograma y su API, y sí abre Ventas; el menú y `smoke_permisos_cajero` también OK).
- Regresión completa de `tests/` (28 scripts smoke + `browser_test` + `browser_auditoria`): todo OK **salvo `smoke_cliente`**, que falla en `seed CARLOS BENÍTEZ`: el cliente 3 fue renombrado a mano a "PRUEBA" en la base (el seed editado; no tiene relación con la migración). `comparar_js_py` no se corrió (no toca nada de lo cambiado).
- No se probó a mano en el navegador la interacción real de las pantallas nuevas (regla 7 de CLAUDE.md): falta que lo hagas vos.
- Hay procesos `run.py` viejos corriendo (PIDs 21832, 3348, 20016, 3148, de antes de esta sesión) con el código anterior: reiniciar el servidor antes de probar.

## DER: falta reflejar
`diagnosticos` (+`id_consulta_cab`, −`id_consulta_detalle`, −`sintomas`, usa `diagnostico_sintoma`), `odontograma` (+`id_consulta_cab`, −`id_funcionario`, único por consulta), `consultas_cab.id_funcionario` NOT NULL, `estado_dental.estado` → `activo`, `permisos` sin `ventana` (por `id_menu`). Y los CUS: funcionario = sesión, odontograma único por consulta con precarga, síntomas como selección múltiple.

## Correcciones pendientes de Consultorio (solo relevado, nada implementado)
Contra la base real y el repo:
| Corrección | Estado |
|---|---|
| Columna `"id_ paciente"` con espacio en `tratamientos` | **Hecha en la base**: la columna es `id_paciente`; ningún código usa el nombre con espacio |
| Valor `'cancelado'` en `tratamientos.estado` | **Hecha en la base**: está en el CHECK `chk_estado_trat` |
| Columna `activo` en `sesiones_tratamiento` | **Hecha en la base** |
| `tratamiento_insumos` → `sesion_insumos` con FK a `sesiones_tratamiento` | **Hecha en la base**: `tratamiento_insumos` ya no existe y `sesion_insumos` tiene FK RESTRICT; ningún código nombra la vieja |
| `CREATE TABLE` de `tipo_procedimiento_medico` y `medicamentos` | **Las tablas existen en la base, pero SIN script**: no hay ningún `CREATE TABLE` de Consultorio en el repo (tampoco de `tratamientos`, `sesiones_tratamiento` ni `sesion_insumos`). Sigue sin hacer: versionarlos |

Limitación: no pude ver `01_migracion_der.sql`, así que no sé si esas correcciones vinieron de ahí; solo verifiqué el estado de la base. Lo que falta (script `CREATE TABLE` idempotente de esas tablas) queda anotado en CLAUDE.md para la migración de Consultorio a Tabler.
