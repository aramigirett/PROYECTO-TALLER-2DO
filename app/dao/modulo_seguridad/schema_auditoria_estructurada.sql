-- =====================================================================================================================
-- Auditoría de cambios estructurada (Etapa C, Rúbrica 9). Idempotente; se corre como postgres.
--   * auditoria_cambios.modulo              VARCHAR(30) NULL   módulo del sistema al que pertenece la entidad
--   * auditoria_cambios.valores_anteriores  JSONB NULL         {campo: valor} ANTES del cambio (solo lo que cambió)
--   * auditoria_cambios.valores_nuevos      JSONB NULL         {campo: valor} DESPUÉS del cambio (solo lo que cambió)
--   * auditoria_cambios.detalle             VARCHAR(255) -> TEXT (ya no se corta)
--   * acción EXPORTACION en el CHECK (cada exportación de un informe de auditoría queda auditada)
-- Las filas anteriores a este script quedan con modulo y JSON en NULL: no se tocan (la tabla es inmutable, ver
-- trg_auditoria_inmutable); la pantalla deduce su módulo de la entidad y arma el campo/anterior/nuevo desde `detalle`.
-- ALTER TABLE ... ADD COLUMN y ALTER COLUMN TYPE no disparan trg_auditoria_inmutable (es un trigger de fila UPDATE/DELETE).
-- Los privilegios de odontoclinic_app (solo SELECT e INSERT en la tabla) alcanzan las columnas nuevas: son de tabla.
-- ⚠️ Estas columnas no están en el DER: hay que agregarlas.
-- =====================================================================================================================
ALTER TABLE auditoria_cambios ADD COLUMN IF NOT EXISTS modulo             VARCHAR(30);
ALTER TABLE auditoria_cambios ADD COLUMN IF NOT EXISTS valores_anteriores JSONB;
ALTER TABLE auditoria_cambios ADD COLUMN IF NOT EXISTS valores_nuevos     JSONB;
ALTER TABLE auditoria_cambios ALTER COLUMN detalle TYPE TEXT;

ALTER TABLE auditoria_cambios DROP CONSTRAINT IF EXISTS auditoria_cambios_accion_check;
ALTER TABLE auditoria_cambios ADD CONSTRAINT auditoria_cambios_accion_check
    CHECK (accion IN ('ALTA', 'MODIFICACION', 'BAJA', 'REACTIVACION', 'CIERRE', 'EXPORTACION', 'CONSULTA'));   -- CONSULTA: visita a Informes (migración 03)

CREATE INDEX IF NOT EXISTS ix_auditoria_cambios_usuario ON auditoria_cambios (id_usuario, fecha_hora DESC);
CREATE INDEX IF NOT EXISTS ix_auditoria_cambios_modulo  ON auditoria_cambios (modulo, fecha_hora DESC);

COMMENT ON COLUMN auditoria_cambios.modulo IS 'Módulo del sistema de la entidad auditada (p. ej. Módulo Facturación). NULL en las filas anteriores a la Etapa C: se deduce de la entidad.';
COMMENT ON COLUMN auditoria_cambios.valores_anteriores IS 'JSONB {campo: valor} con los valores ANTES del cambio, solo de los campos que cambiaron. NULL en un ALTA y en las filas anteriores a la Etapa C. En BAJA/REACTIVACION lleva el estado.';
COMMENT ON COLUMN auditoria_cambios.valores_nuevos IS 'JSONB {campo: valor} con los valores DESPUÉS del cambio, solo de los campos que cambiaron (en un ALTA, todos los cargados). En BAJA/REACTIVACION lleva el estado.';
COMMENT ON COLUMN auditoria_cambios.detalle IS 'Texto legible del cambio ("Campo: A -> B; ..."). TEXT: no se corta.';

-- =====================================================================================================================
-- UMBRALES de las alertas (una sola fila). Se cambian con un UPDATE como postgres; la aplicación solo los lee.
-- =====================================================================================================================
CREATE TABLE IF NOT EXISTS auditoria_umbrales (
    id_umbral             SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id_umbral = 1),
    max_bajas_dia         SMALLINT NOT NULL DEFAULT 5  CHECK (max_bajas_dia >= 1),
    max_reactivaciones    SMALLINT NOT NULL DEFAULT 3  CHECK (max_reactivaciones >= 2),
    dias_reactivaciones   SMALLINT NOT NULL DEFAULT 30 CHECK (dias_reactivaciones >= 1),
    hora_inicio           TIME     NOT NULL DEFAULT '07:00',
    hora_fin              TIME     NOT NULL DEFAULT '20:00',
    ultimo_dia_laboral    SMALLINT NOT NULL DEFAULT 6  CHECK (ultimo_dia_laboral BETWEEN 1 AND 7),
    ventana_alertas_dias  SMALLINT NOT NULL DEFAULT 30 CHECK (ventana_alertas_dias >= 1),
    CHECK (hora_inicio < hora_fin)
);
INSERT INTO auditoria_umbrales (id_umbral) VALUES (1) ON CONFLICT (id_umbral) DO NOTHING;

