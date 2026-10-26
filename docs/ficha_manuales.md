# Ficha para manuales — OdontoClinic

Datos tomados del código y de la base (26/10/2026). Mensajes entre comillas = texto exacto del sistema.

## 1. Acceso y seguridad

| Tema | Valor |
|---|---|
| Usuario | CI/RUC de la persona vinculada (funcionario o médico); el navegador recuerda solo el CI/RUC (cookie `oc_usuario`) |
| Código 2FA | 6 dígitos por correo, **5 minutos**, de un solo uso. Sin contador propio de intentos por código: se invalida al usarse o vencer; cada intento inválido o vencido se audita |
| Reenviar código 2FA | No hay botón: se vuelve a iniciar sesión y se genera un código nuevo |
| Intentos hasta bloqueo | **3** contraseñas erróneas → bloqueo de **15 min** (o desbloqueo manual por el Administrador con el permiso `desbloquear`) |
| Mensaje de bloqueo | "Cuenta bloqueada por intentos fallidos. Contactá al administrador o esperá 15 minutos para volver a intentar." |
| Avisos por correo | Código 2FA; alerta de intento fallido (usuario, IP, intento N de 3); alerta de bloqueo al usuario y a los administradores; código de recuperación; recordatorios de citas (respaldo de WhatsApp) |
| Olvidé mi contraseña | Enlace en el login → CI/RUC → código de 6 dígitos por correo, **10 min**, máximo **5** intentos, **60 s** entre envíos. Mensaje: "Si el CI/RUC corresponde a una cuenta activa, enviamos un código de recuperación al correo registrado." Código malo: "Código inválido o vencido. Volvé a solicitar uno si hace falta." |
| País permitido | Solo **PY** (`PAIS_PERMITIDO`). Redes privadas siempre; IP pública sin geolocalizar se permite y se audita. Mensaje: "No es posible acceder al sistema desde esta ubicación." |
| Inactividad | Cierre a los **30 min**; aviso con cuenta regresiva a los **120 s**. Mensaje: "Sesión cerrada por inactividad" |
| Contraseña | Mínimo 8 caracteres, una mayúscula, un número y un símbolo. En Usuarios se ve una lista en vivo (✗ rojo → ✓ verde) y Guardar queda deshabilitado hasta cumplirla; al editar, vacía = conserva la actual. Mensaje del servidor: "La contraseña debe tener: …" (lo que falte) |
| HTTPS | No implementado (decisión documentada) |

## 2. Roles y menú

| Rol | Ventanas que ve (acciones) |
|---|---|
| Administrador | Todas (bypass). Solo él: Gestión de Usuarios, Roles y Permisos, Mantener Menú, Tablero de Administrador, Auditoría de Cambios, Copias de Seguridad e Informes |
| Médico | Agenda, Citas, Avisos, Pacientes, Funcionario, Médicos, Disponibilidad y referenciales de Agendamiento: solo ver. Citas y Consulta: ver + estado. Historial Médico, Diagnósticos, Odontograma, Recetas, Sesiones, Órdenes de estudio y análisis, Justificativo, Fichas y Tratamientos: ver, nuevo, anular (según la ventana; algunas con editar y estado). Referenciales de Consultorio: todo. Referenciales de Facturación: el conjunto heredado (ver pantalla Roles y Permisos) |
| Recepción | Agenda, Citas, Avisos, Disponibilidad: ver, nuevo, anular (Citas y Avisos también estado). Pacientes: ver, nuevo, editar. Consulta: ver, nuevo, anular, estado. Fichas: solo ver. Funcionario y Médicos: solo ver. Clientes, Caja, Depósito, Ítems, Tipo Ítems, Formas de cobro, Marcas y Entidades: ver, nuevo, editar, anular. **Sin datos clínicos** |
| Cajero | Apertura y Cierre de Caja y Arqueo: ver, nuevo, anular, estado. Pedido, Venta, Cobranzas, Remisión y Notas: ver, nuevo, anular. Cliente: ver, nuevo, editar. Referenciales de Facturación: solo ver. Sin Agendamiento, Consultorio ni Seguridad |

