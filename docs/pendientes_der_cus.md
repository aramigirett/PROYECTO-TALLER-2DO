# Pendientes de DER y CUS

> Lo que la base real tiene y la tesis (DER, CUS, secuencias) todavía no.
> Movido tal cual desde `CLAUDE.md` (sin cambios de contenido) al reorganizarlo. La guía compacta es `CLAUDE.md`.

## Cambios del DER pendientes de reflejar
Lista única (Seguridad, Facturación y Consultorio) de lo que la base REAL tiene y el DER de la tesis todavía no. Cada punto sale de un script idempotente del repositorio (entre paréntesis). Los avisos ⚠️ originales siguen en el lugar donde se explican.

**Seguridad**
- `usuarios`: se **quitaron** `ci_ruc` y `correo` (el CI y el correo salen de la persona vinculada; `schema_datos_unica_fuente*.sql`); se **agregaron** `intentos_fallidos`, `bloqueado` y `fecha_bloqueo` (`schema_acceso_seguridad.sql`). `funcionario.cedula` y `medico.cedula` con UNIQUE.
- `token_2fa.proposito` (`'LOGIN'` | `'RECUPERACION'`, CHECK) y su índice parcial (`schema_acceso_seguridad.sql`).
- `auditoria_acceso`: `id_usuario_actor` (FK a `usuarios`, nullable) y `pais_detectado VARCHAR(2)` (`schema_acceso_seguridad.sql`, `schema_ip_inactividad.sql`). **Se eliminó la tabla `paises`** (`schema_eliminar_paises.sql`).
- `permisos`: **sin columna `ventana`**; se identifican por `id_menu` (FK a `menu`, una fila por ventana, `clave` = la ventana del catálogo); la acción `desbloquear` en el CHECK; la tabla `menu` (`migraciones/02_migracion_requiere_codigo.sql`, `schema_permisos_*.sql`).
- `auditoria_cambios`: `modulo VARCHAR(30)`, `valores_anteriores JSONB`, `valores_nuevos JSONB`, `detalle` de `VARCHAR(255)` a `TEXT`, la acción `EXPORTACION` en el CHECK; tabla `auditoria_umbrales` y vista `v_auditoria_anomalias` (`schema_auditoria_estructurada.sql`); trigger `trg_auditoria_inmutable` (también en `auditoria_acceso`).
- Roles de base de datos `odontoclinic_app` y `odontoclinic_backup` (no son del DER, pero sí de la documentación de seguridad: `schema_usuario_app.sql`).

**Facturación**
- `forma_cobro.tipo` (`'EFECTIVO'`, `'TARJETA'`, `'CHEQUE'`, `'TRANSFERENCIA'`, NOT NULL) y `cobro_det.numero_referencia VARCHAR(30)` (`schema_cobranzas_columnas.sql`).
- `nota_credito_debito_cab.id_apertura` (INT NOT NULL, FK a `apertura_cierre_caja`) y `monto_reintegro NUMERIC(12,0)` (`schema_notas_columnas.sql`).
- Tabla **`cuenta_bancaria`** (`id_cuenta_bancaria`, `id_entidad_emisora`, `tipo_cuenta`, `numero_cuenta`, `titular`, `activo`) y `recaudacion_depositar.id_cuenta_bancaria` con su CHECK (`schema_cuenta_bancaria.sql`).
- Verificar contra el DER (se crearon por script, no figuran como "tal cual"): `empresa` y `timbrado` (`schema_empresa_timbrado.sql`), `venta_cab` / `venta_det` / `cuenta_cobrar` (`schema_ventas.sql`; `venta_det.descripcion` VARCHAR(200) en `schema_ventas_etapa2.sql`), `items.id_deposito` NOT NULL y la tabla `deposito`
  (`migracion_items_deposito.sql`), `tipo_items.controla_stock`, la baja lógica (`activo`) con índices únicos parciales de los referenciales y la fila `SIN NOMBRE` de `cliente`.