COMMENT ON TABLE auditoria_umbrales IS 'Umbrales de v_auditoria_anomalias (una sola fila). Se editan con UPDATE como postgres.';
COMMENT ON COLUMN auditoria_umbrales.max_bajas_dia IS 'Alerta si un usuario hace esta cantidad o más de BAJAS (anulaciones) en un mismo día.';
COMMENT ON COLUMN auditoria_umbrales.max_reactivaciones IS 'Alerta si un mismo registro se reactiva esta cantidad o más de veces dentro de dias_reactivaciones.';
COMMENT ON COLUMN auditoria_umbrales.dias_reactivaciones IS 'Días hacia atrás en que se cuentan las reactivaciones repetidas de un mismo registro.';
COMMENT ON COLUMN auditoria_umbrales.hora_inicio IS 'Inicio del horario laboral (inclusive).';
COMMENT ON COLUMN auditoria_umbrales.hora_fin IS 'Fin del horario laboral (exclusive): desde esa hora una operación es "fuera de horario".';
COMMENT ON COLUMN auditoria_umbrales.ultimo_dia_laboral IS 'Último día laboral de la semana en ISO (1 = lunes ... 7 = domingo). 6 = lunes a sábado.';
COMMENT ON COLUMN auditoria_umbrales.ventana_alertas_dias IS 'Las alertas solo miran los últimos N días (las anteriores dejan de mostrarse).';

-- La aplicación no debe poder cambiar sus propios umbrales: solo lectura.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'odontoclinic_app') THEN
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON auditoria_umbrales FROM odontoclinic_app;
        GRANT SELECT ON auditoria_umbrales TO odontoclinic_app;
    END IF;
END $$;