La matriz exacta se ve y se edita en **Roles y Permisos** (selector de rol, casillas por columna y por módulo, "Guardar permisos").

**Menú (orden):** Agendamiento (Agenda, Citas, Avisos, Pacientes, Funcionario, Médicos, Historial Médico) · Referenciales Agendamiento (Ciudad, Cargo, Consultorio, Disponibilidad Horaria, Especialidad, Día, Turno) · Referenciales Consultorio (Tipo diagnóstico, Síntomas, Tipo Tratamiento, Tipo Insumo, Tipo Procedimiento Médico, Medicamentos, Tipo Estudio, Tipo Análisis) · Consultorio (Registrar Consulta, Fichas Médicas, Diagnósticos, Odontograma, Tratamientos, Recetas, Orden de Estudios, Orden de Análisis, Justificativo) · Referenciales Facturación (Forma de Cobro, Marca de Tarjeta, Entidad Emisora, Entidad Adherida, Cuenta Bancaria, Tipo Ítems, Ítems, Caja, Depósito, Cliente) · Facturación (Apertura y Cierre de Caja, Pedido Cliente, Ventas, Cobranzas, Nota de Remisión, Notas de Crédito y Débito, Arqueo) · Seguridad (Usuarios, Roles y Permisos, Mantener Menú, Tablero, Auditoría de Cambios, Copias de Seguridad) · Informes.

## 3. Auditoría

| Tema | Detalle |
|---|---|
| Qué registra | `auditoria_acceso`: cada intento de login, 2FA, recuperación, bloqueo/desbloqueo, cierre por inactividad (con IP, país y actor). `auditoria_cambios`: ALTA, MODIFICACION, BAJA, REACTIVACION, CIERRE, EXPORTACION y CONSULTA (visitas a Informes), con usuario, IP, módulo y valores anterior/nuevo |
| Nunca guarda | Contraseña, código 2FA ni contenido clínico |
| Inmutable | Ambas tablas: la aplicación solo lee e inserta |
| Alertas | Más de 5 bajas en un día (umbral 5) · operaciones fuera de lunes–sábado 07:00–20:00 (las exportaciones y consultas de Informes no cuentan) · 3 o más reactivaciones del mismo registro en 30 días. Umbrales en `auditoria_umbrales` |
| Pantallas | Tablero de Administrador (accesos) y Auditoría de Cambios: solo Administrador, filtros, detalle campo anterior/nuevo |
| Exportaciones | PDF o CSV, tope **5.000** filas con aviso; cada exportación queda auditada |

## 4. Copias de seguridad

| Tema | Valor |
|---|---|
| Horario | Diario **23:00** (tarea programada que ejecuta `scripts/backup_diario.bat`; la crea quien administra el servidor) y botón en la pantalla (solo Administrador, auditado) |
| Copias | Formato `pg_dump -Fc`, `odontosisbd_AAAAMMDD_HHMMSS.dump`; se conservan las **7** más recientes |
| Ubicación | `BACKUP_DIR` = `C:\OdontoClinic\backups` (fuera de OneDrive); registro en `backup.log` |
| Cifrado | **No**: las copias no se cifran (la contraseña viaja solo por `PGPASSWORD` del proceso hijo; cuenta de solo lectura `odontoclinic_backup`) |
| Restauración | No desde la pantalla: solo con la guía `docs/backups.md` |

## 5. Informes (solo Administrador, pantalla `/informes`)

| Pestaña | Contenido | Filtros | Exportación |
|---|---|---|---|
| Resumen | Total facturado (neto), saldo por cobrar, citas, tasa de asistencia, consultas, ingresos por día | Fechas, Médico | No |
| Agendamiento | Agendadas, atendidas, canceladas, ausentes y tasas; evolución diaria; por médico; ausentes y reiteradas (2+); canceladas | Fechas, Médico | PDF y Excel |
| Consultorio | Consultas, pacientes distintos y nuevos, promedio diario, diagnósticos, tratamientos, procedimientos, insumos, por médico (sin nombres de pacientes) | Fechas, Médico | PDF y Excel |
| Facturación | Gravado 10 %/5 %, IVA, exentas, total; contado vs. crédito; ventas por día; cobros por forma; cuentas a cobrar; detalle (NC restan, ND suman) | Fechas, Condición | PDF y Excel |
| Auditoría | Accesos exitosos y fallidos, bloqueos e intentos por IP, usuarios con más fallos | Fechas | PDF y Excel |

