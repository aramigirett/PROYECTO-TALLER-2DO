# Etapa 5 — Gestionar Tratamientos y Sesiones (Procedimientos e Insumos Utilizados)

## Relevamiento (código y base reales)

**Tablas.** `tratamientos` (consulta NOT NULL, `id_diagnostico` NULL, paciente/médico/consultorio heredados, tipo, descripción, fecha, `estado` CHECK pendiente/en_seguimiento/finalizado/cancelado; sin `activo`; `codigo` y `id_funcionario`, `id_tipo_diagnostico` sin uso). `sesiones_tratamiento` (`id_tratamiento`, `numero_sesion`, **un solo** `id_tipo_procedimiento`, fecha, descripción, observaciones, `proxima_cita`, `activo`; único parcial `(id_tratamiento, numero_sesion) WHERE activo`). `sesion_insumos` (`id_sesion`, `id_insumo`, cantidad > 0, `activo`; **sin único** por sesión+insumo). Datos reales: 3 tratamientos (2 finalizados, 1 pendiente), 3 sesiones.

**1. Facturación (Venta de Tratamiento).** Lee de `tratamientos`: `id_tratamiento`, `id_paciente`, `estado` (`<> 'cancelado'`), `fecha_tratamiento`, `codigo` (solo lo muestra) y `id_tipo_tratamiento` → precio/IVA de `tipos_tratamiento`. Excluye los que ya tienen venta EMITIDA y toma `FOR UPDATE OF t` (mismo bloqueo que `deleteTratamiento`). `venta_det.id_tratamiento` es FK RESTRICT. **No lee** estados intermedios (un finalizado se factura igual), ni sesiones, ni consulta. Para no romperla: mantener `estado='cancelado'` como anulación, no renombrar columnas ni borrar filas, conservar el `FOR UPDATE` y el bloqueo "FACTURADO". Regresión completa de Facturación al final de cada commit.

**2. Ciclo de estados hoy.** `pendiente` (alta) → `en_seguimiento` (lo pone automáticamente la 1.ª sesión) → `finalizado` (`PUT /tratamientos/<id>/finalizar`, permiso `estado`, **sin chequear médico ni consulta**; bloqueado si está pendiente) ; `cancelado` = anular (`DELETE`, bloqueado con sesiones activas o venta EMITIDA). No hay vuelta atrás.

**3. Sesiones en consultas posteriores.** Hoy la sesión **no tiene `id_consulta_cab`** y cuelga solo del tratamiento: se puede registrar en cualquier momento, sin consulta, sin chequear médico ni estado de la consulta que creó el tratamiento (que puede estar finalizada). Es decir, el multi-visita ya "funciona" pero sin ningún control clínico (cualquiera con `sesiontratamiento nuevo` carga sesiones). Anular una consulta ya se bloquea con tratamientos, pero una consulta **finalizada** no impide cargar sesiones después.

**4. Contradicciones con las reglas.**
- Sesión con **un** solo procedimiento: el análisis pide "los procedimientos realizados" (varios). Hoy `sesiones_tratamiento.id_tipo_procedimiento` es único.
- `guardarSesion` no valida médico, consulta ni estado de la consulta; no toma FOR SHARE sobre tipo de procedimiento ni insumos (permite inactivos); permite el mismo insumo repetido.
- `guardarTratamiento` no toma `FOR UPDATE` sobre la consulta ni `FOR SHARE` sobre el tipo (permite tipo inactivo), no revalida contra carrera, acepta cualquier fecha obligatoria desde el cliente (no hay propuesta) y no verifica que el actor sea el médico de la consulta.
- `finalizar`/`anular` sin chequear médico ni consulta; lecturas sin privacidad (`GET /tratamientos` y `/<id>` con `require_login` exponen todo a cualquier usuario).
- Anulación de tratamiento = `estado='cancelado'` (ya definitiva, no hay reactivar) → OK con la regla.
- Sin auditoría en ninguno de los dos; vistas SB Admin 2 + jQuery (521 y 518 líneas); sesiones es ventana contextual (`en_menu False`).
- `numero_sesion` correlativo reutiliza el número tras anular la última (OK, único parcial).