-- =====================================================================================================================
-- VISTA: v_auditoria_anomalias
-- Propósito : señales de uso anómalo sobre auditoria_cambios para el Administrador (sección "Alertas" de la pantalla
--             Auditoría de Cambios). Una fila por alerta; solo mira los últimos ventana_alertas_dias días.
-- Tipos     : BAJAS_EN_EL_DIA          un usuario con max_bajas_dia o más BAJAS (anulaciones) en un mismo día.
--             FUERA_DE_HORARIO         un usuario con operaciones (no exportaciones ni consultas de Informes) fuera del horario laboral en un día
--                                      (antes de hora_inicio, desde hora_fin o después de ultimo_dia_laboral).
--             REACTIVACIONES_REPETIDAS un mismo registro (entidad + id) reactivado max_reactivaciones o más veces en
--                                      dias_reactivaciones días.
-- Columnas  : tipo, id_usuario, usuario, fecha_desde, fecha_hasta (para filtrar el listado), entidad e id_registro (solo
--             en reactivaciones), accion (filtro sugerido, NULL = todas), cantidad, descripcion.
-- Umbrales  : tabla auditoria_umbrales (una fila).
-- =====================================================================================================================
CREATE OR REPLACE VIEW v_auditoria_anomalias AS
WITH u AS (SELECT * FROM auditoria_umbrales WHERE id_umbral = 1),
nombres AS (
    SELECT us.id_usuario,
           COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido, 'Usuario ' || us.id_usuario) AS nombre
    FROM usuarios us
    LEFT JOIN funcionario f ON f.id_funcionario = us.id_funcionario
    LEFT JOIN medico m ON m.id_medico = us.id_medico
),
bajas AS (
    SELECT 'BAJAS_EN_EL_DIA'::varchar(30) AS tipo, a.id_usuario, a.fecha_hora::date AS fecha_desde,
           a.fecha_hora::date AS fecha_hasta, NULL::varchar(50) AS entidad, NULL::integer AS id_registro,
           'BAJA'::varchar(20) AS accion, count(*)::integer AS cantidad,
           'Realizó ' || count(*) || ' bajas/anulaciones el mismo día (umbral: ' || u.max_bajas_dia || ').' AS descripcion
    FROM auditoria_cambios a CROSS JOIN u
    WHERE a.accion = 'BAJA' AND a.fecha_hora >= CURRENT_DATE - u.ventana_alertas_dias
    GROUP BY a.id_usuario, a.fecha_hora::date, u.max_bajas_dia
    HAVING count(*) >= u.max_bajas_dia
),
fuera AS (
    SELECT 'FUERA_DE_HORARIO'::varchar(30) AS tipo, a.id_usuario, a.fecha_hora::date AS fecha_desde,
           a.fecha_hora::date AS fecha_hasta, NULL::varchar(50) AS entidad, NULL::integer AS id_registro,
           NULL::varchar(20) AS accion, count(*)::integer AS cantidad,
           count(*) || ' operaciones fuera del horario laboral (' || to_char(u.hora_inicio, 'HH24:MI') || ' a '
               || to_char(u.hora_fin, 'HH24:MI') || ', hasta el día ' || u.ultimo_dia_laboral || ' de la semana), entre las '
               || to_char(min(a.fecha_hora), 'HH24:MI') || ' y las ' || to_char(max(a.fecha_hora), 'HH24:MI') || '.' AS descripcion
    FROM auditoria_cambios a CROSS JOIN u
    WHERE a.accion NOT IN ('EXPORTACION', 'CONSULTA')
      AND a.fecha_hora >= CURRENT_DATE - u.ventana_alertas_dias
      AND (EXTRACT(ISODOW FROM a.fecha_hora) > u.ultimo_dia_laboral
           OR a.fecha_hora::time < u.hora_inicio OR a.fecha_hora::time >= u.hora_fin)
    GROUP BY a.id_usuario, a.fecha_hora::date, u.hora_inicio, u.hora_fin, u.ultimo_dia_laboral
),
reactiv AS (
    SELECT 'REACTIVACIONES_REPETIDAS'::varchar(30) AS tipo,
           (array_agg(a.id_usuario ORDER BY a.fecha_hora DESC))[1] AS id_usuario,
           min(a.fecha_hora)::date AS fecha_desde, max(a.fecha_hora)::date AS fecha_hasta,
           a.entidad::varchar(50) AS entidad, a.id_registro, 'REACTIVACION'::varchar(20) AS accion,
           count(*)::integer AS cantidad,
           'El registro ' || a.entidad || ' #' || a.id_registro || ' se reactivó ' || count(*) || ' veces en '
               || u.dias_reactivaciones || ' días (umbral: ' || u.max_reactivaciones || ').' AS descripcion
    FROM auditoria_cambios a CROSS JOIN u
    WHERE a.accion = 'REACTIVACION' AND a.fecha_hora >= CURRENT_DATE - u.dias_reactivaciones
      AND a.fecha_hora >= CURRENT_DATE - u.ventana_alertas_dias
    GROUP BY a.entidad, a.id_registro, u.dias_reactivaciones, u.max_reactivaciones
    HAVING count(*) >= u.max_reactivaciones
)
SELECT t.tipo, t.id_usuario, n.nombre AS usuario, t.fecha_desde, t.fecha_hasta, t.entidad, t.id_registro, t.accion,
       t.cantidad, t.descripcion
FROM (SELECT * FROM bajas UNION ALL SELECT * FROM fuera UNION ALL SELECT * FROM reactiv) t
LEFT JOIN nombres n ON n.id_usuario = t.id_usuario;

COMMENT ON VIEW v_auditoria_anomalias IS 'Alertas de uso anómalo de auditoria_cambios: muchas bajas en un día, operaciones fuera de horario y reactivaciones repetidas. Umbrales en auditoria_umbrales.';
COMMENT ON COLUMN v_auditoria_anomalias.tipo IS 'BAJAS_EN_EL_DIA | FUERA_DE_HORARIO | REACTIVACIONES_REPETIDAS.';
COMMENT ON COLUMN v_auditoria_anomalias.fecha_desde IS 'Primer día de la alerta (filtro "desde" del listado).';
COMMENT ON COLUMN v_auditoria_anomalias.fecha_hasta IS 'Último día de la alerta (filtro "hasta" del listado).';
COMMENT ON COLUMN v_auditoria_anomalias.cantidad IS 'Cantidad de operaciones que disparan la alerta.';

-- La vista es solo lectura para la aplicación (mismo criterio que el resto de las vistas).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'odontoclinic_app') THEN
        REVOKE ALL ON v_auditoria_anomalias FROM odontoclinic_app;
        GRANT SELECT ON v_auditoria_anomalias TO odontoclinic_app;
    END IF;
END $$;