Fechas: por defecto del día 1 del mes a hoy, Desde ≤ Hasta. Cada visita, consulta y exportación queda auditada (informe y filtros). Montos en guaraníes con punto de miles; Excel con números reales.

## 6. Validaciones por pantalla

Formatos comunes: teléfono nacional (celular `09XX XXX XXX` o línea baja con código de área); montos y cantidades enteros con punto de miles (el servidor recibe el entero sin puntos). Los avisos se clasifican en 5 tipos: obligatorio, caracteres, duplicado, rango y estado.

### Comunes (todas las pantallas con esos campos)

| Validación | Regla | Mensaje exacto |
|---|---|---|
| Teléfono | Celular `^09\d{8}$` o línea baja `^0[2-8]\d{7,8}$`, con o sin espacios | "Ingrese un celular (09XX XXX XXX) o una línea baja con código de área (021 XXX XXXX)." / vacío: "El campo teléfono es obligatorio y no puede estar vacío." |
| Correo | Formato válido, máx. 100 | "El correo no tiene un formato válido." |
| CI/RUC | Cédula 5–10 dígitos o RUC con verificador | "La CI/RUC no es válida: use una cédula (5 a 10 dígitos) o un RUC con verificador (ej. 80012345-0)." / "El dígito verificador del RUC no es válido." |
| Precio | Entero > 0, máx. 999.999.999.999 | "El precio debe ser mayor a 0." / "El precio debe ser un número entero (guaraníes, sin decimales)." |
| Monto | Entero ≥ 0 (o > 0 según pantalla) | "El monto no puede ser negativo." / "El monto debe ser un número entero mayor a 0." |
| Cantidad | Entero ≥ 0 (> 0 en movimientos), máx. 2.147.483.647 | "La cantidad debe ser un número entero mayor a 0." / "La cantidad no puede ser negativa." |
| IVA | 0, 5 o 10 | "El IVA debe ser Exenta (0), 5% o 10%." |
| Texto | Obligatorio, largo máximo, sin caracteres de control | "El campo X es obligatorio y no puede estar vacío." / "El campo X no puede superar los N caracteres." |
| Fechas | AAAA-MM-DD, Desde ≤ Hasta | "Las fechas deben tener el formato AAAA-MM-DD." / "La fecha "desde" no puede ser posterior a "hasta"." |
| Duplicado en referenciales | Descripción única entre activos | "Ya existe un/una … activo/a con …" |

### Referenciales (los 4 módulos)

| Pantalla | Regla | Mensaje exacto |
|---|---|---|
| Facturación: Forma de Cobro, Marca, Entidades, Tipo Ítems, Ítems, Caja, Depósito, Cliente, Cuenta Bancaria | Descripción en MAYÚSCULAS, única entre activos; baja bloqueada si está en uso (409) | "Ya existe … activo con …" / motivo del uso |
| Cuenta Bancaria | Número 5–30, solo números y guiones | "El número de cuenta debe tener entre 5 y 30 caracteres: solo números y guiones." |
| Ítems | Precio > 0; cantidad ≥ 0; sin control de stock → cantidad 0 | "El campo cantidad es obligatorio (use 0 si no hay stock)." |
| Cliente | CI/RUC; teléfono y correo opcionales | mensajes comunes |
| Agendamiento: Paciente, Médico, Funcionario | Nombre, apellido, cédula, fecha de nacimiento, teléfono, dirección, correo obligatorios | "La fecha de nacimiento no puede ser futura." / "La fecha de nacimiento no es válida." |
| Disponibilidad Horaria | El día se calcula desde la fecha; hora fin > inicio; cupos 1–1000; sin superposición | "La hora de fin debe ser posterior a la hora de inicio." / "Los cupos deben estar entre 1 y 1000." / "La fecha elegida es Domingo y ese día no está registrado (o está anulado) en el referencial Día: regístrelo antes de cargar disponibilidades para esa fecha." |
| Día | Uno de los 7 días | "El día debe ser uno de los días de la semana: Lunes, Martes, Miércoles, Jueves, Viernes, Sábado o Domingo." |
| Consultorio | Nombre, dirección, teléfono y correo obligatorios | mensajes comunes |
| Consultorio clínico (8 referenciales) | Descripción única; precio de Tipo Tratamiento > 0 | mensajes comunes |

