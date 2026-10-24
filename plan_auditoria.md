# Etapa C — Auditoría (consulta, informes y alertas): relevamiento y plan

## 1. Relevamiento

### Estructura de `auditoria_cambios`
- Columnas: `id_auditoria_cambio`, `fecha_hora`, `id_usuario`, `entidad`, `id_registro`, `accion`, `detalle VARCHAR(255)`, `ip`.
- **No hay columna de módulo.** Se deriva de `entidad` con un mapa en código.
- **No hay valores anterior/nuevo estructurados.** Todo va en `detalle` como texto libre armado por `detalle_cambios()`:
  - Modificación: `"Teléfono: A -> B; Correo: X -> Y"` (solo lo que cambió).
  - Alta / baja / reactivación: `"Campo: valor; ..."`.
  - Se corta a 255 caracteres.
- CHECK de acción actual: `ALTA`, `MODIFICACION`, `BAJA`, `REACTIVACION`, `CIERRE`. **`ANULACION` no existe**: las anulaciones se registran como `BAJA`.
- Ya es inmutable: trigger `trg_auditoria_inmutable` y la app solo tiene `SELECT`/`INSERT`.
- Hoy: 48 filas, 21 combinaciones entidad/acción.

### Quién registra hoy (19 APIs)
- **Referenciales de Facturación:** Forma de Cobro, Marca de Tarjeta, Entidad Emisora, Entidad Adherida, Tipo Ítems, Ítems, Caja, Depósito, Cliente, Cuenta Bancaria.
- **Movimientos de Facturación:** Apertura/Cierre de Caja, Pedido Cliente, Venta (`venta_cab`), Cobro (`cobro_cab`), Remisión (`nota_remision_cab`), Notas de Crédito/Débito, Arqueo (`arqueo_caja`, `recaudacion_depositar`).
- **Seguridad:** solo Backup (`id_registro = 0`).

### Quién NO registra (se anota en CLAUDE.md; se suma en la migración a Tabler)
- **Agendamiento:** Paciente, Médico, Funcionario, Agenda cabecera/detalle, Cita, Avisos y Recordatorios, Historial; referenciales Ciudad, Cargo, Consultorio, Disponibilidad Horaria, Especialidad, Día, Turno.
- **Consultorio:** los 10 movimientos (Consulta, Diagnóstico, Ficha Médica, Odontograma, Tratamiento, Sesiones/Insumos, Receta, Orden de Estudios, Orden de Análisis, Justificativo) y los 8 referenciales.
- **Seguridad:** alta/edición/baja de Usuarios y Roles y Permisos (los accesos sí van a `auditoria_acceso`, otra tabla).

### Tablero actual de accesos
`auditoria_api.py` (45 líneas) y `auditoria-index.html` (135 líneas, SB Admin 2). Ya tiene filtro de fechas y de resultado.

## 2. Plan

1. **Detalle campo / anterior / nuevo, sin migrar datos.** Parser en Python (`auditoria_detalle.py`) que convierte `detalle` en filas, usado por pantalla, PDF y CSV.
   - `A -> B` → anterior y nuevo.
   - `Campo: valor` → solo "nuevo".
   - Si no se puede separar o quedó cortado a 255 caracteres → una fila "Detalle" con el texto completo.
   - No se cambia el esquema de `auditoria_cambios` ni cómo auditan los 19 módulos.
2. **Pantalla "Auditoría de Cambios"** (`base_tabler.html`, solo Administrador).
   - Carpeta `app/rutas/modulo_seguridad/auditoria_cambios/` (routes, API, template); mismo patrón que Copias de Seguridad (`solo_admin`).
   - Entrada en `menu_catalog.py`, fila en `menu` y seed `schema_permisos_auditoria_cambios.sql`. Sin permisos para otros roles. El buscador general la encuentra.
   - Filtros: fechas (últimos 7 días por defecto), usuario, módulo, entidad, acción.
   - Listado paginado, del más reciente al más antiguo: fecha y hora, usuario, IP, módulo, entidad, id de registro, acción. Modal de detalle campo / anterior / nuevo.
   - API solo `GET`: ninguna acción modifica la auditoría.
3. **Exportación PDF y CSV** con los filtros aplicados.
   - PDF: `auditoria_pdf_service.py` (ReportLab, mismo estilo que la factura): empresa, filtros, fecha de emisión y usuario. Patrón `calcular_datos` / `dibujar` / `generar`.
   - CSV con BOM UTF-8 para Excel.
   - Cada exportación se audita: `entidad='auditoria_cambios'`, acción `EXPORTACION` (se amplía el CHECK), con formato y filtros en el detalle.
   - Tope de 5.000 filas por exportación, con aviso si se recorta.
4. **Alertas:** vista `v_auditoria_anomalias` (`schema_auditoria_anomalias.sql`, con comentarios y `COMMENT ON`).
   - Muchas bajas por usuario y día.
   - Operaciones fuera del horario laboral.
   - Reactivaciones repetidas de un mismo registro.
   - Umbrales en una tabla de parámetros de una sola fila (cambiables con `UPDATE`).
   - Sección "Alertas" arriba de la pantalla, con badge de cantidad; cada alerta aplica el filtro correspondiente al listado.
5. **Tablero de Accesos:** misma barra de fechas, exportación PDF y CSV (también auditada) y enlace cruzado en ambos sentidos con Auditoría de Cambios. Migración a Tabler.
6. **Tests y documentación**
   - `tests/seguridad/smoke_auditoria_consulta.py`: permisos, filtros, parser, paginación, PDF y CSV, auditoría de la exportación, vista de anomalías, inmutabilidad.
   - Regresión completa.
   - CLAUDE.md: estado de la rúbrica 9 y lista de módulos sin auditoría.
   - `resumen_auditoria.md` sin commitear.

## 3. Decisiones de negocio (propuesta por defecto)

| # | Pregunta | Propuesta |
|---|---|---|
| 1 | Horario laboral | Lunes a sábado, 07:00 a 20:00; fuera de eso se alerta |
| 2 | Umbrales | 5 o más bajas por usuario y día; 3 o más reactivaciones del mismo registro en 30 días |
| 3 | Anulaciones | Tratar `BAJA` como "anulación" (sin acción nueva; evita tocar los 9 movimientos) |
| 4 | Tablero de Accesos | Migrarlo a Tabler |
| 5 | Exportación | Tope de 5.000 filas con aviso |