- Objetos de base (para el análisis de Base de Datos II): `sp_siguiente_numero_factura`, `sp_registrar_arqueo` y los triggers y vistas de Ventas, Cobranzas, Remisión, Notas y Arqueo (ver "Objetos de base de datos").

**Consultorio**
- **Eliminada** la tabla `consultas_detalle` (`schema_consultorio_etapa0.sql`).
- `tipos_tratamiento.precio NUMERIC(12,0)` e `iva SMALLINT` (0 / 5 / 10); `insumos.presentacion` y `medicamentos.presentacion` (campo que el análisis no tenía).
- `diagnosticos`: `id_consulta_cab` (NOT NULL, FK) en lugar de `id_consulta_detalle`; sin `sintomas`; tabla **`diagnostico_sintoma`**; pieza FDI con CHECK; trigger diferido (todo diagnóstico vigente tiene un síntoma) (`migraciones/02…`, `etapa4`).
- `odontograma`: `id_consulta_cab` (NOT NULL, FK) en lugar de `id_funcionario`, **uno por consulta**, `activo` y **sin `estado`**; `odontograma_detalle.activo` y único parcial; superficie `O V L M D T` y pieza FDI con CHECK; **`estado_dental.aplica_a`** (`PIEZA` | `SUPERFICIE`) y `estado_dental.estado` → `activo` (`etapa0`, `etapa4`, `migraciones/02…`).
- `consultas_cab`: `id_funcionario` NOT NULL (el funcionario es la sesión), `id_cita` NOT NULL con único parcial (`WHERE activo`), duración 1–480, estados `programada` / `en_proceso` / `finalizada` / `cancelada`; `ficha_medica_consulta` con rangos clínicos y presión, una ficha por consulta (`etapa3`).
- `sesiones_tratamiento.id_consulta_cab` (NOT NULL, FK) y **columna retirada** `sesiones_tratamiento.id_tipo_procedimiento`; tabla **`sesion_procedimientos`** (`id_sesion_procedimiento`, `id_sesion`, `id_tipo_procedimiento`, `activo`; único parcial; trigger diferido de "al menos un procedimiento"); `sesion_insumos` con único parcial
  por sesión + insumo y cantidad 1–999; trigger `trg_validar_sesion_consulta` (`etapa5`).
- `receta_medicamento`: único parcial por receta + medicamento; trigger diferido (toda receta vigente tiene un medicamento) (`etapa6`).
- **`justificativo_medico.estado`**: de `activo` / `anulado` a **`pendiente` / `emitido` / `anulado`** (por defecto `pendiente`; lo que estaba `activo` pasó a `emitido`) y `dias_reposo` de 1 a 365 (`etapa7`).
- Baja lógica con `activo` e índices únicos parciales con `UPPER()` en los 8 referenciales; `permisos` de las ventanas nuevas (`consulta: anular`, `fichamedica: nuevo`, `odontograma: editar`, `justificativomedico: estado`) (`schema_permisos_consultorio_roles.sql`).

## CUS a actualizar
Lo que la documentación (CUS, secuencias, diagramas de clase) debe decir para coincidir con el sistema. Mismo criterio que "Cambios del DER": primero el cambio, después el CUS afectado.

**Seguridad:** *Mantener Acceso* (contraseña compleja, bloqueo a los 3 intentos con desbloqueo manual y automático a los 15 min, recuperación de contraseña por código, 2FA de 6 dígitos, cierre por inactividad a los 30 min con aviso, validación de IP por país, "recordar usuario", alertas por correo y auditoría de cada intento);
*Mantener Usuario* (CI y correo salen de la persona vinculada; cambio de cédula con confirmación); *Roles y Permisos* (acciones `ver` / `nuevo` / `editar` / `anular` / `estado` / `desbloquear`; ventanas exclusivas del Administrador); *Auditoría* (consulta, filtros, exportación a PDF y CSV, alertas, inmutabilidad) y *Copias de seguridad*.

