# Etapa 4 — Diagnóstico y Odontograma (plan breve, a aprobar)

Rama `consultorio-tabler` (al día con origin: el commit `documentacion` con los planes ya lo subiste vos). **No se modificó nada.** Misma base que la etapa 3: Tabler con el patrón de la
pantalla de Atención, solo el médico de la consulta crea / modifica / anula, consulta `programada` o `en_proceso` revalidada **dentro de la transacción** (consulta bloqueada `FOR UPDATE`),
anulación definitiva, auditoría sin contenido clínico, un médico solo ve lo suyo, "Volver a la consulta", `smoke_*` + test de navegador.

## 1. Lo que hay hoy y no cumple

**Diagnóstico** (`DiagnosticoDao`, `diagnostico_api.py`, `diagnosticos-medicos-index.html` de 1.178 líneas en SB Admin 2)
- Los síntomas son **opcionales** ("puede ir vacía"); se aceptan síntomas y tipo de diagnóstico **inactivos** (solo se verifica que el síntoma exista; el tipo ni eso) y sin `FOR SHARE`.
- **No valida la pieza dental** (texto libre de hasta 10 caracteres) ni la fecha (la manda el navegador).
- La consulta se lee con `FOR SHARE` y solo se rechaza `finalizada`: **una consulta `cancelada` admite diagnósticos**, y no se exige ser el médico de la consulta.
- Anular: sin bloqueo de filas; cuenta como "tratamiento asociado" también uno `cancelado`; no mira `cancelada`.
- Lecturas: el listado y el diagnóstico por paciente piden `diagnostico ver` pero devuelven los de **todos** los médicos; el lookup `GET /diagnosticos-medicos/consulta/<id>` es `@require_login`
  (cualquiera con sesión, incluso el Cajero, lee diagnósticos). Ese lookup lo usan los combos de Tratamiento, Receta, Órdenes y Justificativo. No audita.

**Odontograma** (`OdontogramaDao` —ubicado por error en `referenciales_agendamiento/`—, `odontograma_api.py` de 560 líneas, `odontograma-index.html` de 1.208 líneas)
- Todavía tiene la columna `estado` (Activo / Finalizado / Inactivo) con sus dos índices; la baja usa `activo` y `estado` a la vez.
- Crear: lee la consulta con `FOR UPDATE` pero **admite `cancelada`** y no exige ser el médico de la consulta; la precarga es solo una consulta aparte que el navegador tiene que aplicar (no es atómica) y
  toma "el último" del paciente sin mirar que sea anterior a esta consulta.
- Los hallazgos: `guardarDetalle` **pisa** el existente en vez de rechazar el repetido; agregar / quitar / editar hallazgos **no revalida la consulta** (se puede tocar el odontograma de una consulta
  finalizada); editar y quitar piden `editar`, que la ventana no expone (solo el Administrador podría). La superficie es texto libre de 2 caracteres (la vista solo dibuja O, M, D, L: falta la vestibular) y
  el número de pieza no se valida (FDI). `odontograma.id_paciente` y `odontograma_detalle.id_odontograma` son `CASCADE`. No audita. Lecturas sin límite por médico.
- No hay datos cargados (0 odontogramas, 0 diagnósticos): las migraciones no tocan datos.

## 2. Diagnóstico — qué se hace

- **Reglas al guardar** (una transacción; consulta `FOR UPDATE`, tipo y síntomas `FOR SHARE`): médico de la consulta; consulta `programada`/`en_proceso`; **tipo de diagnóstico activo**; **al menos un
  síntoma** y todos activos (el error nombra cuál está inactivo); descripción obligatoria (hasta 1.000 caracteres); **pieza dental FDI válida** si se carga (permanentes 11–18, 21–28, 31–38, 41–48;
  temporales 51–55, 61–65, 71–75, 81–85); observaciones opcionales (hasta 2.000). Paciente y médico se heredan de la consulta; el código `DX-0001` lo genera el servidor.
- **Anular** (definitiva): médico de la consulta, consulta abierta (`finalizada` y `cancelada` bloquean), y **sin tratamiento vigente** asociado (los `cancelado` no cuentan), todo con la consulta y el
  diagnóstico bloqueados. No hay edición (solo Ver / Nuevo / Anular, como en el CUS).
