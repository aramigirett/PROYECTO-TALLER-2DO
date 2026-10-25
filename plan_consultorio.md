# Plan: migración del Módulo Consultorio a Tabler con el estándar completo

Rama `consultorio-tabler` (creada desde `main`, que estaba limpio y al día con origin). Relevamiento hecho sobre el código y sobre la base real
`odontosisbd` (columnas, índices, CHECK, conteo de filas). **No se modificó nada.** Este archivo no se commitea.

## 1. Hallazgos que cambian el plan

1. **Ninguna de las 18 pantallas cumple el estándar.** Todas extienden `base.html` (SB Admin 2, jQuery + DataTables); ninguna audita en
   `auditoria_cambios` (0 llamadas a `auditar` en las 19 APIs de `modulo_consultorio`); ninguna tiene Estado / "Mostrar inactivos" / Reactivar.
2. **Tipo Diagnóstico y Síntomas ya tienen `activo` e índice único parcial en la base** (`ux_tipo_diagnostico_descripcion_activo`,
   `ux_sintoma_descripcion_activo`), pero sus DAO siguen haciendo `DELETE FROM`. CLAUDE.md dice "borrado físico, agregar `activo`": está
   desactualizado. Alguien tocó la base sin dejar script en el repo. Falta solo el cambio del DAO y versionar el SQL.
3. **No hay NINGÚN `CREATE TABLE` de Consultorio en el repo** (no solo `tipo_procedimiento_medico` y `medicamentos`): tampoco `consultas_*`,
   `ficha_medica_consulta`, `diagnosticos`, `odontograma*`, `tratamientos`, `sesiones_tratamiento`, `sesion_insumos`, `recetas*`,
   `orden_*`, `justificativo_medico`, `insumos`, `sintoma`, `tipo_*`. Una base nueva no se puede reconstruir. Se resuelve con un script
   idempotente generado desde la base real (etapa 0).
4. **PDF:** solo el Justificativo lo tiene. Receta, Orden de Estudios y Orden de Análisis no.
5. **Tests:** solo Tipo Tratamiento tiene smoke propio; `smoke_migracion02` cubre de forma parcial Consulta, Diagnóstico y Odontograma. Los otros
   14 no tienen ninguno.
6. **Datos reales en la base** (para saber qué se puede probar): consultas 2, ficha 1, diagnósticos 0, odontogramas 0, tratamientos 3, sesiones 3,
   recetas 1, órdenes de estudio 2, órdenes de análisis 0, justificativos 1, `consultas_detalle` 0.
7. `consultas_detalle` (detalle clínico de la consulta: síntoma, pieza dental, tipo de diagnóstico, procedimiento) está vacía y su DAO hace
   `DELETE FROM` físico. Ver pregunta 4.
8. "Historial Médico" aparece en el menú bajo "Módulo Consultorio" pero es un movimiento de Agendamiento: **queda fuera de este plan**.

## 2. Referenciales (8)

Estado de programación: las 8 están **completas** (alta/edición/baja funcionando). Todas: vista SB Admin 2 + jQuery/DataTables, sin Estado ni
Reactivar, sin auditoría, `puede(...)` y `@require_permiso` ya presentes (permisos por `id_menu` OK: las 19 ventanas tienen fila en `menu`).

| Referencial | Tabla | Borrado hoy | `activo` + único parcial en BD | `estaEnUso` | Tests | Falta para el estándar |
|---|---|---|---|---|---|---|
| Tipo Tratamiento | `tipos_tratamiento` (+precio, iva) | Lógico | Sí / sí (sin `UPPER`) | Sí (tratamientos) | `smoke_tipo_tratamiento` | Vista Tabler, Estado/Reactivar, auditoría, protocolo `FOR UPDATE` |
| Tipo Insumo Utilizado | `insumos` (+presentación) | Lógico | Sí / sí | Sí (`sesion_insumos`) | No | Ídem |
| Tipo Procedimiento Médico | `tipo_procedimiento_medico` | Lógico | Sí / sí | Sí (`consultas_detalle`, sesiones) | No | Ídem + `CREATE TABLE` |
| Medicamentos | `medicamentos` (nombre_comercial, presentación) | Lógico | Sí / sí | Sí (`receta_medicamento`) | No | Ídem + `CREATE TABLE` |
| Tipo Estudio | `tipo_estudio` | Lógico | Sí / sí | Sí (`orden_estudios`, no cancelada) | No | Ídem |
| Tipo Análisis | `tipo_analisis` | Lógico | Sí / sí | Sí (`orden_analisis`, no cancelada) | No | Ídem |
| Tipo Diagnóstico | `tipo_diagnostico` (descripción + categoría `tipo_diagnostico`) | **Físico** (DAO) | **Sí / sí** (ya en BD) | Sí (4 refs) | No | DAO a lógico, normalizar a MAYÚSCULAS (hoy no lo hace), Tabler, Estado/Reactivar, auditoría |
| Síntomas | `sintoma` | **Físico** (DAO) | **Sí / sí** (ya en BD) | Sí (`consultas_detalle`, `diagnostico_sintoma`) | No | Ídem |