**Agendamiento:** *Registrar Agenda*, *Gestionar Cita*, *Avisos* e *Historial* con baja lógica (anular ≠ eliminar); el médico se da de baja de forma lógica con mensaje de "en uso" (pendiente de código).

**Consultorio:**
- *Los 6 CUS de referenciales de Consultorio* (Tipo Tratamiento, Tipo Insumo, Tipo Procedimiento, Medicamentos, Tipo Estudio, Tipo Análisis): **sin Código** (solo ID interno), descripción en mayúsculas, baja lógica con "Mostrar inactivos" y "Reactivar", baja bloqueada si está en uso, auditoría; Tipo Tratamiento con precio e IVA;
  Insumo y Medicamento con presentación. *Tipo Diagnóstico* y *Síntomas* también con baja lógica.
- *Registrar Consulta*: parte de una cita Confirmada sin consulta, la registra un funcionario (la sesión), estados `programada` → `en_proceso` → `finalizada` | `cancelada`, cancelada ≠ anulada (la cita pasa a Cancelado / vuelve a Confirmado), no se anula con datos clínicos asociados.
- *Gestión Ficha Médica*: una por consulta, rangos clínicos aprobados, IMC calculado, solo el médico de la consulta.
- *Gestionar Diagnóstico*: tipo y descripción obligatorios, **síntomas por selección múltiple (al menos uno)**, pieza FDI opcional, fecha del servidor, no se anula con tratamiento vigente.
- *Gestionar Odontograma*: **uno por consulta con precarga del último vigente del paciente**, hallazgos por pieza FDI, superficie y estado dental (de superficie o de pieza completa), sin duplicados vigentes, quitar un hallazgo es baja lógica, solo Activo / Anulado.
- *Gestionar Tratamientos*: desde una consulta activa, estados `pendiente` → `en_seguimiento` → `finalizado` | `cancelado` (finaliza el médico; no se anula con sesiones ni factura), la facturación de tratamientos desde Facturación.
- ***Gestionar Procedimientos e Insumos Utilizados*: cada sesión se registra en una consulta (mismo paciente y médico que el tratamiento; un tratamiento de varias visitas recibe sesiones en consultas posteriores), una sesión tiene uno o más procedimientos e insumos opcionales con cantidad, solo se anula la última.**
- *Generar Recetas e Indicaciones*, *Generar Orden de Estudios*, *Generar Orden de Análisis*: vínculos opcionales con un diagnóstico vigente y un tratamiento de la misma consulta, **PDF con el contenido y auditoría de cada descarga**, las órdenes avanzan un paso por vez **también con la consulta finalizada**
  (solo el médico), no se cancelan completadas.
- ***Generar Justificativo Médico*: estados `pendiente` → `emitido` | `anulado`; se registra pendiente, "Generar" lo emite (documento oficial) y "Anular" lo anula; el PDF sale con marca BORRADOR (pendiente), sin marca (emitido) o ANULADO; días de reposo de 1 a 365.**
- Transversal: todos los movimientos clínicos los carga el médico de la consulta (Recepción y Administrador no), anulación definitiva, auditoría sin contenido clínico.

**Facturación:** *Apertura y Cierre de Caja* (el cierre cuenta solo el efectivo y resta los reintegros), *Pedido*, *Ventas* (de ítems desde pedido y de tratamiento, factura en PDF, numeración con timbrado), *Cobranzas por forma de cobro* (tarjeta, cheque diferido, transferencia, recibo en PDF), *Nota de Remisión* (entregas
parciales por depósito), *Notas de Crédito y Débito* (reintegro en efectivo, devolución de mercadería), *Arqueo de Caja* con recaudación a depositar y *Cuenta Bancaria*; los 9 referenciales con baja lógica y reactivación.

