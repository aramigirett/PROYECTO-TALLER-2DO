# Historial de Consultorio

> Leer al tocar cualquier pantalla, DAO o tabla de Consultorio.
> Movido tal cual desde `CLAUDE.md` (sin cambios de contenido) al reorganizarlo. La guía compacta es `CLAUDE.md`.

## Estado real del Módulo Consultorio (actualizado — COMPLETO; el estado FINAL, tras la migración a Tabler, está en "Estado final de Consultorio" más abajo)

Análisis confirmado (10 movimientos + 8 referenciales documentados con el
profesor). Decisión clave resuelta: **Registrar Consulta parte de una Cita
ya reservada en Agendamiento** (estado "Confirmado"), no es un registro
independiente.

### Registrar Consulta — reconstruido para partir de la Cita
- `agenda_cabecera.id_consultorio` (NOT NULL, FK a `consultorio`, RESTRICT):
  el Consultorio ahora se asigna al crear la Agenda del médico, para poder
  heredarse automáticamente en toda la cadena Agenda→Cita→Consulta (esto
  resolvió un hueco del análisis: el CUS asumía que Consultorio se precargaba
  solo, pero nunca se había definido dónde se capturaba por primera vez).
- `consultas_cab.id_cita`: NOT NULL, FK a `cita_detalle.id_cita_detalle`,
  UNIQUE (una cita = una sola consulta).
- Al guardar una Consulta: el backend valida que la cita exista, esté
  "Confirmado", y no tenga consulta previa — todo en una transacción. Paciente
  /Médico/Consultorio/Fecha/Hora se derivan de la cita (el backend nunca
  confía en lo que mande el formulario para esos campos, evita falsificación).
  Al guardar, la cita pasa a "Realizado" automáticamente.
- Campos editables en la Consulta una vez vinculada a la Cita: Fecha y Hora
  son de solo lectura; Duración y Estado (el estado propio de la Consulta:
  programada/en proceso/finalizada — NO el estado de la Cita) sí son editables.
- ANULAR (baja lógica) bloquea con "EN_USO" si la consulta ya tiene Ficha
  Médica, Diagnóstico o Tratamiento asociado.
- Pendiente marcado, no resuelto: `PacienteDao.deletePaciente` es DELETE
  físico y `cita_cabecera.id_paciente` es CASCADE — borrar un paciente con
  citas confirmadas perdería ese historial en cascada. No se tocó (pertenece
  a entidades de Agendamiento ya cerrado), queda anotado para cuando se
  revise Paciente/Médico a fondo.

### Otros hallazgos ya resueltos
- Ficha Médica: **no había duplicación real** — el modal embebido en
  Consulta (carga clínica de 1 ficha) y la pantalla standalone
  `ficha-medica-index` (listado/auditoría transversal con estadísticas) son
  dos usos legítimos y distintos del mismo DAO. No se tocó nada.
- Renombrado interno: la carpeta que servía `TipoDiagnosticoDao` tenía
  nombres internos (blueprint, endpoint, template) que decían literalmente
  "diagnostico", chocando con el módulo real de Diagnósticos Médicos. Se
  renombró todo a `tipodiagnostico`/`tipo-diagnostico-index` — cero cambio
  de comportamiento, solo claridad. La URL del API JSON
  (`/api/v1/diagnosticos...`) NO se tocó a propósito, porque también la
  consume la pantalla de Diagnósticos Médicos.
- `Sintoma` y `TipoDiagnostico`: quedan con DELETE físico (catálogos base),
  pero ahora validan uso antes de borrar (`estaEnUso()` → 409 "EN_USO"),
  mismo patrón que Agendamiento. Se agregó además una FK real
  `consultas_detalle.id_sintoma → sintoma(id_sintoma) ON DELETE RESTRICT`
  (antes solo protegido a nivel de aplicación).

### Odontograma — corregido (3 problemas)
- Estaba mal ubicado en `modulo_agendamiento/` — movido a
  `modulo_consultorio/odontograma/` (solo la carpeta física; blueprint,
  endpoint y prefijo de URL quedaron iguales a propósito, para no romper un
  botón "Ver Odontograma" con URL hardcodeada en
  `diagnosticos-medicos-index.html`).
- ANULAR era DELETE físico pese a que ya existía `cambiarEstadoOdontograma()`
  (baja lógica, con columna `estado` y CHECK Activo/Finalizado/Inactivo) sin
  usar. Corregido para usar baja lógica, y se agregó el filtro
  `estado <> 'Inactivo'` en los listados (si no, la baja lógica se vería
  como que "Eliminar" no hace nada).
- Bug real corregido: `getOdontogramasByPaciente()` usaba una columna
  inexistente (`p.ci` en vez de `p.cedula_entidad`) — tiraba error de SQL en
  cualquier llamada real a `GET /api/v1/odontogramas/paciente/<id>`.
- Pendiente igual que Consulta: `odontograma.id_paciente` es CASCADE, mismo
  riesgo latente que `cita_cabecera.id_paciente` (no resuelto, anotado).

### Las 6 referenciales de Consultorio — todas programadas y probadas
Tipo Tratamiento, Tipo Insumo Utilizado, Tipo Procedimiento Médico,
Medicamentos, Tipo Estudio, Tipo Análisis. Todas usan **baja lógica**
(`activo`), a diferencia de las referenciales de Agendamiento — decisión
confirmada en cada CUS original, no es inconsistencia.

**Tipo Tratamiento: precio (rama `consultorio`).** `tipos_tratamiento.precio NUMERIC(12,0) NOT NULL` con
`CHECK (precio > 0)` (guaraníes, sin decimales; lo usa la Venta de Tratamiento de Facturación). Migración idempotente:
`app/dao/referenciales_consultorio/tipo_tratamiento/schema_tipo_tratamiento_precio.sql` (columna nullable → datos →
NOT NULL y CHECK; si quedara una fila sin precio corta con un mensaje que la nombra). Datos iniciales: 11 tratamientos
odontológicos (LIMPIEZA DENTAL (PROFILAXIS) … IMPLANTE DENTAL).
- **`PRUEBA` (registro de prueba) se anuló por la migración y quedó con precio 1**, aunque tiene 2 tratamientos asociados
  (7 y 9). Es una excepción deliberada: la baja desde la pantalla lo habría bloqueado por estar en uso. Los
  tratamientos siguen listándose (sus `JOIN` no filtran por `activo`); el tipo ya no aparece en el combo de altas.
- API: `precio` obligatorio en POST/PUT con `validar_precio` (compartido con Ítems, `app/rutas/modulo_facturacion/utils.py`)
  y **un único mensaje** para cualquier precio inválido: "El precio debe ser un número entero mayor a 0." (`campo: precio`).
  La vista (todavía SB Admin 2) valida con `FacturacionValidadores.precio` (el mismo JS compartido) y muestra el precio como
  "Gs. 200.000". Esta API sigue normalizando con `strip().upper()` (no colapsa espacios internos, a diferencia de Facturación).
- **IVA (rama `consultorio`)**, igual que en `items`: `tipos_tratamiento.iva SMALLINT NOT NULL DEFAULT 10` con
  `CHECK (iva IN (0, 5, 10))` (0 = exenta). Migración idempotente aparte:
  `app/dao/referenciales_consultorio/tipo_tratamiento/schema_tipo_tratamiento_iva.sql` (los existentes, incluido
  `PRUEBA`, quedan en 10; el orden respecto de la migración de precio es indistinto; volver a correrla no pisa un IVA
  ya editado). La API exige `iva` en POST/PUT con `validar_iva` (compartido con Ítems; mensaje "El IVA debe ser Exenta
  (0), 5% o 10%.", `campo: iva`; el precio se valida primero). La vista tiene el combo IVA (10% por defecto, 5%,
  Exenta) y la columna IVA, y valida con `FacturacionValidadores.iva`.
- Los lectores de `tipos_tratamiento` (Gestionar Tratamientos y el combo de `tratamiento-index.html`) solo usan `id` y
  `descripcion`: no se ven afectados.

**Corrección importante aplicada después de programarlas:** el campo
`codigo` que pedían los CUS originales (Alta con Código + Descripción) fue
sacado por decisión posterior de Ara — **ya no existe** en ninguna de las 6.
Quedan solo con su ID interno autonumérico como identificador, igual que
las referenciales de Agendamiento (Especialidad/Cargo). La validación de
duplicados pasa a hacerse por `descripcion` (o `nombre_comercial` en el
caso de Medicamentos, que nunca tuvo campo Descripción). Se agregó también
un índice único parcial en `insumos.descripcion`, que antes no lo tenía
(solo `codigo` estaba protegido).

⚠️ **Pendiente, no de código:** los CUS documentados en el Word de la tesis
todavía dicen "el encargado de consultorio ingresa el Código y la
Descripción" — hay que corregir esos 6 documentos para que coincidan con
esta decisión, si no queda la misma inconsistencia análisis-vs-código que
venimos evitando, pero al revés.