- **Se siguen mostrando** los diagnósticos viejos aunque su tipo o sus síntomas se hayan anulado después (los listados no filtran por `activo` del tipo ni del síntoma).
- **Privacidad:** un médico solo lee lo de SUS consultas (listado, por paciente y por consulta); Recepción y Cajero no leen (Recepción ya no tiene `diagnostico`); el Administrador lee todo. El lookup por
  consulta pasa de `@require_login` a "cualquiera de las ventanas que lo necesitan" (`diagnostico`, `tratamiento`, `receta`, `ordenestudio`, `ordenanalisis`, `justificativomedico`) más el límite por médico.
- **Auditoría** (`diagnosticos`): ALTA y BAJA con **código DX, N.º de consulta, paciente (CI) y quién; sin tipo, síntomas, descripción, pieza ni observaciones**.
- **Pantalla** `diagnostico-index.html` (Tabler): sin `?consulta=` = listado con filtros (código o paciente, fechas) y `Ver` / `Anular`; con `?consulta=<id>` = la consulta en una tarjeta (con "Volver a la consulta"),
  los diagnósticos de esa consulta y el formulario **Nuevo diagnóstico** (tipo, selector de síntomas con búsqueda y marcas, descripción, pieza dental FDI en un selector agrupado por cuadrante, observaciones).

## 3. Odontograma — qué se hace

- **Uno por consulta, precargado**: al crearlo, el servidor copia en la misma transacción los hallazgos del último odontograma vigente del paciente de una consulta **anterior** (por fecha y hora) y lo
  informa ("precargado desde la consulta CON-…"); si no hay previo, queda vacío. Lo que se cambie no toca el anterior.
- **Se retira la columna `estado`** (más su `CHECK` y los índices `idx_odontograma_estado` y `ux_odontograma_consulta_vigente`): queda `activo` + el único parcial `ux_odontograma_consulta_activo`.
  Se elimina el endpoint `PATCH …/estado`. `odontograma.id_paciente` y `odontograma_detalle.id_odontograma` pasan a `RESTRICT`.
- **Hallazgos** (`odontograma_detalle`): pieza FDI válida (con `CHECK` en la base), superficie en `O` (oclusal/incisal), `V` (vestibular), `L` (lingual/palatina), `M` (mesial), `D` (distal) o `T` (pieza completa),
  y estado dental. **Un registro idéntico (misma pieza + superficie + estado) se rechaza con un mensaje claro** (hoy se pisa). Agregar y quitar hallazgos: solo el médico de la consulta, con la consulta abierta,
  revalidado en la transacción. Se agrega la acción `editar` a la ventana `odontograma` (catálogo y seed del rol Médico) porque agregar / quitar hallazgos es modificar el odontograma.
- **Anular el odontograma** (definitivo): médico de la consulta, consulta abierta; los hallazgos quedan como historial del registro anulado y se puede crear otro (se precarga del último vigente).
- **Visual por piezas FDI** (`odontograma-index.html`, SVG generado en el navegador): arcada superior e inferior con los cuatro cuadrantes (18…11 | 21…28 / 48…41 | 31…38); interruptor para ver la dentición
  temporal (55…51 | 61…65 / 85…81 | 71…75). Cada pieza se dibuja con sus 5 superficies (V arriba, L abajo, M y D a los costados según el cuadrante, O al centro) más un contorno para los hallazgos de pieza
  completa. **El color de cada superficie / pieza sale del estado dental** (`estado_dental.color`, con su símbolo), con leyenda; clic en una pieza abre un panel lateral con sus hallazgos, el selector de estado
  (filtrado según corresponda a pieza o a superficie), la observación y los botones Agregar / Quitar. Todo con `data-*` y funciones de dibujo separadas (`dibujarPieza`, `pintarOdontograma`) y clases CSS propias
  para que Antigravity pueda pulir el diseño sin tocar la lógica.