### Movimientos

| Pantalla | Regla | Mensaje exacto |
|---|---|---|
| Apertura de Caja | Caja obligatoria; monto ≥ 0 | "Debe seleccionar una caja." / "El monto de apertura debe ser un número entero mayor o igual a 0." |
| Pedido Cliente | Cliente activo; al menos un ítem; stock suficiente; total máximo | "Debe seleccionar un cliente." / "El total del pedido supera el importe máximo permitido." / "El pedido ya fue facturado; no se puede anular." |
| Ventas | Pedido o tratamientos; cliente/paciente | "Debe seleccionar un pedido." / "Debe seleccionar al menos un tratamiento." / "Debe seleccionar un paciente." |
| Cobranzas | Cuenta con saldo; al menos una forma; monto > 0 y ≤ saldo | "Debe seleccionar una cuenta a cobrar." / "Debe agregar al menos una forma de cobro." / "La cuenta a cobrar ya está pagada." / "El monto supera el saldo pendiente de Gs. N." |
| Nota de Remisión | Venta, depósito de origen, ítems; fecha de traslado ≥ hoy | "Debe seleccionar una venta." / "Debe seleccionar el depósito de origen." / "Debe indicar al menos un ítem a remitir." / "La fecha de traslado no puede ser anterior a hoy." |
| Notas de Crédito y Débito | Factura, tipo, renglones o devolución | "Debe seleccionar una factura." / "Debe indicar si la nota es de crédito o de débito." / "Debe agregar al menos un renglón a la nota." |
| Arqueo de Caja | Apertura, monto contado de cada forma; observación si hay diferencia | "Debe seleccionar una apertura de caja." / "Debe indicar el monto contado de cada forma de cobro." |
| Agenda | Médico, especialidad, consultorio, fecha; un médico por día; publicar solo disponibilidades del mismo médico y fecha | "Debe seleccionar al menos una disponibilidad." / "Las observaciones no pueden superar los 500 caracteres." |
| Citas | Paciente (buscador por cédula o nombre), agenda, horario con cupo, hora dentro del horario, estado, motivo | "Debe seleccionar el paciente." / "Debe seleccionar un horario de la agenda." / "Paciente no encontrado" |
| Avisos | Cita o paciente (con fecha y hora); mensaje ≤ 1000 | "Debe seleccionar el paciente o la cita." / "El mensaje no puede superar los 1000 caracteres." |
| Consulta y ficha médica | Peso 1–500 kg, talla 30–250 cm, temperatura 30–45 °C, FC 20–250, FR 5–80, presión sistólica/diastólica | "La temperatura debe ser un número entre 30 y 45 (°C), con hasta 2 decimales." / "La presión arterial debe tener el formato sistólica/diastólica (ej.: 120/80)." / "La ficha debe tener al menos un dato." |
| Diagnóstico y tratamiento | Tipo y descripción obligatorios; fecha no futura | "El tipo de diagnóstico es obligatorio." / "La descripción del tratamiento es obligatoria." / "La fecha del tratamiento no puede ser futura." |
| Odontograma | Pieza FDI válida; superficie O, V, L, M, D o T | "La superficie debe ser O (oclusal / incisal), V (vestibular), L (lingual / palatina), M (mesial), D (distal) o T (pieza completa)." |
| Sesiones | Descripción obligatoria; próxima cita ≥ hoy | "La descripción de la sesión es obligatoria." / "La próxima cita no puede ser anterior a hoy." |
| Recetas | Cada medicamento con dosis, frecuencia y duración | "Cada medicamento debe tener dosis, frecuencia y duración." |
| Órdenes y Justificativo | Tipo y motivo obligatorios; días de reposo obligatorios | "Los días de reposo son obligatorios." / "Las indicaciones generales son obligatorias." |
