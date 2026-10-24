# Etapa C — Auditoría (consulta, informes y alertas): resumen

## Qué se hizo
1. **Auditoría estructurada** (`schema_auditoria_estructurada.sql`, idempotente): `auditoria_cambios` suma `modulo VARCHAR(30)`, `valores_anteriores JSONB`,
   `valores_nuevos JSONB` (NULL, con `COMMENT ON`), `detalle` pasa a `TEXT` y la acción `EXPORTACION` entra al CHECK. Más la tabla `auditoria_umbrales`
   (una fila, solo lectura para la app) y la vista `v_auditoria_anomalias` (con comentarios y `COMMENT ON`).
2. **Helper central**: `detalle_cambios()` devuelve un `DetalleAuditoria` (un `str` con los campos que cambiaron) y `utils.auditar()` guarda módulo y JSON:
   ALTA solo nuevos, MODIFICACION solo lo que cambió, BAJA / REACTIVACION / CIERRE el estado. **No se tocó ninguna API**: las 19 que auditan siguen igual.
   Si una API arma el texto a mano, se separa con el parser cuando tiene la forma `Campo: A -> B`; si no, queda solo el texto.
3. **Pantalla "Auditoría de Cambios"** (solo Administrador, Tabler): filtros (últimos 7 días por defecto, usuario, módulo, entidad, acción), listado paginado
   de más reciente a más antiguo, modal campo / anterior / nuevo, solo lectura (405 en escritura), buscador general, `menu_catalog` + fila en `menu`, sin
   permisos para otros roles. BAJA se muestra como **"Baja / Anulación"**.
4. **Exportación PDF y CSV** con los filtros, tope de 5.000 filas con aviso, PDF con el estilo de la factura (empresa, filtros, fecha de emisión y usuario),
   CSV UTF-8 con BOM y protegido contra fórmulas. **Cada exportación queda auditada.**
5. **Alertas** con la vista `v_auditoria_anomalias` (5 o más bajas por usuario y día; operaciones fuera de lunes a sábado 07:00 a 20:00; 3 o más
   reactivaciones del mismo registro en 30 días). Umbrales en `auditoria_umbrales`. Sección "Alertas" con badge y cada alerta filtra el listado.
6. **Tablero de Accesos**: migrado a Tabler, mismo filtro de fechas, exportación a PDF y CSV (auditada) y enlace cruzado en ambos sentidos con las fechas elegidas.

## Archivos
Nuevos: `app/Services/auditoria_detalle.py`, `app/Services/auditoria_pdf_service.py`, `app/dao/modulo_seguridad/AuditoriaConsultaDao.py`,
`schema_auditoria_estructurada.sql`, `schema_permisos_auditoria_cambios.sql`, `auditoria_cambios_api.py`, `auditoria_cambios_routes.py`,
`templates/auditoria-cambios-index.html`, `tests/seguridad/smoke_auditoria_consulta.py`, `tests/seguridad/browser_auditoria.py`.
Modificados: `AuditoriaCambiosDao.py`, `AuditoriaDao.py` (+`contar_intentos`), `utils.py`, `auditoria_api.py` (+exportar), `auditoria-index.html` (Tabler),
`menu_catalog.py`, `app/__init__.py`, `schema_usuario_app.sql`, `schema_caja.sql` y `schema_apertura_cierre_caja.sql` (ver "Hallazgos"), `CLAUDE.md`, `tests/README.md`.
Ya aplicado a la base real: `schema_auditoria_estructurada.sql`, `schema_permisos_auditoria_cambios.sql` y `schema_usuario_app.sql`.

## Pruebas
- `smoke_auditoria_consulta.py`: **FALLOS: ninguno** (esquema, permisos de la app, trigger, registro, parser, API, filtros, paginación, PDF/CSV, tope, auditoría
  de las exportaciones, vista de anomalías con umbrales, Tablero). Borra por ID lo que genera (verificado: sin restos).
- `browser_auditoria.py` (Edge headless con `fetch` simulado): **FALLOS: ninguno** en las dos pantallas.
- Regresión completa de los `smoke_*.py`: todos en **ninguno** tras los ajustes de abajo. Primera pasada: fallaron 3 por cambios propios de esta etapa (ver "Hallazgos"),
  ya corregidos y vueltos a correr. No corrí `facturacion/browser_test.py` ni `comparar_js_py.py` (no se tocó nada de lo que cubren).
- **Límite:** no se probó con login real + 2FA en un navegador (las pantallas se probaron con sesión simulada y `fetch` simulado). Conviene mirarlas a mano una vez.

## Hallazgos y ajustes
- **Latente, corregido:** `schema_caja.sql` y `schema_apertura_cierre_caja.sql` rehacían el CHECK de `accion` sin `EXPORTACION` (el de caja ni siquiera tenía `CIERRE`); volver a
  correrlos (lo hace el test de apertura) rompía las exportaciones. Ahora el CHECK de ambos es el completo.
- `smoke_ip_pais.py` buscaba `<th>País</th>` literal en el Tablero viejo (cambió el HTML al migrarlo): ahora busca `País</th>`.
- `smoke_permisos_app.py` exigía CRUD en todas las tablas salvo las dos de auditoría: se agregó `auditoria_umbrales` como tabla de solo lectura (y se verifica).
- Las filas viejas de auditoría (48 al empezar) siguen con módulo y JSON en NULL (la tabla es inmutable): se ven bien porque la pantalla deduce el módulo y arma
  campo / anterior / nuevo desde el texto. El texto de una modificación de campos con `; ` adentro del valor no se puede separar y se muestra como una sola fila "Detalle".
- Las alertas solo miran los últimos 30 días; los datos reales actuales (de pruebas del 23 y 24 de octubre) pueden generar alguna alerta de "fuera de horario".

## Pendiente (anotado en CLAUDE.md)
- Agregar al DER: las 3 columnas, `detalle` TEXT, la acción `EXPORTACION`, `auditoria_umbrales` y `v_auditoria_anomalias`.
- Agendamiento, Consultorio y los ABM de Seguridad (Usuarios, Roles y Permisos) no auditan: se suman al migrarlos a Tabler, con este formato.
- Nada commiteado.