Dependencias pendientes documentadas en cada DAO (`estaEnUso()` devuelve
`False` por ahora, sin fingir una validación imposible):
- Tipo Insumo Utilizado y Tipo Procedimiento Médico: dependen de
  `sesion_insumos`/`sesiones_tratamiento` (parte de "Gestionar Procedimientos
  e Insumos Utilizados", sin programar). Tipo Procedimiento Médico sí valida
  parcialmente hoy contra `consultas_detalle.id_tipo_procedimiento` (FK real
  ya conectada).
- Medicamentos: depende de `receta_medicamento` ("Generar Recetas e
  Indicaciones", sin programar).
- Tipo Estudio: depende de `orden_estudios` ("Generar Orden de Estudios",
  sin programar).
- Tipo Análisis: depende de `orden_analisis` ("Generar Orden de Análisis",
  sin programar).

### Movimientos grandes — estado real (actualizado)

**5 movimientos auditados y cerrados de punta a punta:** Registrar Consulta,
Gestionar Diagnóstico, Gestión Ficha Médica, Gestionar Odontograma,
Gestionar Tratamientos. Cada uno respeta ahora su CUS real (no lo que se
asumía por "parecido" a otro módulo):

- **Registrar Consulta**: reconstruido para partir de una Cita Confirmada
  (ver sección de arriba). Editable solo Duración/Estado una vez vinculada.
- **Gestionar Diagnóstico**: solo Ver/Anular (se sacó un botón "Modificar"
  que no correspondía a su CUS). Anular ahora es baja lógica real
  (`activo`, antes DELETE físico), con las 2 validaciones que pide el CUS
  (bloquea si tiene Tratamiento asociado, bloquea si la consulta está
  "finalizada"). Bug aparte corregido: `generarCodigo()` (DX-000N) contaba
  mal por año contra un código único global — corregido para no chocar.
- **Gestión Ficha Médica**: Ver/Editar/Anular (Editar SÍ es legítimo acá —
  corrige la misma ficha mientras la consulta sigue abierta, no crea una
  nueva; distinto criterio a Diagnóstico/Tratamiento a propósito). No tenía
  ningún botón Anular conectado — se agregó, con baja lógica real y bloqueo
  si la consulta está "finalizada".
- **Gestionar Odontograma**: Ver/Anular. Reubicado a `modulo_consultorio/`
  (estaba mal puesto en Agendamiento). Baja lógica real (antes DELETE
  físico pese a tener el mecanismo ya construido). Bug de columna
  inexistente (`p.ci`→`p.cedula_entidad`) corregido.
- **Gestionar Tratamientos**: Ver/Anular. Construido de cero ya alineado al
  CUS desde el arranque (parte de Consulta activa, vinculación opcional a
  Diagnóstico, hereda Paciente/Médico/Consultorio, estados
  `pendiente→en_seguimiento→finalizado`+`cancelado`).
- **Generar Recetas e Indicaciones**: Ver/Anular. Cuelga directo de
  Consulta (no de Tratamiento), con vinculación OPCIONAL a Diagnóstico
  y/o Tratamiento de esa misma consulta. Cabecera `recetas`
  (indicaciones_generales) + detalle `receta_medicamento` (dosis,
  frecuencia, duración por medicamento — mínimo 1). Anular bloqueado si
  la consulta está "finalizada" (sin regla de "solo la última", a
  diferencia de Sesiones). Con entrada propia en sidebar (mismo criterio
  que Tratamiento) + 4ª tarjeta de Acción Rápida en Consulta.
  Dependencia cruzada conectada: `MedicamentoDao.estaEnUso()` dejó de ser
  un stub que devolvía `False` fijo — ahora valida contra
  `receta_medicamento` de verdad.
- **Generar Orden de Estudios**: Ver/Anular. Cuelga directo de Consulta,
  vinculación OPCIONAL a Diagnóstico/Tratamiento (igual que Recetas).
  Tabla ÚNICA `orden_estudios` (un solo Tipo de Estudio por orden, sin
  cabecera+detalle) — **sin columna `activo`**, el propio `estado`
  (CHECK: pendiente/enviado/en_proceso/completado/cancelado) hace de baja
  lógica (`cancelado` = anulado). Dos acciones desde la misma pantalla:
  "Actualizar Estado" (avanza UN paso a la vez en la secuencia fija —
  el sistema calcula el siguiente estado, el usuario no elige a cuál
  saltar) y "Anular" (bloqueado si ya está completado/cancelado). Con
  entrada propia en sidebar + 5ª tarjeta de Acción Rápida en Consulta.
  Dependencia cruzada conectada: `TipoEstudioDao.estaEnUso()` valida
  contra `orden_estudios` con `estado <> 'cancelado'`.

**✅ MÓDULO CONSULTORIO COMPLETO — 10 movimientos + 8 referenciales,
todos auditados contra su CUS real y probados de punta a punta:**

Movimientos: Registrar Consulta, Gestionar Diagnóstico, Gestión Ficha
Médica, Gestionar Odontograma, Gestionar Tratamientos, Gestionar
Procedimientos e Insumos Utilizados, Generar Recetas e Indicaciones,
Generar Orden de Estudios, Generar Orden de Análisis, Generar
Justificativo Médico.

Referenciales: Tipo Tratamiento, Tipo Insumo Utilizado, Tipo
Procedimiento Médico, Medicamentos, Tipo Estudio, Tipo Análisis (todas
baja lógica), Especialidad/Día/Turno/Cargo/Consultorio/Disponibilidad
Horaria (de Agendamiento, DELETE físico — ver sección de Agendamiento).

- **Gestionar Procedimientos e Insumos Utilizados**: cuelga de un
  Tratamiento (sin entrada propia en sidebar, acceso siempre contextual).
  Tablas `sesiones_tratamiento`+`sesion_insumos`. `numero_sesion`
  correlativo con único parcial. Primera sesión pasa el tratamiento a
  `en_seguimiento`. Solo se puede anular la última sesión activa, con
  cascada a sus insumos. "Finalizar Tratamiento" vive acá (no en
  Gestionar Tratamientos).
- **Generar Recetas e Indicaciones**: cuelga de Consulta, vinculación
  opcional a Diagnóstico y/o Tratamiento. Cabecera `recetas` + detalle
  `receta_medicamento` (mínimo 1 medicamento). Con entrada propia en
  sidebar + tarjeta de Acción Rápida.
- **Generar Orden de Estudios / Generar Orden de Análisis**: idénticos
  estructuralmente entre sí (solo cambia el catálogo). Tabla única, sin
  `activo` — el propio `estado` (pendiente/enviado/en_proceso/completado/
  cancelado) hace de baja lógica. Dos acciones: "Actualizar Estado"
  (avanza UN paso, secuencial estricto — el sistema calcula el siguiente,
  no se puede saltar) y "Anular" (bloqueado si completado/cancelado).
- **Generar Justificativo Médico**: cuelga de Consulta, vinculación
  opcional SOLO a Diagnóstico (sin Tratamiento, a diferencia de
  Recetas/Órdenes). Campos: Días de Reposo (>0) + Recomendaciones.
  Estados simples `activo`/`anulado` (no la cadena de 4 pasos de las
  Órdenes). **Genera PDF al vuelo con ReportLab** (instalado, sin
  dependencias de sistema — funciona limpio en Windows), sin persistir
  archivo en el servidor — se regenera desde los datos de la BD cada vez.
  Un justificativo anulado sigue siendo descargable, pero con marca
  "ANULADO" visible en rojo (no se bloquea la descarga, sirve de
  respaldo/auditoría). Servicio en `app/Services/justificativo_pdf_service.py`
  — pensado para reutilizar el mismo patrón si en el futuro se agrega PDF
  a Recetas/Órdenes.

**Dependencias cruzadas conectadas a lo largo del módulo** (todos los
`estaEnUso()` que quedaban documentados como "pendiente, esperando a que
exista X" ya fueron conectados apenas esa tabla se construyó):
`TratamientoDao.deleteTratamiento()` bloquea si hay sesiones activas;
`TipoInsumoDao.estaEnUso()` (no existía — bug real, cualquier insumo se
podía anular en uso); `TipoProcedimientoMedicoDao.estaEnUso()` (sumó
`sesiones_tratamiento`); `MedicamentoDao.estaEnUso()` (contra
`receta_medicamento`); `TipoEstudioDao`/`TipoAnalisisDao.estaEnUso()`
(contra sus respectivas órdenes, con `estado <> 'cancelado'`). Bug de
seguridad aparte corregido: `tipo_insumo_api.py` chequeaba `if resultado:`
en vez de comparar contra `"EN_USO"` (permitía anular en uso sin
bloquear, por ser cualquier string "truthy" en Python).

**Mejora de UX aplicada a todo el módulo:** los mensajes de éxito/error
usan datos descriptivos reales (código, fecha+paciente, descripción,
etc.), nunca IDs crudos.

## Migración 02 (aplicada, rama `migracion-02`)
Script: `migraciones/02_migracion_requiere_codigo.sql` (idempotente, una transacción, se corre con postgres después del
backup; el original sin cambios queda en `02_migracion_requiere_codigo.original.sql`). Probada primero sobre una copia
restaurada del backup (dos corridas), y recién después aplicada a `odontosisbd`. El código se ajustó en el mismo cambio.
- **`diagnosticos`**: `id_consulta_detalle` → **`id_consulta_cab`** (NOT NULL, FK RESTRICT); se quitó `sintomas` (texto libre).
  Los síntomas se guardan en **`diagnostico_sintoma`** (selección múltiple desde el referencial Síntomas, opcional): alta
  transaccional, `GET` devuelve `sintomas: [{id_sintoma, descripcion_sintoma}]`. Paciente y médico **se derivan de la consulta**
  (el body se ignora); la consulta tiene que estar activa y no finalizada. El diagnóstico se registra solo desde Registrar
  Consulta (la pantalla exige `?consulta=`). `SintomaDao.estaEnUso` ahora también mira `diagnostico_sintoma`. Los DAO de
  Receta, Órdenes, Justificativo, Tratamiento y Consulta validan el diagnóstico por `diagnosticos.id_consulta_cab` (antes por
  `consultas_detalle`, que estaba vacía: hoy esos cruces andaban en falso).
- **`odontograma`**: `id_funcionario` → **`id_consulta_cab`** (NOT NULL, FK RESTRICT). **Uno por consulta**: índice único
  parcial `ux_odontograma_consulta_vigente (id_consulta_cab) WHERE estado <> 'Inactivo'` (la tabla no tiene `activo`: su baja
  lógica es `estado = 'Inactivo'`). Paciente y médico salen de la consulta. El **vigente del paciente es el de su última
  consulta** (`getOdontogramaVigentePaciente`); al crear uno nuevo la pantalla lo **precarga** con ese estado
  (`GET /api/v1/odontogramas/precarga/<id_consulta>`). Entrada desde Registrar Consulta: tarjeta "Odontograma"
  (`odontograma-index?consulta=<id>`). `GET /odontogramas/validar-paciente` pasó a `validar-consulta/<id>`.
- **`consultas_cab.id_funcionario` obligatorio**: sale SIEMPRE de la sesión (`id_funcionario_sesion()` en
  `permisos_contexto.py`); si el usuario no es funcionario (p. ej. un Médico) → 403 "Solo un funcionario puede registrar
  consultas." La consulta la registra Recepción desde la cita; el médico es un dato de la consulta.
- **`estado_dental.estado` → `activo`** (NOT NULL DEFAULT true; el JSON de `/estados-dentales` ahora trae `activo`).
- **`permisos`**: sin `ventana`; ver "Modelo de permisos".
- **Datos migrados:** consultas 6 y 17 → funcionario 3; los diagnósticos 2 y 10 y los odontogramas 8 y 9 (datos de prueba sin
  consulta del mismo médico) se **borraron con sus dependientes** (5 detalles de odontograma). `permisos` conserva sus 339 filas.
- `odontoclinic_app` conserva todos sus privilegios (verificado: SELECT/INSERT/UPDATE/DELETE en las tablas tocadas y en
  `diagnostico_sintoma`). La auditoría y `trg_auditoria_inmutable` no se tocaron.
- Test: `tests/consultorio/smoke_migracion02.py` (esquema, `PermisoDao`, Administrador/Cajero y URL directa, consulta con/sin
  funcionario, diagnóstico con síntomas, odontograma único por consulta con precarga, consulta finalizada).
- ⚠️ **Falta reflejar en el DER:** `diagnosticos` (+`id_consulta_cab`, −`id_consulta_detalle`, −`sintomas`; usa `diagnostico_sintoma`),
  `odontograma` (+`id_consulta_cab`, −`id_funcionario`, único por consulta), `consultas_cab.id_funcionario` NOT NULL,
  `estado_dental.estado` → `activo`, `permisos` sin `ventana` (identificada por `id_menu`). Y el análisis (CUS): Registrar
  Consulta/Diagnóstico/Odontograma deben decir que el funcionario es la sesión, que el odontograma es uno por consulta con
  precarga del anterior y que los síntomas del diagnóstico son una selección múltiple.
- **Odontograma: igualarlo al estándar en la migración de Consultorio a Tabler.** Hoy NO tiene columna `activo`: su baja lógica es
  `estado = 'Inactivo'` (CHECK Activo/Finalizado/Inactivo) y el único parcial es `ux_odontograma_consulta_vigente ... WHERE
  estado <> 'Inactivo'`. Al migrarlo hay que agregar `activo BOOLEAN NOT NULL DEFAULT true` e índice único parcial
  `WHERE activo = true` (conservando `estado` para Activo/Finalizado), y actualizar los filtros `estado <> 'Inactivo'` de
  `OdontogramaDao` (listados, `existeOdontogramaConsulta`, `getOdontogramaVigentePaciente`, alta) y el test `smoke_migracion02`.
- **Pendientes de Consultorio para la migración a Tabler** (relevados contra la base, no tienen script en el repo):
  la base YA tiene `tratamientos.id_paciente` (sin espacio), `'cancelado'` en el CHECK de `tratamientos.estado`,
  `sesiones_tratamiento.activo`, `sesion_insumos` con FK a `sesiones_tratamiento` (`tratamiento_insumos` ya no existe) y las
  tablas `tipo_procedimiento_medico` y `medicamentos`. Lo que SIGUE sin hacer: **versionar el `CREATE TABLE`** de
  `tipo_procedimiento_medico` y `medicamentos` (no hay ningún `CREATE TABLE` de Consultorio en el repo: ni de esas ni de
  `sesiones_tratamiento`/`sesion_insumos`/`tratamientos`) y dejar un script idempotente que reproduzca esas correcciones en una
  base nueva. Se hace junto con la migración de Consultorio a Tabler.

## Migración de Consultorio a Tabler (CERRADA, rama `consultorio-tabler`)
Plan completo en `plan_consultorio.md` (sin versionar). Etapas 0 a 7, un commit por etapa. **Decisiones de negocio confirmadas:**
- **PDF** de Receta, Orden de Estudios y Orden de Análisis (estilo factura/Justificativo).
- **Auditoría de Consultorio sin contenido clínico:** solo quién, cuándo, paciente, N.º de documento y cambios de estado (nunca diagnósticos,
  síntomas, indicaciones, medicamentos, observaciones). Los referenciales sí auditan su descripción.
- **Anulación definitiva** en todos los movimientos de Consultorio; solo los referenciales se reactivan.
- **Odontograma: solo Activo y Anulado** (sin "Finalizado"); lo que impide modificarlo es que la consulta esté finalizada.
- **Movimientos clínicos** (Ficha, Diagnóstico, Odontograma, Tratamiento, Sesiones, Receta, Órdenes, Justificativo): rol Médico/Odontólogo, consulta
  `programada` o `en_proceso` (se revalida al guardar), no se anulan con la consulta `finalizada`, paciente y médico heredados de la consulta.
  Diagnóstico: tipo, al menos un síntoma y descripción obligatorios, pieza dental FDI válida, no se anula con tratamiento asociado. Odontograma: sin
  repetir pieza + superficie + estado. Órdenes: avanzan de estado y no se cancelan si están Completadas o Canceladas.
- Registrar Consulta: la registra un funcionario desde una cita `Confirmado` sin consulta; bloquea si paciente, médico o consultorio están inactivos; no se
  anula con Ficha, Diagnóstico o Tratamiento.

### Estado final de Consultorio (cierre de la migración)
- **Las 18 pantallas están en Tabler** (`base_tabler.html`, Bootstrap 5, fetch + JS vanilla, SweetAlert2): 8 referenciales con baja lógica (Tipo Diagnóstico, Síntomas, Tipo Tratamiento, Tipo Insumo, Tipo Procedimiento Médico, Medicamentos, Tipo Estudio, Tipo Análisis) y 10 movimientos
  (Registrar Consulta con su Atención, Fichas Médicas, Diagnóstico, Odontograma visual FDI, Tratamientos, Sesiones, Recetas, Orden de Estudios, Orden de Análisis y Justificativo). Excepción fuera de Consultorio: "Historial Médico" (Agendamiento).
- **Reglas comunes de los movimientos clínicos** (con test): solo el médico de la consulta crea y anula; consulta `programada` / `en_proceso` revalidada en la transacción con la consulta `FOR UPDATE`; paciente y médico heredados; referenciales elegidos con `FOR SHARE` rechazando
  inactivos; anulación definitiva (no con la consulta finalizada); privacidad (un médico solo lee lo suyo, el Administrador lee todo y no escribe, Recepción solo ve las fichas); auditoría estructurada sin contenido clínico (los PDF sí lo llevan y cada descarga se audita como `EXPORTACION`);
  "Volver a la consulta" en cada pantalla contextual.
- **PDF** de Receta, Orden de Estudios, Orden de Análisis y Justificativo con un servicio común (`documento_clinico_pdf_service.py`); N.º de documento derivado del id (`CON-`, `RCT-`, `OES-`, `OAN-`, `JUS-`).
- **Esquema:** `schema_consultorio_base.sql` + las migraciones `schema_consultorio_etapa0` y `etapa2` a `etapa7` (idempotentes, no-op sobre una base al día) versionan las 24 tablas; el catálogo, los permisos (`schema_permisos_consultorio_roles.sql`) y la auditoría están cubiertos por tests.
- **Tests del módulo** (`tests/consultorio/`, ver `tests/README.md`): un `smoke_*` por movimiento y por referenciales, `smoke_*_vistas` y `browser_*` (Edge headless) por pantalla, el comparador JS ↔ Python de los validadores (324 casos) y los tres transversales del cierre
  (`smoke_esquema_consultorio`, `smoke_permisos_consultorio`, `smoke_auditoria_consultorio`).

### Etapa 0 (hecha): esquema versionado y andamiaje
- ⚠️ **Cambio del DER: se eliminó la tabla `consultas_detalle`** (vacía, sin FK entrantes ni objetos que dependieran; superada por Diagnóstico, Tratamiento y
  Sesiones; no figura en la Lista de Archivos de ningún CUS vigente). Se quitaron su DAO, su API (`/consultas-detalle`), las pestañas de detalle clínico de
  `consulta-index.html` y sus referencias en `estaEnUso()` de Síntomas, Tipo Diagnóstico y Tipo Procedimiento. Además `odontograma` suma `activo`
  (⚠️ DER) con único parcial `ux_odontograma_consulta_activo WHERE activo`; `estado` se retira en la etapa 4.
- Scripts en `app/dao/referenciales_consultorio/`: `schema_consultorio_base.sql` (las 23 tablas de Consultorio, generado de la base real, idempotente; es la
  fuente para reconstruir la base: depende de las tablas de Agendamiento/Seguridad, que todavía no están versionadas) y `schema_consultorio_etapa0.sql`
  (migración de una base existente, con verificación previa de `consultas_detalle`). Los 6 únicos parciales de los referenciales comparan con `UPPER()`.
- Auditoría: las 18 entidades de Consultorio están en `MODULO_POR_ENTIDAD`/`ETIQUETA_ENTIDAD` (módulos "Referenciales Consultorio" y "Módulo Consultorio";
  los 10 movimientos son `ENTIDADES_MOVIMIENTO`). `app/rutas/modulo_consultorio/utils.py` reexporta los helpers de Facturación.
- Test: `tests/consultorio/smoke_esquema_consultorio.py` (reconstruye las tablas en una base temporal y las compara con la real).
- **Corrección a la tabla de estado de referenciales de más arriba:** Tipo Diagnóstico y Síntomas YA tenían `activo` e índice único parcial en la base; solo
  sus DAO seguían con `DELETE` físico (resuelto en la etapa 2).
- ✅ **Resuelto en la etapa 3:** al anular una consulta la cita vuelve a `Confirmado` y `consultas_cab.id_cita` es UNIQUE parcial (`WHERE activo = true`); la anulación se audita.
- **Pendiente de la migración de Agendamiento (médicos):** al intentar eliminar un médico con historial, el mensaje dice *"No se encontró el médico con el ID 19 o
  no se pudo eliminar"*. Tiene que ser **baja lógica** (`medico.activo`) con un mensaje claro de que está en uso (consultas, agendas, citas, usuario vinculado), y
  `MedicoDao.deleteMedico` debe devolver `"EN_USO"` con el motivo y la API responder 409 (como Paciente→cliente y Consultorio→cajas).
- **Pendiente de la migración de Agendamiento:** generar el script base (`CREATE TABLE`) de Agendamiento y de Seguridad (paciente, medico, funcionario,
  consultorio, cita_*, agenda_*, usuarios, roles, permisos, menu, auditoría...) para que la base completa se pueda reconstruir desde el repo.
  `schema_consultorio_base.sql` depende de esas tablas.
- El DAO de Odontograma vive en `app/dao/referenciales_agendamiento/odontograma/` (ubicación equivocada; se mueve en la etapa 4).

### Etapa 3 (hecha): Registrar Consulta + Ficha Médica
Plan aprobado: `plan_etapa3.md` (sin versionar). **Decisiones de negocio confirmadas:**
- **Estados de la consulta:** `programada → en_proceso → finalizada` y `programada | en_proceso → cancelada`; `finalizada` y `cancelada` son finales. **Inicia y finaliza el
  médico de la consulta; cancela Recepción** (funcionario) **o el médico de la consulta**. `cancelada` ≠ `anulada`: cancelada = la atención no se realizó y queda en el
  historial, y **su cita pasa de `Realizado` a `Cancelado`** en la misma transacción (devolviendo el cupo; no vuelve a `Confirmado` y se audita); anulada = baja por error,
  definitiva, y la cita vuelve a `Confirmado`. Si la cita ya no estaba `Realizado` (la tocó Agendamiento) no se pisa y la auditoría lo dice.
- **Quién carga lo clínico:** el usuario debe estar vinculado a un médico (`id_medico_sesion()` en `permisos_contexto.py`) **y ser el médico de esa consulta** (se aplica a
  Ficha Médica ya y al resto de los movimientos en las etapas siguientes). El **Administrador queda con lectura clínica** (puede ver; no crea, edita ni cambia estados
  clínicos). Un médico solo ve SUS consultas en el listado y en el resumen.
- **Permisos** (`schema_permisos_consultorio_roles.sql`, idempotente y auditado): `Medico` = consulta `ver`/`estado`, y todo lo clínico (Ficha con `ver/nuevo/editar/anular`);
  `Recepcion` = consulta `ver/nuevo/estado/anular` y Ficha solo `ver`. Los usuarios vinculados a un médico pasan al rol `Medico` (los usuarios 9 y 10 están inactivos).
  `fichamedica` suma la acción `nuevo` en el catálogo.
- **Anular una consulta** también se bloquea con Odontograma, Receta, Órdenes (no canceladas) o Justificativo vigentes y con la consulta finalizada (el CUS: "no es posible
  anular una consulta con datos clínicos asociados").
- **Lecturas clínicas** (la ficha) restringidas a `fichamedica: ver`; **rangos clínicos de la ficha aprobados** (temperatura 30–45 °C, FC 20–250, FR 5–80, presión sistólica
  50–300 y diastólica 30–200 con sistólica > diastólica, peso 1–500 kg, talla 30–250 cm) y **no se permiten fichas sin ningún dato**; n.º de consulta `CON-0000017` derivado del id.
- **Mejora futura (fuera de esta etapa): reasignación del médico de una consulta** (p. ej. un suplente). Hoy el médico de la consulta es el de la cita y no se puede cambiar.
**Commit 1 (hecho):**
- `schema_consultorio_etapa3.sql` (id_cita único parcial, duración 1–480, CHECK de rangos y de la presión de la ficha, FK de la ficha a `RESTRICT`; `chk_ficha_con_datos` va
  `NOT VALID` a propósito para no tocar la ficha vacía 15 anterior) y su reflejo en `schema_consultorio_base.sql`.
- `ConsultaDao`/`consulta_api.py` reescritos: alta con bloqueo de la cita (`FOR UPDATE`, consulta simple: bloquearla con el JOIN a `estado_cita` daba "no encontrada" al
  perder una carrera), paciente/médico/consultorio/funcionario activos, estado inicial siempre `programada`; `PATCH /consultas/<id>/estado` (reemplaza al `PUT` libre);
  `DELETE` con reversión de la cita; `GET /consultas` con filtros y paginación en el servidor; `/indicadores`; `/citas-disponibles`; `/<id>/resumen` (solo contadores).
- Auditoría de `consultas_cab` (ALTA, MODIFICACION de estado y BAJA) con N.º de consulta, paciente con CI y médico; nunca contenido clínico.
- `CitaDao.getCitasConfirmadasSinConsulta` ya no cuenta las consultas anuladas.
- Tests: `smoke_consulta.py` (134 chequeos, incluida la carrera de dos altas) con `tests/consultorio/_fixtures.py` (datos `ZZ` por SQL, sin depender de usuarios reales).
- Datos de prueba para la prueba manual con el médico Oscar Gonzales (CI 2222222, usuario con rol `Medico`): `scripts/datos_prueba_oscar.py` (idempotente; sin `--ejecutar`
  solo simula). Los médicos Laura González y Andrea Cabrera (15 y 19) tienen sus usuarios INACTIVOS: no usarlos para probar.
**Commit 2 (hecho): Ficha Médica**
- **Validaciones** (servidor: `app/rutas/modulo_consultorio/validadores_clinicos.py`; espejo `app/static/js/consultorio-validadores.js`; base: `chk_ficha_rangos` y
  `chk_ficha_presion`): temperatura 30–45 °C, FC 20–250, FR 5–80, presión `SSS/DDD` (50–300 / 30–200, sistólica > diastólica), peso 1–500 kg, talla 30–250 cm (hasta 2 decimales,
  coma o punto), textos hasta 2.000 caracteres, **al menos un dato**. **El IMC lo calcula el servidor** (`peso / (talla/100)²`, 2 decimales); el del navegador se ignora.
  Si cambia un rango, cambiar los tres sitios; `tests/consultorio/comparar_ficha_js_py.py` verifica que JS y Python den lo mismo (74 casos, con JScript).
- **Quién y cuándo:** crear, editar y anular la ficha: solo el médico de esa consulta (`id_medico_sesion()`), con la consulta `programada` o `en_proceso`; se revalida DENTRO de la
  transacción con la consulta bloqueada (`FOR UPDATE`), así que si la cancelan mientras se carga, la ficha se rechaza (409). Una ficha activa por consulta (índice parcial + 409).
  Recepción y el Administrador solo leen.
- **Privacidad:** las lecturas (`/ficha-medica/consulta/<id>` y `/ficha-medica/<id>`) ya no son `@require_login`: piden `fichamedica ver`, y un médico solo lee las de SUS consultas.
  El listado (`GET /ficha-medica`, reemplaza a `/fichas-todas`) identifica la ficha (consulta, paciente con CI, médico, fecha, cuántos datos tiene) y **no devuelve ningún valor clínico**.
- **Auditoría** (`ficha_medica_consulta`): ALTA (consulta y paciente), MODIFICACION **sin valores** (ni anteriores ni nuevos; "sin cambios" no audita) y BAJA (Activo → Anulado).
- Tests: `smoke_ficha_medica.py` (115 chequeos: esquema, permisos por rol, 31 valores inválidos, IMC, una por consulta, estados de la consulta, auditoría sin valores, listado sin
  valores clínicos, dos altas simultáneas y la consulta que se cancela mientras se guarda) y `comparar_ficha_js_py.py`. `smoke_migracion02` ahora borra la auditoría que genera.
**Commit 3 (hecho): vistas Tabler**
- `consulta-index.html` (se reemplazaron las 2.142 líneas por ~330; se fueron el CSS "médico" de 700 líneas, jQuery, DataTables, Bootstrap 4 por CDN y el modal de funcionario):
  4 indicadores del servidor, filtros (estado, paciente o CI, fechas) y paginación en el servidor, badges de estado, `Abrir` y `Anular`, y el modal **Nueva Consulta** (elegir una cita
  `Confirmado` pendiente con buscador, duración opcional; no se elige médico, paciente ni funcionario).
- **Pantalla central** `consulta-detalle.html` en `/referenciales/consulta/consulta-detalle/<id>` (contextual, sin entrada de menú; permiso `consulta ver`; 404 si no existe o está
  anulada; 403 si es de otro médico): cabecera en tarjeta, acciones de estado según lo que devuelve `GET /consultas/<id>/resumen` (`acciones`: iniciar, finalizar, cancelar,
  cargar_clinico), la **tarjeta de la Ficha Médica** (formulario con IMC en vivo y las mismas validaciones del servidor; vista, editar y anular) y la grilla de los 7 registros clínicos
  con su contador de vigentes (se ofrecen según el `ver` de cada ventana destino; "Abrir" si puede cargar, "Ver" si no). Los destinos siguen en SB Admin 2 y se abren con `?consulta=<id>`
  (Diagnósticos también con `&paciente=&medico=`). **Pendiente de las etapas 4 a 7:** que cada destino lea `?consulta=` con la validación nueva y agregue "Volver a la consulta".
- `ficha-medica-index.html`: listado/auditoría transversal de fichas (consulta, paciente con CI, médico, estado de la consulta, cuántos datos tiene) **sin valores clínicos**; la ficha se
  abre, edita o anula desde la consulta.
- Las vistas declaran `const PK = 'id_consulta_cab'` / `PK_FICHA = 'id_ficha_medica'` (lección de la etapa 1: el JSON de Flask viene con las claves ordenadas).
- Tests: `smoke_consulta_vistas.py` (acceso por rol y por médico, Tabler sin jQuery, qué tarjetas ve cada rol, baja real por HTTP con el id de la vista) y `browser_consulta.py` (Edge headless con
  fetch simulado: listado, filtros, paginación, Nueva Consulta, atención de la consulta en 4 escenarios —médico programada, médico con ficha, Recepción, finalizada— y Fichas).

### Etapa 7 (hecha): Justificativo Médico y cierre del módulo
Plan: `plan_etapa7.md` (sin versionar). **Decisiones confirmadas (Justificativo):** estados **`pendiente` → `emitido` | `anulado`** (el CUS): se registra `pendiente`; la acción "Generar Justificativo" (permiso `estado`, solo el médico de la
consulta, también con la consulta finalizada, no con la cancelada ni anulada, auditada como MODIFICACION de estado) lo pasa a `emitido` y recién ahí es el documento oficial; "Anular" (definitivo) lo pasa a `anulado` desde `pendiente` o
`emitido`, **no con la consulta finalizada**. Solo el médico de la consulta crea y anula (consulta programada / en proceso revalidada en la transacción); Recepción sin acceso, Administrador solo lectura; un médico solo ve lo suyo. Días de reposo
1 a 365; recomendaciones opcionales; vínculo opcional solo con un diagnóstico vigente de la misma consulta; fecha fijada por el servidor; N.º `JUS-0000012` derivado del id.
- ⚠️ **Cambio del DER:** `justificativo_medico.estado` pasa de `activo` / `anulado` a **`pendiente` / `emitido` / `anulado`** (CHECK; por defecto `pendiente`; lo que estaba `activo` pasó a `emitido`) y `dias_reposo` tiene CHECK de 1 a 365.
  El CUS "Generar Justificativo Médico" debe describir los tres estados y la acción "Generar" como la que emite el documento.
**Commit 1 (hecho): base, backend y PDF**
- `schema_consultorio_etapa7.sql` (idempotente; `schema_consultorio_base.sql` actualizado). El rol Médico recibe `justificativomedico: estado` (`schema_permisos_consultorio_roles.sql`; el catálogo suma la acción `estado` a la ventana).
- `JustificativoMedicoDao` y `justificativo_medico_api.py` reescritos sobre `documento_clinico.py` (`/api/v1/justificativos`: GET lista con filtros y paginación, GET `/<id>`, POST, `PUT /<id>/emitir`, `DELETE /<id>`, `GET /<id>/pdf`; un médico solo lee lo
  suyo). Bloqueos: consulta `FOR UPDATE` → diagnóstico `FOR SHARE`; emitir: consulta `FOR SHARE` → justificativo `FOR UPDATE`.
- Auditoría (`justificativo_medico`): ALTA (Estado Pendiente), MODIFICACION (Pendiente → Emitido), BAJA (Pendiente o Emitido → Anulado; `estructura_auditoria` respeta el estado anterior que informa la API) y **EXPORTACION en cada descarga del PDF**, con
  N.º, consulta y paciente con CI; nunca los días de reposo ni las recomendaciones.
- **PDF** en el servicio común (`documento_clinico_pdf_service.py`, tipo `justificativo`): "se indica reposo por N día(s) a partir del dd/mm/aaaa" + recomendaciones; **pendiente = marca BORRADOR, emitido = sin marca, anulado = marca ANULADO**.
  `justificativo_pdf_service.py` se eliminó.
- `validar_justificativo` + espejo JS (324 casos JS ↔ Python en el comparador). Test: `smoke_justificativo.py` (esquema, permisos, validaciones, ciclo pendiente → emitido → anulado, consulta finalizada / cancelada / anulada, privacidad, PDF con sus tres marcas y
  la auditoría de cada descarga, auditoría sin contenido y carreras).

**Commit 2 (hecho): vista Tabler**
- `justificativo-medico-index.html` (reemplaza las 455 líneas SB Admin 2 + jQuery): listado con filtros (paciente o CI, estado, fechas) y paginación en el servidor, con `Ver`, **`PDF`**, **`Generar`** (pendiente → emitido, con confirmación; también con la
  consulta finalizada, no con la cancelada) y `Anular` (pendiente o emitido, solo con la consulta abierta); con `?consulta=<id>`: tarjeta de la consulta, "Volver a la consulta", los justificativos de esa consulta y el modal **Nuevo justificativo** (días de
  reposo 1–365, recomendaciones, diagnóstico opcional; mismas validaciones que el servidor). Las rutas pasan `es_medico`.
- Tests: `smoke_justificativo_vistas.py` (acceso por rol, Tabler sin jQuery, quién ve cada botón, generar / anular / PDF reales por HTTP con los ids de la vista, también con la consulta finalizada) y 4 escenarios más en `browser_documentos.py` (listado, de la
  consulta, rechazo del servidor, lectura).

**Commit 3 (hecho): cierre del módulo**
- **Barrido de lo viejo (eliminado):** en el cierre, los endpoints sin ningún consumidor `GET /odontogramas/paciente/<id>`, `GET /diagnosticos-medicos/paciente/<id>` y `GET /sesiones-tratamiento/tratamiento/<id>` (la vista lee las sesiones del detalle del
  tratamiento), con sus filtros `id_paciente` de los DAO y el ayudante `_acceso_tratamiento`; **`GET /consultas/<id>` y `GET /consultas/activas`** (solo pedían sesión: **filtraban pacientes y médicos de cualquier consulta a cualquier usuario logueado**, incluido el
  Cajero; nadie los usaba) con `ConsultaDao.getConsultasActivas`; `justificativo_pdf_service.py` (lo reemplaza el servicio común). Durante la migración ya se habían quitado `ConsultaDetalleDao`, `consulta_detalle_api` (`/consultas-detalle`), el DAO de
  Odontograma de Agendamiento (se movió) y las plantillas SB Admin 2 `diagnosticos-medicos-index`, `orden-estudio-index`, `orden-analisis-index` (las dos órdenes comparten `app/templates/orden-clinica-index.html`) y las reescritas de las demás pantallas.
  Verificado: ninguna plantilla de `modulo_consultorio` sin ruta, ningún método de DAO / helper sin uso, las 18 pantallas extienden `base_tabler.html`.
- **`smoke_permisos_consultorio.py`** (transversal): la política de los 10 movimientos contra la matriz real, y para Médico, Recepción, Cajero y Administrador × las 18 vistas y cada acción (ver, nuevo, editar, anular, estado, PDF y reactivar de los referenciales) que con permiso nunca
  responde 403 ni 5xx y sin permiso responde 403; el límite "un médico solo ve lo suyo" (detalle, listado, PDF y lookups de 9 documentos clínicos reales) y "el Administrador solo lee" (21 escrituras clínicas rechazadas para Administrador, otro médico, Recepción y Cajero; 436 combinaciones usuario × vista / acción en total).
- **`smoke_auditoria_consultorio.py`**: barrido estático (las 29 rutas que mutan llaman a `auditar`) y dinámico (35 filas de auditoría de los 9 movimientos con marcadores secretos en todos los campos clínicos: ninguna los contiene).
- **`smoke_esquema_consultorio.py` ampliado:** ahora compara también la definición completa de cada restricción, **todos** los triggers, los comentarios, las 4 funciones de validación y las **24** tablas (se sumó `sesion_procedimientos`); `schema_consultorio_base.sql` suma los
  `COMMENT ON` que faltaban. En una base con las tablas de Agendamiento y Seguridad reconstruye el módulo idéntico a la real; **una base completamente vacía todavía no se puede armar** (falta versionar los `CREATE TABLE` de Agendamiento y Seguridad).
- **Permisos de los 8 referenciales clínicos (decidido tras el cierre):** los gestionan el **Médico** (`ver`, `nuevo`, `editar`, `anular`) y el Administrador (bypass); **Recepción y Cajero no tienen ningún permiso sobre ellos** (a Recepción se le quitaron 28 filas, incluido Medicamentos que tenía acciones sin `ver`).
  Seed idempotente `schema_permisos_consultorio_roles.sql` (con backup previo y auditado en `auditoria_cambios`); `smoke_permisos_consultorio` lo verifica. Los combos de otras pantallas siguen leyendo estos catálogos con `require_login`.
- **Pendiente fuera de Consultorio:** "Historial Médico" (Agendamiento) sigue en SB Admin 2 y en el menú de Consultorio.

### Etapa 6 (hecha): Recetas, Orden de Estudios y Orden de Análisis (con PDF)
Plan: `plan_etapa6.md` (sin versionar). **Decisiones confirmadas:** solo el médico de la consulta crea y anula (consulta programada / en proceso revalidada en la transacción; Recepción sin acceso, Administrador solo lectura;
no se anula con la consulta finalizada); **avanza el estado de una orden solo el médico de la orden, también con la consulta FINALIZADA** (el paciente trae el resultado días después) y no con la cancelada ni anulada;
vínculos opcionales con un diagnóstico vigente y con un tratamiento no cancelado **de la misma consulta** (así lo dice el CUS); la receta no tiene `estado` (el "estado inicial Pendiente" es de las órdenes); fecha del documento
fijada por el servidor; N.º de documento derivado del id (`RCT-0000012`, `OES-0000005`, `OAN-0000003`), sin columnas nuevas.
**Commit 1 (hecho): base, backend y PDF**
- `schema_consultorio_etapa6.sql` (idempotente; `schema_consultorio_base.sql` actualizado): único parcial `receta_medicamento (receta, medicamento) WHERE activo` (un medicamento no se repite en una receta; si había repetidos
  vigentes se dejó el primero), `activo` NOT NULL, CHECK de textos no vacíos y trigger diferido `trg_receta_con_medicamento` (toda receta vigente tiene al menos un medicamento).
- Código común: `documento_clinico.py` (consulta y vínculos bloqueados, N.º de documento, clínica y médico para el PDF) y `orden_base.py` (`OrdenBaseDao`: las dos órdenes son idénticas, solo cambia el catálogo; `OrdenEstudioDao` y
  `OrdenAnalisisDao` solo declaran tabla y columnas) con la fábrica de API `orden_api_base.crear_orden_api` (`/api/v1/orden-estudios` y `/orden-analisis`); `RecetaDao` + `receta_api.py` (`/api/v1/recetas`).
  Bloqueos: consulta `FOR UPDATE` → diagnóstico y tratamiento `FOR SHARE` → medicamentos / tipo `FOR SHARE` en orden de id (los inactivos se rechazan; lo ya cargado se sigue mostrando aunque el catálogo se anule).
  Avanzar el estado: consulta `FOR SHARE` → orden `FOR UPDATE`, un paso por vez que calcula el sistema (el cuerpo no elige el estado).
- Endpoints (todos con privacidad: un médico solo lee lo de SUS consultas): `GET` lista (filtros `q`, `estado`, `desde`, `hasta`, `consulta`, paginación), `GET /<id>`, `POST`, `PUT /<id>/estado` (órdenes), `DELETE /<id>`, `GET /<id>/pdf`.
- Auditoría (`recetas`, `orden_estudios`, `orden_analisis`): ALTA, BAJA, MODIFICACION (estado de la orden) y **EXPORTACION en cada descarga del PDF**, con N.º de documento, consulta y paciente con CI; **nunca** medicamentos, dosis,
  tipos, motivo ni indicaciones.
- **PDF** (`app/Services/documento_clinico_pdf_service.py`, patrón `calcular_datos_documento` / `dibujar_documento` / `generarDocumentoPdf`): encabezado con la clínica (`empresa`), título, N.º y fecha, paciente con CI, médico con
  especialidad (y N.º de registro solo si lo tiene), el contenido (receta: tabla de medicamentos + indicaciones; órdenes: tipo, motivo, indicaciones y estado), firma y sello, marca ANULADA / CANCELADA en rojo (se descarga igual) y
  continúa en otra página si es largo. **Lleva el contenido clínico; la auditoría no.** El Justificativo (etapa 7) pasará a este servicio.
- `validadores_clinicos.py` + `consultorio-validadores.js`: `validar_receta`, `validar_orden_estudio`, `validar_orden_analisis` y sus espejos (298 casos JS ↔ Python en `comparar_ficha_js_py.py`).
- Tests: `smoke_receta.py`, `smoke_orden_clinica.py` (las dos órdenes con el mismo código, incluido el avance con la consulta finalizada y las carreras) y `smoke_pdf_documentos.py` (contenido de los tres PDF, marca, varias páginas, privacidad y
  la auditoría de cada descarga). `_fixtures.py`: la receta de los fixtures se inserta con su medicamento (trigger diferido) y suma `medicamento()`, `tipo_estudio()` y `tipo_analisis()`.

**Commit 2 (hecho): vistas Tabler**
- `receta-index.html` (reemplaza las 537 líneas SB Admin 2 + jQuery): **sin `?consulta=`** = listado con filtros (paciente o CI, fechas) y paginación en el servidor, con `Ver` (modal con la tabla de medicamentos, dosis, frecuencia, duración
  e indicaciones), **`PDF`** (se abre en otra pestaña) y `Anular` (solo con la consulta abierta); **con `?consulta=<id>`** = tarjeta de la consulta, "Volver a la consulta", las recetas de esa consulta y el modal **Nueva receta** (filas de
  medicamento con su dosis, frecuencia y duración que se agregan y se quitan, indicaciones generales y diagnóstico / tratamiento opcionales; mismas validaciones que el servidor con `consultorio-validadores.js`).
- **Una sola plantilla para las dos órdenes**: `app/templates/orden-clinica-index.html` (reemplaza las dos de 547 líneas); la ruta de cada una le pasa `cfg` (título, API, clave primaria, columna del tipo, catálogo, ventana, validador).
  Listado con filtros (paciente, CI o tipo; estado; fechas), `Ver` (+ PDF), **avanzar estado** con confirmación y **cancelar**. La vista ofrece avanzar también con la consulta FINALIZADA y solo lo niega con la cancelada; cancelar solo con la
  consulta abierta y la orden no completada.
- Las rutas pasan `es_medico`: solo un usuario vinculado a un médico ve los botones de registrar, avanzar y anular (el Administrador, no).
- Tests: `smoke_docs_vistas.py` (acceso por rol, Tabler sin jQuery, quién ve cada botón, la plantilla común de las órdenes y el avance / la baja reales por HTTP con los ids de las vistas, incluso con la consulta finalizada) y
  `browser_documentos.py` (Edge headless, 9 escenarios: receta en listado / consulta / rechazo del servidor / lectura, orden de estudios en listado / consulta / rechazo / lectura y orden de análisis).
- Pendiente para la etapa 7: el Justificativo pasa al servicio común de PDF y a la misma auditoría de descargas.

### Etapa 5 (hecha): Tratamientos y Sesiones (Procedimientos e Insumos Utilizados)
Plan: `plan_etapa5.md` (sin versionar). **Decisiones confirmadas:** cada sesión se registra DENTRO de una consulta; varios procedimientos por sesión; insumos opcionales (0 o más, sin repetir, cantidad 1–999);
solo el médico crea, anula y finaliza (Recepción sin acceso, Administrador solo lectura); anulación de tratamiento definitiva; anular una sesión solo la última vigente, desde su consulta abierta, con cascada, y el
tratamiento vuelve a `pendiente` si queda sin sesiones; fecha del tratamiento propuesta hoy (editable, no futura), fecha de la sesión fijada por el servidor, próxima cita opcional no anterior a hoy.
- ⚠️ **Cambios del DER (hay que reflejarlos en el diagrama y el análisis):** `sesiones_tratamiento.id_consulta_cab` (INT NOT NULL, FK RESTRICT a `consultas_cab`: la consulta en la que se registró la sesión, del mismo paciente y
  médico que el tratamiento, puede ser posterior a la que lo creó); **tabla nueva `sesion_procedimientos`** (`id_sesion_procedimiento`, `id_sesion` FK, `id_tipo_procedimiento` FK, `activo`; único parcial por sesión + tipo
  entre los vigentes; al menos uno por sesión vigente, con trigger diferido); **columna retirada `sesiones_tratamiento.id_tipo_procedimiento`** (los datos se migraron a `sesion_procedimientos`); `sesion_insumos` con único parcial
  por sesión + insumo y cantidad 1–999; `activo` / `estado` NOT NULL. Triggers `trg_validar_sesion_consulta` (la consulta de la sesión es del mismo paciente y médico que el tratamiento) y `trg_sesion_con_procedimiento`.
- ⚠️ **El CUS de "Gestionar Procedimientos e Insumos Utilizados" debe reflejar que cada sesión se registra en una consulta** (mismo paciente y médico que el tratamiento; un tratamiento de varias visitas recibe sus sesiones
  en consultas posteriores), que una sesión tiene uno o más procedimientos y que los insumos son opcionales.
**Commit 1 (hecho): base y backend**
- `app/dao/referenciales_consultorio/schema_consultorio_etapa5.sql` (idempotente; `schema_consultorio_base.sql` actualizado). Al migrar, los renglones de insumo repetidos en una misma sesión se fusionaron en uno (suma de cantidades).
- `TratamientoDao` y `SesionTratamientoDao` reescritos. Bloqueos: consulta `FOR UPDATE` → tratamiento `FOR UPDATE` → tipos `FOR SHARE` en orden de id (tipo de tratamiento, diagnóstico, procedimientos, insumos; los inactivos se rechazan).
  Alta de tratamiento: médico de la consulta, consulta `programada` / `en_proceso` revalidada, diagnóstico opcional vigente y de la misma consulta. Sesión: consulta abierta y del mismo paciente y médico que el tratamiento, que debe estar
  `pendiente` o `en_seguimiento` (la 1.ª sesión lo pasa a `en_seguimiento`). Anular tratamiento: sin sesiones vigentes ni venta EMITIDA y con la consulta que lo creó abierta. **Finalizar** (permiso `estado`): solo el médico del
  tratamiento, desde `en_seguimiento`, sin exigir la consulta abierta. Un tratamiento finalizado no admite sesiones ni anular sus sesiones.
- APIs `/api/v1/tratamientos` (GET lista con filtros `q`, `estado`, `desde`, `hasta`, `consulta`, `paciente`, `en_curso=1` y paginación; GET `/<id>` con sus sesiones; GET `/consulta/<id>` lookup de Receta y Órdenes con
  `require_algun_permiso`; POST; DELETE; PUT `/<id>/finalizar`) y `/api/v1/sesiones-tratamiento` (GET `/tratamiento/<id>`, GET `/<id>`, POST, DELETE). Un médico solo lee lo suyo; Recepción sin acceso.
- Auditoría (`tratamientos` y `sesiones_tratamiento`): ALTA / BAJA con consulta, paciente (con CI) y tipo de tratamiento, y MODIFICACION del estado del tratamiento (finalizar, 1.ª sesión, última sesión anulada); **nunca**
  descripciones, observaciones, procedimientos ni insumos.
- `validadores_clinicos.py` + `consultorio-validadores.js`: `validar_tratamiento` / `validar_sesion` y sus espejos (215 casos JS ↔ Python en `comparar_ficha_js_py.py`).
- `TipoProcedimientoMedicoDao.esta_en_uso` consulta `sesion_procedimientos`; Insumo y Tipo Tratamiento siguen igual (ya hacían el `FOR SHARE` del hijo: el alta toma el bloqueo del referencial).
- **Facturación (Venta de Tratamiento) intacta:** lee `id_tratamiento`, `id_paciente`, `estado <> 'cancelado'`, `fecha_tratamiento`, `codigo` e `id_tipo_tratamiento`; `smoke_ventas.py` se adaptó para anular los tratamientos como el médico de una
  consulta abierta (datos ZZ) y pasa completo.
- Tests: `smoke_tratamiento.py` (79 chequeos, con carreras del tipo y de la consulta que se anulan mientras se guarda) y `smoke_sesion_tratamiento.py` (92, con varias visitas, cascada, base de datos y carreras). Las vistas de esta etapa
  (todavía las viejas SB Admin 2) se reescriben en el commit 2.
**Commit 2 (hecho): vistas Tabler**
- `tratamiento-index.html` (reemplaza las 521 líneas SB Admin 2 + jQuery): **sin `?consulta=`** = listado con filtros (paciente / CI / tipo, estado, fechas) y paginación en el servidor, con `Ver` (modal con el detalle y sus
  sesiones), `Sesiones`, `Finalizar` y `Anular`; **con `?consulta=<id>`** = tarjeta de la consulta, "Volver a la consulta", los tratamientos de esa consulta, los **tratamientos en curso del paciente creados en otras
  consultas** (con el botón "Registrar sesión en esta consulta": así se arma un tratamiento de varias visitas) y el modal **Nuevo tratamiento** (tipo, diagnóstico opcional de la consulta, fecha propuesta hoy y no futura,
  descripción; mismas validaciones que el servidor con `consultorio-validadores.js`). Anular solo se ofrece sin sesiones, sin factura y con la consulta de origen abierta; Finalizar, en seguimiento.
- `sesion-tratamiento-index.html` (reemplaza las 518 líneas viejas; pantalla contextual `?tratamiento=<id>[&consulta=<id>]`): tarjeta del tratamiento y de la consulta en la que se registra, tabla de sesiones (número, fecha,
  consulta, procedimientos, insumos × cantidad, próxima cita), `Ver`, `Anular` (solo la última, con la consulta de la sesión abierta y el tratamiento no finalizado), `Finalizar tratamiento` y el modal **Nueva sesión**
  (procedimientos con buscador y contador, descripción, observaciones, próxima cita no anterior a hoy y filas de insumos con cantidad que se agregan y se quitan). Sin `?consulta=` es solo lectura ("Volver a tratamientos");
  con una consulta de otro paciente o médico avisa y no ofrece registrar.
- Las rutas pasan `es_medico`: solo un usuario vinculado a un médico ve los botones de registrar, finalizar y anular (el Administrador, no).
- Tests: `smoke_trat_vistas.py` (acceso por rol, Tabler sin jQuery, quién ve cada botón, recorrido de un tratamiento de dos visitas y baja real por HTTP con los ids de las vistas) y `browser_tratamiento.py` (Edge headless,
  11 escenarios: listado, tratamientos de la consulta y en curso del paciente, alta y rechazo del servidor, lectura, sesiones con procedimientos / insumos / validaciones, consulta cerrada, otra consulta, tratamiento finalizado).

### Etapa 4 (hecha): Diagnóstico y Odontograma
Plan: `plan_etapa4.md`. **Decisiones confirmadas:** pieza dental del diagnóstico **opcional** (si se carga, FDI válida); la **fecha del diagnóstico la fija el servidor** (no editable);
quitar un hallazgo del odontograma = **baja lógica del renglón** (`activo = false`, no borrado físico); un odontograma sin hallazgos se permite; la acción `editar` de la ventana Odontograma se
agregó al catálogo y solo la tiene el rol Médico.
- ⚠️ **Cambios del DER (hay que reflejarlos en el diagrama y el análisis):** `estado_dental.aplica_a` (`PIEZA` | `SUPERFICIE`: Caries, Obturación, Incrustación, Sellador, Resina, Amalgama y
  Fractura son de superficie; los otros 15, de pieza completa); `odontograma` **sin la columna `estado`** (queda `activo`); `odontograma_detalle.activo` (baja lógica por renglón) con único parcial
  `(odontograma, pieza, superficie, estado) WHERE activo`; superficie `O V L M D` o `T` (pieza completa) con CHECK; pieza FDI con CHECK en `odontograma_detalle.numero_diente` y en
  `diagnosticos.pieza_dental`; FKs de `odontograma.id_paciente` y `odontograma_detalle.id_odontograma` a `RESTRICT`; **trigger diferido** `trg_diagnostico_con_sintoma` (todo diagnóstico vigente tiene
  al menos un síntoma). Script `schema_consultorio_etapa4.sql` (idempotente; `schema_consultorio_base.sql` actualizado).
- **Diagnóstico** (`DiagnosticoDao`, `diagnostico_api.py`): crea y anula solo el médico de la consulta, con la consulta `programada` / `en_proceso` revalidada con la consulta bloqueada (`FOR UPDATE`);
  tipo ACTIVO y **al menos un síntoma, todos ACTIVOS** (bloqueados `FOR SHARE`, en orden); descripción obligatoria; pieza FDI opcional (permanentes 11–18, 21–28, 31–38, 41–48; temporales 51–55, 61–65,
  71–75, 81–85); anular (definitiva) sin tratamiento **vigente** asociado. Los diagnósticos ya cargados se siguen mostrando aunque su tipo o sus síntomas se hayan anulado. Un médico solo lee lo de SUS
  consultas. El lookup `GET /diagnosticos-medicos/consulta/<id>` (lo usan Tratamiento, Receta, Órdenes y Justificativo) pasó de `@require_login` a `@require_algun_permiso` (nuevo decorador). Auditoría
  (`diagnosticos`): ALTA / BAJA con código DX, N.º de consulta y paciente; sin tipo, síntomas ni descripción.
- **Odontograma** (`OdontogramaDao`, ahora en `app/dao/referenciales_consultorio/odontograma/`; `odontograma_api.py`): uno por consulta; **la precarga la hace el servidor** en la misma transacción
  (copia los hallazgos ACTIVOS del último odontograma vigente del paciente de una consulta ANTERIOR no cancelada); hallazgos con pieza FDI + superficie + estado, un estado de pieza completa solo con `T` y uno de
  superficie solo con `O V L M D`, **un registro idéntico activo se rechaza** (409); agregar / quitar hallazgos con la acción `editar`, solo el médico de la consulta con la consulta abierta. Se eliminaron
  `PUT`, `PATCH …/estado`, `validar-consulta` y `precarga`. Auditoría (`odontograma`): ALTA (con "Precargado desde CON-…"), MODIFICACION ("odontograma modificado", sin piezas ni estados) y BAJA.
- `validadores_clinicos.py` + `consultorio-validadores.js`: `validar_pieza_fdi`, `validar_superficie`, `validar_diagnostico` y sus espejos (142 casos JS ↔ Python en `comparar_ficha_js_py.py`).
- `acceso_consulta()` en `modulo_consultorio/utils.py`: la consulta existe y, si el usuario es médico, es suya (lo usan Ficha, Diagnóstico y Odontograma).
- Tests: `smoke_diagnostico.py` (117 chequeos, con las carreras del tipo / síntoma / consulta que se anulan mientras se guarda) y `smoke_odontograma.py` (137, con la precarga y los duplicados).
  `smoke_migracion02.py` quedó solo con las secciones de esquema, permisos y consulta (lo demás lo cubren los tests nuevos).
**Commit 2 (hecho): vistas Tabler**
- `diagnostico-index.html` (reemplaza `diagnosticos-medicos-index.html`, 1.178 líneas SB Admin 2 + jQuery): **sin `?consulta=`** = listado con filtros (código, paciente o CI, fechas) y paginación en el servidor, `Ver` (modal con
  tipo, síntomas, descripción, pieza y observaciones) y `Anular`; **con `?consulta=<id>`** (desde la Atención de la consulta) = tarjeta de la consulta, "Volver a la consulta", los diagnósticos de esa consulta y el modal
  **Nuevo diagnóstico** (tipo, selector de síntomas con búsqueda y contador, pieza FDI en un selector de 8 cuadrantes, descripción, observaciones; mismas validaciones que el servidor con `consultorio-validadores.js`).
  Las rutas pasan `es_medico` al template: solo un usuario vinculado a un médico ve "Nuevo" y "Anular" (el Administrador, no).
- `odontograma-index.html` (reemplaza las 1.208 líneas viejas): **listado** (sin `?consulta=`) y **odontograma visual** (con `?consulta=<id>`): SVG generado en el navegador con las piezas FDI en dos arcadas y cuatro
  cuadrantes (+ interruptor de dentición temporal: 32 piezas permanentes, 52 con las temporales), cada pieza con sus 5 superficies (V hacia afuera, M hacia la línea media, O al centro) y un contorno para los hallazgos
  de pieza completa; **el color de cada superficie / contorno es `estado_dental.color`**, con el símbolo y una leyenda; clic en una superficie (o en el número = pieza completa) abre el panel de la pieza (estados filtrados por
  `aplica_a`, observación, Agregar y Quitar con confirmación); tabla con todos los hallazgos; "Crear odontograma" (precargado) y "Anular odontograma" (definitivo). **Para pulir el diseño** (Antigravity): el dibujo está en
  `dibujarPieza()` / `pintarOdontograma()` y las clases `.odo-*` del `<style>` de la plantilla (variables `--odo-*`); la lógica no depende de esas clases.
- Los destinos que faltan migrar (Tratamientos, Recetas, Órdenes, Justificativo) siguen con `?consulta=` y todavía no tienen "Volver a la consulta" (etapas 5 a 7).
- Tests: `smoke_diag_odo_vistas.py` (acceso por rol, Tabler sin jQuery, quién ve cada botón, baja real por HTTP con el id de la vista) y `browser_diag_odontograma.py` (Edge headless, 8 escenarios: listados, diagnóstico en la
  consulta con alta y rechazo del servidor, lectura, odontograma sin crear / editor / solo lectura; verifica las 32 y 52 piezas, la orientación M/D y V/L por cuadrante, el color por estado, el filtrado de estados por pieza o
  superficie, agregar / quitar y anular).

### Etapa 2 (hecha): Tipo Diagnóstico y Síntomas
- Mismo `CatalogoDao` y `crear_api_catalogo` que la etapa 1 (ahora con `FECHA = False`: estas dos tablas no tienen `fecha_registro`). **Tipo Diagnóstico** lleva
  descripción (`descripcion_diagnostico`, la clave única entre los activos) y tipo (`tipo_diagnostico`, obligatorio, en MAYÚSCULAS); su API sigue en `/api/v1/diagnosticos`
  (la consume también Gestión de Diagnósticos para su combo). **Síntomas** solo lleva la descripción (`/api/v1/sintomas`, que alimenta el selector de síntomas del
  diagnóstico). Ambos en modo ampliado; el `DELETE` físico y las validaciones propias (solo letras) desaparecieron.
- Baja bloqueada (409): Tipo Diagnóstico → diagnósticos vigentes o tratamientos no `cancelado`; Síntoma → `diagnostico_sintoma` de diagnósticos vigentes. Auditoría
  como en la etapa 1 (entidades `tipo_diagnostico` y `sintoma`).
- `schema_consultorio_etapa2.sql` (idempotente): pasa a MAYÚSCULAS lo cargado antes (`prueba` → `PRUEBA`, etc.).
- **Pendiente de la etapa 4 (Diagnóstico):** el alta de un diagnóstico debe tomar `FOR SHARE` sobre su tipo y sobre cada síntoma elegido (y rechazar los inactivos),
  y los listados que muestran diagnósticos ya cargados NO deben filtrar por `activo` del tipo (un diagnóstico viejo con un tipo anulado se sigue viendo).
- `SintomaDao.estaEnUso` / `TipoDiagnosticoDao.estaEnUso` pasaron a `esta_en_uso` (devuelve el motivo o `False`, como el resto).
- Tests: `smoke_referenciales_consultorio` y `browser_referenciales` ahora cubren los 8.

### Etapa 1 (hecha): los 6 referenciales con baja lógica en Tabler
Tipo Tratamiento, Tipo Insumo Utilizado, Tipo Procedimiento Médico, Medicamentos, Tipo Estudio y Tipo Análisis cumplen el Estándar de referenciales (los 6 puntos).
- **Código compartido:** `app/dao/referenciales_consultorio/CatalogoDao.py` (listar con/sin inactivos, obtener, duplicado, alta, modificación, `anular` con
  `FOR UPDATE` + `_motivo_en_uso` en la misma transacción, `reactivar` que valida duplicado) y la fábrica `app/rutas/modulo_consultorio/catalogo_api.py`
  (`crear_api_catalogo`: GET lista/uno, POST, PUT, DELETE, PATCH `/reactivar`, auditoría y permisos). Cada referencial declara solo lo suyo: su DAO hereda de
  `CatalogoDao` (tabla, clave de texto, extras y el motivo de uso) y su `*_api.py` llama a la fábrica. Nombres de blueprint y URL sin cambios; las claves JSON de
  los lookups de otras pantallas tampoco (`id_insumo`, `id_tipo_procedimiento`, `nombre_comercial`...), solo se suman `activo` y `fecha_registro`.
- **Vistas:** una plantilla por pantalla (`base_tabler.html`, modal, Estado, "Mostrar inactivos", Reactivar con SweetAlert2, `facturacion-listado.js` y
  `facturacion-validadores.js`). Tipo Tratamiento suma Precio (Gs.) e IVA (10% / 5% / Exenta); Insumo y Medicamento, Presentación (opcional).
- **Descripción en modo ampliado en TODOS los de Consultorio** (`normalizar_descripcion(..., 100, ampliada=True)`): MAYÚSCULAS, letras con tildes y Ñ, números,
  espacios y `. - / , % ( ) + &`, hasta 100, debe empezar con letra o número (ej. `AMOXICILINA/CLAVULÁNICO 875/125 MG`, `LIMPIEZA DENTAL (PROFILAXIS)`).
  `normalizar_descripcion` ganó `campo`/`etiqueta`/`articulo` (Medicamentos usa `nombre_comercial` / "nombre comercial" / "El") y `validar_presentacion`
  (opcional, hasta 100, mismos caracteres); espejo en `facturacion-validadores.js` (`V.presentacion`, y `V.descripcion` con `etiqueta`/`articulo`).
- **Bajas bloqueadas (409) si están en uso:** Tipo Tratamiento → tratamientos no `cancelado`; Insumo → `sesion_insumos` activos; Procedimiento → sesiones
  activas; Medicamento → `receta_medicamento` activos; Estudio / Análisis → órdenes no `cancelado`. **Etapa 5 (hecha):** el alta de tratamientos y sesiones toma `FOR SHARE` sobre tipo de tratamiento, procedimiento e insumo. **Etapa 6 (hecha):** lo mismo para Medicamento, Tipo Estudio y Tipo Análisis.
- **Id en las vistas:** cada plantilla declara `const PK = '<clave primaria>'` y arma las URL con `f[PK]`. **Nunca tomar "la primera clave" del JSON:** Flask
  devuelve las claves ordenadas alfabéticamente y la primera es `activo` (la vista pedía `/tipos-tratamiento/true` y todo daba 404: anular, reactivar y editar).
  `smoke_referenciales_consultorio` hace la baja y la reactivación reales por HTTP con el id que arma la vista y comprueba contra `url_map` que todas las filas
  reales resuelvan sus rutas; `browser_referenciales` usa un mock con las claves ordenadas como el servidor.
- ⚠️ **Presentación (Insumo y Medicamento) es un campo nuevo para el análisis: hay que agregarlo al DER y a los CUS de "Mantener Tipo Insumo Utilizado" y
  "Mantener Medicamentos"** (texto opcional, hasta 100 caracteres, en MAYÚSCULAS, p. ej. `CAJA X 20 COMPRIMIDOS`). La columna `presentacion VARCHAR(100)` ya
  existía en `insumos` y `medicamentos`, pero no figuraba en la documentación. Igual que `precio` e `iva` de Tipo Tratamiento (ver más arriba).
- **Auditoría** (`auditoria_cambios`, módulo "Referenciales Consultorio"): ALTA, MODIFICACION (solo lo que cambió; sin cambios no audita), BAJA y REACTIVACION.
- Tests: `tests/consultorio/smoke_referenciales_consultorio.py` (338 chequeos sobre los 6), `tests/consultorio/browser_referenciales.py` (Edge headless, ~230
  chequeos de DOM) y `smoke_tipo_tratamiento.py` actualizado (el test limpia ahora la auditoría que genera).