## 3. Movimientos (10)

Estado de programación: los 10 están **completos** según CLAUDE.md y lo verificado en la base (tablas, CHECK y datos presentes). Ninguno a medias
ni inexistente. Todos en SB Admin 2, sin auditoría, sin tests propios (salvo lo parcial de `smoke_migracion02`).

| Movimiento | Tablas | Template (líneas) | Baja hoy | Estados | PDF | Falta para el estándar |
|---|---|---|---|---|---|---|
| Registrar Consulta | `consultas_cab`, `consultas_detalle` | `consulta-index` (2541, con modales de ficha, diagnóstico, accesos rápidos) | Lógica (`activo`) | programada / en_proceso / finalizada / cancelada | No (no aplica) | Tabler con cabecera en tarjeta + filtros + badges; auditoría; dividir el template gigante; destino de `consultas_detalle` |
| Gestión Ficha Médica | `ficha_medica_consulta` | `ficha-medica-index` (784) | Lógica (`activo`) | — (sigue a la consulta) | No (no aplica) | Tabler, auditoría (Editar SÍ, es excepción del CUS) |
| Gestionar Diagnóstico | `diagnosticos`, `diagnostico_sintoma` | `diagnosticos-medicos-index` (1178) | Lógica (`activo`) | — | No (no aplica) | Tabler, auditoría |
| Gestionar Odontograma | `odontograma`, `odontograma_detalle`, `estado_dental` | `odontograma-index` (1208, 560 de API) | Lógica con **`estado='Inactivo'`**, sin `activo` | Activo / Finalizado / Inactivo | No | **Pendiente CLAUDE.md:** agregar `activo` + único parcial `WHERE activo`; Tabler (el odontograma dibujado se porta con cuidado); auditoría |
| Gestionar Tratamientos | `tratamientos` (código TR) | `tratamiento-index` (521) | **No tiene `activo`**: la baja es `estado='cancelado'` | pendiente / en_seguimiento / finalizado / cancelado | No | Tabler, auditoría |
| Procedimientos e Insumos (Sesiones) | `sesiones_tratamiento`, `sesion_insumos` | `sesion-tratamiento-index` (518, contextual) | Lógica (`activo`, solo la última) | — | No | Tabler, auditoría con cascada a insumos |
| Generar Recetas e Indicaciones | `recetas`, `receta_medicamento` | `receta-index` (537) | Lógica (`activo`) | — | **No existe** | Tabler, auditoría, **PDF nuevo** (ver pregunta 1) |
| Generar Orden de Estudios | `orden_estudios` | `orden-estudio-index` (547) | Por estado (`cancelado`), sin `activo` | pendiente → enviado → en_proceso → completado / cancelado | **No existe** | Tabler, auditoría, **PDF nuevo** |
| Generar Orden de Análisis | `orden_analisis` | `orden-analisis-index` (547, gemela) | Ídem | Ídem | **No existe** | Ídem |
| Generar Justificativo Médico | `justificativo_medico` | `justificativo-medico-index` (455) | Por estado (`anulado`) | activo / anulado | **Sí** (`justificativo_pdf_service.py`, ReportLab) | Tabler, auditoría, rehacer el PDF con el estilo de la factura |

Observaciones: Recetas, Órdenes y Justificativo no usan "Reactivar" (el estándar lo exige para referenciales; en movimientos solo Anular).
Los códigos DX-000N y TR-* son identificadores de movimiento (como el N.º de factura): se mantienen visibles.

## 4. Qué se aplica a cada grupo

- **Referenciales:** el estándar de 6 puntos tal cual (patrón de referencia: Caja / Ítems, con `facturacion-listado.js`, que es genérico y se reutiliza
  sin cambios). Validadores nuevos solo si hay reglas nuevas, siempre en espejo `utils.py` ↔ JS.
