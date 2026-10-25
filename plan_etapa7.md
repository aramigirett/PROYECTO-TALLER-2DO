# Etapa 7 — Justificativo Médico y cierre del módulo Consultorio

## Relevamiento
**Justificativo hoy.** Tabla `justificativo_medico` (consulta NOT NULL, `id_diagnostico` NULL, `dias_reposo` CHECK > 0, `recomendaciones` NULL, `fecha_justificativo`, `estado` CHECK `activo`/`anulado`; 1 fila real). DAO + API + vista **SB Admin 2 + jQuery (455 líneas, la única de las 18 pantallas que no es Tabler)** + `justificativo_pdf_service.py` (101 líneas, sin clínica ni especialidad). Mismos problemas que tenían las etapas 3 a 6: alta sin bloqueo de la consulta, sin `FOR SHARE` del diagnóstico, no valida que quien carga sea el médico de la consulta, lecturas abiertas, sin auditoría, sin N.º de documento, PDF sin auditar.
**Contradicción con las reglas:** el análisis dice "estado inicial Pendiente"; la tabla solo admite `activo` / `anulado` y un justificativo se emite en el acto (no hay flujo que lo "avance"). **Recomiendo mantener `activo` / `anulado`** (la acción es generar o anular, como dice la misma regla) y mostrar "Vigente" / "Anulado"; si querés "Pendiente" de verdad habría que definir qué lo hace pasar a otro estado.
**Las 18 pantallas de Consultorio:** 17 ya están en Tabler (8 referenciales, Consulta, Atención, Fichas, Diagnóstico, Odontograma, Tratamiento, Sesiones, Receta, Órdenes ×2 comparten plantilla); queda el Justificativo. Aparte, **"Historial Médico"** (movimiento de Agendamiento que se ubica en el menú de Consultorio) sigue en SB Admin 2: no es de las 18 ni de este módulo, no lo toco (queda para la migración de Agendamiento).
**Candidatos a eliminar (sin consumidor en vistas ni JS; confirmo uno por uno antes de borrar):** `GET /odontogramas/paciente/<id>` y `GET /diagnosticos-medicos/paciente/<id>` (+ sus métodos de DAO), `GET /sesiones-tratamiento/tratamiento/<id>` (la vista lee las sesiones del detalle del tratamiento; solo lo usa un test), `justificativo_pdf_service.py` (lo reemplaza el servicio común) y lo que aparezca en el barrido de cierre (plantillas sin ruta: hoy ninguna; métodos de DAO sin uso: hoy ninguno).
**Esquema:** `smoke_esquema_consultorio` ya compara las 23 tablas, constraints, índices y estados dentales contra una base temporal reconstruida; **no compara funciones ni todos los triggers** (los de diagnóstico, sesión, receta) ni comentarios: se completa.

## Decisiones de negocio a aprobar (Parte A)
1. **Estado:** `activo` / `anulado` (ver arriba). Anulación definitiva, con el documento aún descargable con la marca **ANULADO**.
2. **Quién y cuándo:** solo el médico de la consulta, consulta `programada` / `en_proceso` revalidada en la transacción (consulta `FOR UPDATE`); Recepción sin acceso, Administrador solo lectura; **no se anula con la consulta finalizada**; un médico solo ve los de SUS consultas.
3. **Contenido:** días de reposo entero **1 a 365** (CHECK en la base), recomendaciones opcionales (hasta 2.000), diagnóstico opcional vigente de la misma consulta (`FOR SHARE`; sin tratamiento, como dice el CUS). Fecha del documento fijada por el servidor (hoy).
4. **N.º `JUS-0000012`** derivado del id, sin columnas nuevas.
5. **PDF** en el servicio común (`documento_clinico_pdf_service.py`, tipo `justificativo`): clínica, título, N.º, fecha, paciente con CI, médico con especialidad (y registro si lo tiene), "se indica reposo por N día(s) a partir del dd/mm/aaaa", recomendaciones, firma y marca ANULADO; **cada descarga auditada como `EXPORTACION`**; se elimina `justificativo_pdf_service.py`.
6. **Auditoría sin contenido clínico:** ALTA / BAJA / EXPORTACION con N.º, consulta y paciente con CI; nunca los días de reposo ni las recomendaciones.

## Parte B — cierre (qué voy a hacer)
1. **Barrido de lo viejo:** plantillas, endpoints, métodos de DAO, JS y servicios de Consultorio sin uso → los elimino y te paso la lista exacta.
2. **`smoke_permisos_consultorio.py`:** matriz Médico / Recepción / Cajero / Administrador × las 18 pantallas (vista) y cada acción (ver, nuevo, editar, anular, estado, PDF) con el código esperado, incluido "un médico solo ve lo suyo" (listado, detalle, PDF y lookups) y "Administrador solo lectura clínica". Se arma a partir del catálogo `menu_catalog.py` y falla si aparece una ventana de Consultorio que la matriz no cubre.
3. **`smoke_auditoria_consultorio.py`:** todas las entidades de Consultorio con módulo y JSON; barrido estático (cada POST / PUT / PATCH / DELETE de `modulo_consultorio` audita) y dinámico (una operación por entidad con marcadores secretos: ninguna fila los contiene).
4. **Esquema:** ampliar `smoke_esquema_consultorio` (funciones, todos los triggers, comentarios, secuencias) y verificar que `schema_consultorio_base.sql` en una base vacía coincide con la real.
5. **CLAUDE.md:** estado final de Consultorio; sección única **"Cambios del DER pendientes de reflejar"** (Seguridad, Facturación y Consultorio: hoy hay ~15 avisos ⚠️ repartidos) y **"CUS a actualizar"**.
6. **Regresión completa** (todos los módulos y los 6 navegadores simulados).
7. **Merge a `main` y push: solo después de tu prueba y tu confirmación.**

## Archivos y commits (de corrido)
**Commit 1 — Justificativo (base, backend y PDF):** `schema_consultorio_etapa7.sql` (CHECK 1–365, textos), `JustificativoMedicoDao` y `justificativo_medico_api.py` reescritos sobre `documento_clinico.py` (`PREFIJO_JUSTIFICATIVO`), tipo `justificativo` en el servicio de PDF, validadores `validar_justificativo` + espejo JS (casos en el comparador), tests `smoke_justificativo.py` y ampliación de `smoke_pdf_documentos.py`.
**Commit 2 — Justificativo (vista):** `justificativo-medico-index.html` en Tabler (patrón de las etapas 5 y 6), test `smoke_justificativo_vistas.py` + escenarios en `browser_documentos.py`.
**Commit 3 — Cierre:** barrido y eliminaciones, `smoke_permisos_consultorio.py`, `smoke_auditoria_consultorio.py`, esquema ampliado, CLAUDE.md, `tests/README.md`.
**No se commitea:** `plan_etapa7.md`.