## Decisiones de negocio a aprobar
1. **Cada sesión se registra dentro de una consulta** (nueva columna `sesiones_tratamiento.id_consulta_cab` NOT NULL, FK RESTRICT): así un tratamiento de varias visitas recibe sesiones en consultas posteriores del mismo paciente. Regla: la consulta debe ser `programada`/`en_proceso` y activa, del **mismo paciente y el mismo médico** que el tratamiento, revalidada con la consulta `FOR UPDATE`. Las 3 sesiones existentes se asignan a la consulta del tratamiento (backfill).
2. **Varios procedimientos por sesión:** nueva tabla `sesion_procedimientos` (`id_sesion`, `id_tipo_procedimiento`, `observacion` opcional, `activo`, único parcial por sesión+tipo, mínimo 1) y se retira `sesiones_tratamiento.id_tipo_procedimiento` (migrando las 3 filas). Alternativa: dejar un solo procedimiento (decime si preferís).
3. **Insumos:** opcionales (0 o más) o mínimo 1 como hoy? Propongo **mínimo 0** (hay sesiones sin insumos); sin repetidos (único parcial sesión+insumo activo), cantidad entera 1–999.
4. **Quién:** solo el médico de la consulta crea/anula tratamientos y sesiones; **finalizar** tratamiento también solo su médico (el de la consulta que lo creó); Recepción sin acceso; Administrador solo lectura. Tratamiento se crea con la consulta `programada`/`en_proceso`; **finalizar no exige consulta abierta del tratamiento** pero sí que el médico sea el del tratamiento.
5. **Anular tratamiento** = definitivo (`cancelado`), bloqueado con sesiones activas o venta EMITIDA (se mantiene). **Anular sesión**: solo la última activa y solo desde una consulta abierta (y solo el médico); cascada a procedimientos e insumos; si queda sin sesiones y el tratamiento estaba `en_seguimiento` vuelve a `pendiente` (propuesta; hoy no vuelve).
6. **Fecha del tratamiento:** propuesta = hoy, editable, no futura. Fecha de la sesión: fija = hoy (servidor); `proxima_cita` opcional, no anterior a hoy.
7. **Privacidad:** un médico ve solo tratamientos/sesiones de sus consultas; el Administrador ve todo; lecturas con `require_algun_permiso(tratamiento ver)`; sin lecturas abiertas con `require_login` (el combo de Recetas/Órdenes usa `/tratamientos/consulta/<id>` y ya pasa por `acceso_consulta`).
8. **Auditoría sin contenido clínico:** ALTA/BAJA de `tratamientos` y `sesiones_tratamiento` con N.º de consulta, paciente, tipo; sin descripciones ni observaciones; finalizar = `MODIFICACION` Estado `En seguimiento → Finalizado`.
9. **Referenciales** (tipo de tratamiento, procedimiento, insumo): `FOR SHARE` ordenado y rechazo de inactivos con mensaje claro (`campo`). `TipoTratamientoDao`, `TipoProcedimientoMedicoDao`, `TipoInsumoDao.estaEnUso` ya cuentan lo asociado: se actualizan a `sesion_procedimientos`.
10. **Tratamiento vinculado a diagnóstico:** vigente (`activo`) y de la misma consulta, validado con `FOR SHARE` sobre el diagnóstico.

## Archivos y commits
**Commit 1 — base + backend**
- `app/dao/referenciales_consultorio/schema_consultorio_etapa5.sql` (idempotente): `sesiones_tratamiento.id_consulta_cab` (backfill), `sesion_procedimientos` (+ migración, único parcial), único parcial `sesion_insumos(id_sesion, id_insumo) WHERE activo`, CHECK cantidad ≤ 999, FK RESTRICT; actualizar `schema_consultorio_base.sql`; permisos (`schema_permisos_consultorio_roles.sql`: `sesiontratamiento` solo Médico; `tratamiento estado` solo Médico).
- `TratamientoDao.py` y `SesionTratamientoDao.py` reescritos (bloqueos, validaciones en transacción, privacidad por médico, listado paginado, `finalizar`).
- `tratamiento_api.py` / `sesion_tratamiento_api.py` reescritos (auditoría estructurada, errores con `campo`); `acceso_consulta`; `MODULO_POR_ENTIDAD`/etiquetas (+ `sesion_procedimientos`); validadores en `validadores_clinicos.py` + `consultorio-validadores.js` (+ espejo en `comparar_ficha_js_py.py`).
- Actualizar `estaEnUso()` de procedimiento / insumo; `ConsultaDao` (contadores y bloqueos).
- Tests: `smoke_tratamiento.py`, `smoke_sesion_tratamiento.py` (concurrencia, tipos inactivos, otra consulta / otro médico, consulta finalizada, multi-visita, privacidad, auditoría sin clínica, Facturación intacta), ajustar `smoke_esquema_consultorio` y fixtures. Regresión completa incl. Facturación.

**Commit 2 — vistas Tabler**
- `tratamiento-index.html` (listado + modo `?consulta=<id>`: nuevo, ver con sus sesiones, finalizar, anular) y `sesion-tratamiento-index.html` (`?tratamiento=<id>&consulta=<id>`: sesiones del tratamiento, nueva sesión con procedimientos múltiples e insumos con cantidad, anular última, "Volver a la consulta"/"Volver al tratamiento"); rutas con `es_medico`; borrar las vistas viejas.
- Hub de la consulta: tarjeta Tratamientos y sesiones (ya existe) apuntando con `?consulta=`.
- Tests: `smoke_trat_vistas.py` + `browser_tratamiento.py` (Edge headless); CLAUDE.md y tests/README.md; lista de pruebas por usuario (Oscar, Rocío, Administrador) con una consulta en proceso.

**No se commitea:** `plan_etapa5.md`.