- **Pantalla**: sin `?consulta=` = listado de odontogramas con filtros y `Ver` / `Anular`; con `?consulta=<id>` = editor de esa consulta (tarjeta de la consulta, "Volver a la consulta", odontograma, panel).
- **Privacidad / auditoría**: lecturas limitadas al médico de la consulta (el Administrador lee); auditoría de `odontograma`: ALTA (con la consulta de origen de la precarga), MODIFICACION ("odontograma modificado",
  una por cambio, **sin piezas, superficies ni estados**) y BAJA.

## 4. Archivos

**Base de datos** — nuevo `app/dao/referenciales_consultorio/schema_consultorio_etapa4.sql` (idempotente, con backup y corrida doble; `schema_consultorio_base.sql` y su test se actualizan):
quita `odontograma.estado` y sus índices; FKs a `RESTRICT`; `CHECK` de superficie (`O V L M D T`) y de pieza FDI en `odontograma_detalle.numero_diente` y en `diagnosticos.pieza_dental`;
`estado_dental.aplica_a` (`PIEZA` / `SUPERFICIE`) con su clasificación; trigger diferido que exige al menos un síntoma por diagnóstico vigente. Seed: `schema_permisos_consultorio_roles.sql` (+ `odontograma: editar` para Médico).

**Backend** — mueve `OdontogramaDao` a `app/dao/referenciales_consultorio/odontograma/`; reescribe `DiagnosticoDao`, `diagnostico_api.py`, `OdontogramaDao`, `odontograma_api.py`; amplía `validadores_clinicos.py`
(pieza FDI, superficie) y `consultorio-validadores.js` (+ casos en `comparar_ficha_js_py.py`); `decorators.py` (+ `require_algun_permiso`); `menu_catalog.py` (+ `editar` en `odontograma`); routes de ambos.

**Vistas (Tabler)** — reemplaza `diagnosticos-medicos-index.html` (1.178 líneas) por `diagnostico-index.html`; reemplaza `odontograma-index.html` (1.208 líneas); en la pantalla de Atención el destino ya viene con `?consulta=`.

**Tests** — `smoke_diagnostico.py`, `smoke_odontograma.py`, `smoke_diag_odo_vistas.py` (acceso por rol y por médico, Tabler, baja real por HTTP con el id de la vista), `browser_diag_odontograma.py` (Edge headless);
se ajustan `smoke_migracion02.py` (usa `estado` del odontograma y el diagnóstico sin síntomas), `smoke_esquema_consultorio.py`, `_fixtures.py` y `smoke_consulta.py` si hace falta. Documentación en CLAUDE.md y `tests/README.md`.

**Commits** — (1) base + backend de Diagnóstico y Odontograma con sus tests; (2) vistas (Diagnóstico, Odontograma visual) + test de navegador + documentación.

## 5. Decisiones de negocio (lista corta, con mi recomendación)

1. **Pieza dental del diagnóstico: ¿obligatoria u opcional?** *Recomiendo opcional* (hay diagnósticos generales —gingivitis, halitosis—), pero si se carga debe ser FDI válida.
2. **Fecha del diagnóstico:** hoy la manda el navegador. *Recomiendo que la fije el servidor (el día en que se registra), sin poder editarla.*
3. **Clasificación de los 22 estados dentales** (dato nuevo, `estado_dental.aplica_a`, para el DER). *Propuesta —corregila si hace falta—:*
   **Superficie:** Caries, Obturación, Incrustación, Sellador, Resina, Amalgama, Fractura. **Pieza completa:** Sano, Extracción Indicada, Extraído, Endodoncia, Corona, Puente, Implante, Prótesis Parcial,
   Prótesis Total, Movilidad, Bolsa Periodontal, Retracción Gingival, Diente Incluido, Diente Temporal, Ausente Congénito.
4. **Quitar un hallazgo mientras la consulta está abierta = borrado del renglón** (el odontograma como registro se anula de forma definitiva; con la consulta finalizada nada cambia). *Recomiendo así*;
   la alternativa es baja lógica por renglón (más historial, más complejidad).
5. **Un odontograma recién creado sin ningún hallazgo (paciente nuevo sin previo) se permite**: el médico lo va completando durante la consulta. *Recomiendo permitirlo* (a diferencia de la ficha, que no admite vacíos).

Con tu aprobación (y tus correcciones a 3) arranco por el commit 1.