- **Movimientos:** patrón de Pedido y Ventas (cabecera en tarjeta, detalle, badges de estado, filtros), "Anular", auditoría estructurada con
  `detalle_cambios()` + `auditar` mostrando nombres y no IDs, entidad sumada a `MODULO_POR_ENTIDAD` / `ETIQUETA_ENTIDAD` / `ENTIDADES_MOVIMIENTO`,
  `@require_permiso` y `puede(...)` conservados, PDF con el patrón `calcular_datos` / `dibujar` / `generar`.
- **Sin cambio de comportamiento de negocio** en nada de lo ya auditado contra su CUS (cascadas, bloqueos, estados, vinculaciones opcionales).

## 5. Etapas propuestas (un commit por etapa, cada una con su smoke y la regresión de `smoke_permisos_app`)

| # | Etapa | Contenido | Tamaño |
|---|---|---|---|
| 0 | Base de datos y andamiaje | Script idempotente que versiona los `CREATE TABLE` de todo Consultorio (generado desde la base real y verificado restaurándolo en una base temporal); `odontograma.activo`; único parcial de Odontograma; `UPPER()` en únicos de referenciales que no lo tienen; entidades de Consultorio en `MODULO_POR_ENTIDAD` / `ETIQUETA_ENTIDAD`; `utils.py` de Consultorio (`auditar`, validadores, `error_interno`) | M |
| 1 | 6 referenciales que ya son lógicos | Tipo Tratamiento, Tipo Insumo, Tipo Procedimiento, Medicamentos, Tipo Estudio, Tipo Análisis: vista Tabler, Estado, Mostrar inactivos, Reactivar, auditoría, protocolo transaccional de `estaEnUso`. Un smoke parametrizado + browser test | L |
| 2 | Tipo Diagnóstico y Síntomas | De físico a lógico en el DAO, mayúsculas, el resto igual a la etapa 1; `estaEnUso` completo (diagnósticos, `diagnostico_sintoma`, `consultas_detalle`) | S |
| 3 | Registrar Consulta + Ficha Médica | Raíz de la cadena. Consulta en Tabler (listado, cabecera en tarjeta, accesos rápidos), modal de ficha embebido, pantalla de Fichas, auditoría de ambas. Incluye partir `consulta-index` en parciales | XL |
| 4 | Diagnóstico + Odontograma | Diagnóstico con síntomas múltiples; Odontograma con `activo`, precarga y el dibujado portado | L |
| 5 | Tratamientos + Sesiones e Insumos | Los dos juntos (la sesión cuelga del tratamiento), incluyendo "Finalizar" y la conexión con la Venta de Tratamiento | L |
| 6 | Recetas + Órdenes de Estudio y Análisis | Tres pantallas casi gemelas; PDF de cada una si se aprueba | L |
| 7 | Justificativo + cierre | Justificativo en Tabler con PDF estilo factura; smoke de permisos por rol para las 18 ventanas; actualizar CLAUDE.md y `tests/README.md`; limpiar carpetas duplicadas y `base.html` ya sin usos de Consultorio | M |

Orden: referenciales primero porque los combos de los movimientos dependen de ellos (solo activos) y porque fijan el patrón visual y de auditoría;
después los movimientos siguiendo la dependencia Consulta → Diagnóstico/Odontograma → Tratamiento → Sesiones → Recetas/Órdenes → Justificativo.
Riesgo principal: etapas 3 y 4 (templates de 2.500 y 1.200 líneas con mucha lógica en JS/jQuery). Si se prefiere, la 3 se divide en dos commits.

## 6. Decisiones de negocio pendientes

1. **PDF de Receta, Orden de Estudios y Orden de Análisis:** ¿se programan? (Recomiendo sí: son documentos que el paciente se lleva, y el patrón ya existe.)
2. **Auditoría de datos clínicos:** ¿el detalle de `auditoria_cambios` puede incluir contenido clínico (diagnóstico, indicaciones, observaciones) o solo
   quién, cuándo, paciente, número de documento y los cambios de estado? (Recomiendo lo segundo: la pantalla de auditoría ve el Administrador, que no es personal clínico.)
3. **Reactivar movimientos:** ¿una consulta, receta, orden o justificativo anulado puede reactivarse, o la anulación es definitiva? (Recomiendo definitiva; solo Reactivar en referenciales.)
4. **Detalle de consulta (`consultas_detalle`):** tabla vacía con pantalla de carga clínica por renglón (síntoma / pieza / procedimiento). ¿Sigue vigente en el análisis o quedó superada por Diagnóstico, Tratamiento y Sesiones? Si está superada, se retira.
5. **Odontograma `Finalizado`:** ¿se conserva ese estado además de anulado (Activo / Finalizado), o alcanza con Activo / Anulado?
