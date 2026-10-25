-- Módulo Consultorio: estructura completa (23 tablas) para reconstruir la base desde cero. Idempotente (CREATE ... IF NOT EXISTS);
-- se corre como postgres con PGCLIENTENCODING=UTF8. Generada a partir de la base real `odontosisbd` (etapa 0 de la migración a Tabler).
--
-- DEPENDE de las tablas de Agendamiento y Seguridad (paciente, medico, funcionario, consultorio, cita_detalle, usuarios), que se
-- crean antes (sus CREATE TABLE tampoco están versionados todavía). Después de este script: schema_tipo_tratamiento_precio.sql y
-- schema_tipo_tratamiento_iva.sql (seed de tratamientos), schema_permisos_*.sql y schema_usuario_app.sql (permisos de la app).
--
-- Una base que ya existe NO necesita este script: usa schema_consultorio_etapa0.sql. `consultas_detalle` ya no existe (superada por
-- Diagnóstico, Tratamiento y Sesiones). `odontograma.estado` se retira en la etapa 4 (queda solo `activo`).

CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS consultas_cab (
    id_consulta_cab SERIAL,
    id_cita integer NOT NULL,
    id_paciente integer NOT NULL,
    id_medico integer NOT NULL,
    id_consultorio integer NOT NULL,
    id_funcionario integer NOT NULL,
    fecha_cita date NOT NULL,
    hora_cita time without time zone NOT NULL,
    duracion_minutos integer,
    estado character varying(20) DEFAULT 'programada'::character varying,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    activo boolean DEFAULT true,
    CONSTRAINT chk_estado_consulta CHECK (((estado)::text = ANY ((ARRAY['programada'::character varying, 'en_proceso'::character varying, 'finalizada'::character varying, 'cancelada'::character varying])::text[]))),
    CONSTRAINT consultas_cab_pkey PRIMARY KEY (id_consulta_cab),
    CONSTRAINT chk_consulta_duracion CHECK (duracion_minutos IS NULL OR duracion_minutos BETWEEN 1 AND 480),
    CONSTRAINT fk_consulta_cita FOREIGN KEY (id_cita) REFERENCES cita_detalle(id_cita_detalle) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_consulta_consultorio FOREIGN KEY (id_consultorio) REFERENCES consultorio(codigo),
    CONSTRAINT fk_consulta_funcionario FOREIGN KEY (id_funcionario) REFERENCES funcionario(id_funcionario) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_consulta_medico FOREIGN KEY (id_medico) REFERENCES medico(id_medico),
    CONSTRAINT fk_consulta_paciente FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente)
);
CREATE INDEX IF NOT EXISTS idx_consulta_fecha ON consultas_cab USING btree (fecha_cita);
CREATE INDEX IF NOT EXISTS idx_consulta_medico ON consultas_cab USING btree (id_medico);
CREATE INDEX IF NOT EXISTS idx_consulta_paciente ON consultas_cab USING btree (id_paciente);
CREATE UNIQUE INDEX IF NOT EXISTS uk_consulta_cita_activa ON consultas_cab USING btree (id_cita) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS estado_dental (
    id_estado_dental SERIAL,
    descripcion character varying(100) NOT NULL,
    color character varying(7) NOT NULL,
    simbolo character varying(10),
    activo boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    aplica_a character varying(10) DEFAULT 'PIEZA' NOT NULL,
    CONSTRAINT chk_estado_dental_aplica_a CHECK (aplica_a IN ('PIEZA', 'SUPERFICIE')),
    CONSTRAINT estado_dental_pkey PRIMARY KEY (id_estado_dental),
    CONSTRAINT estado_dental_descripcion_key UNIQUE (descripcion)
);

CREATE TABLE IF NOT EXISTS insumos (
    id_insumo SERIAL,
    descripcion character varying(200) NOT NULL,
    presentacion character varying(100),
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    activo boolean DEFAULT true,
    CONSTRAINT insumos_pkey PRIMARY KEY (id_insumo)
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_insumos_descripcion ON insumos USING btree (upper((descripcion)::text)) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS medicamentos (
    id_medicamento integer GENERATED ALWAYS AS IDENTITY,
    nombre_comercial character varying(200) NOT NULL,
    presentacion character varying(100),
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    activo boolean DEFAULT true,
    CONSTRAINT medicamentos_pkey PRIMARY KEY (id_medicamento)
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_medicamento_nombre_comercial ON medicamentos USING btree (upper((nombre_comercial)::text)) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS sintoma (
    id_sintoma SERIAL,
    descripcion_sintoma character varying(255) NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT sintoma_pkey PRIMARY KEY (id_sintoma)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_sintoma_descripcion_activo ON sintoma USING btree (upper((descripcion_sintoma)::text)) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS tipo_analisis (
    id_tipo_analisis integer GENERATED ALWAYS AS IDENTITY,
    descripcion character varying(200) NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    activo boolean DEFAULT true,
    CONSTRAINT tipo_analisis_pkey PRIMARY KEY (id_tipo_analisis)
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_tipo_analisis_descripcion ON tipo_analisis USING btree (upper((descripcion)::text)) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS tipo_diagnostico (
    id_tipo_diagnostico SERIAL,
    descripcion_diagnostico character varying(150) NOT NULL,
    tipo_diagnostico character varying(100) NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT tipo_diagnostico_pkey PRIMARY KEY (id_tipo_diagnostico)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_tipo_diagnostico_descripcion_activo ON tipo_diagnostico USING btree (upper((descripcion_diagnostico)::text)) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS tipo_estudio (
    id_tipo_estudio integer GENERATED ALWAYS AS IDENTITY,
    descripcion character varying(200) NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    activo boolean DEFAULT true,
    CONSTRAINT tipo_estudio_pkey PRIMARY KEY (id_tipo_estudio)
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_tipo_estudio_descripcion ON tipo_estudio USING btree (upper((descripcion)::text)) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS tipo_procedimiento_medico (
    id_tipo_procedimiento integer GENERATED ALWAYS AS IDENTITY,
    descripcion character varying(200) NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    activo boolean DEFAULT true,
    CONSTRAINT tipo_procedimiento_medico_pkey PRIMARY KEY (id_tipo_procedimiento)
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_tipo_proc_descripcion ON tipo_procedimiento_medico USING btree (upper((descripcion)::text)) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS tipos_tratamiento (
    id_tipo_tratamiento SERIAL,
    descripcion character varying(200) NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    activo boolean DEFAULT true,
    precio numeric(12,0) NOT NULL,
    iva smallint DEFAULT 10 NOT NULL,
    CONSTRAINT chk_tipos_tratamiento_iva CHECK ((iva = ANY (ARRAY[0, 5, 10]))),
    CONSTRAINT chk_tipos_tratamiento_precio CHECK ((precio > (0)::numeric)),
    CONSTRAINT tipos_tratamiento_pkey PRIMARY KEY (id_tipo_tratamiento)
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_tipo_trat_descripcion ON tipos_tratamiento USING btree (upper((descripcion)::text)) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS diagnosticos (
    id_diagnostico SERIAL,
    codigo character varying(20),
    id_paciente integer NOT NULL,
    id_medico integer NOT NULL,
    id_tipo_diagnostico integer NOT NULL,
    descripcion_diagnostico text NOT NULL,
    pieza_dental character varying(10),
    fecha_diagnostico date NOT NULL,
    observaciones text,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    id_usuario_registro integer,
    activo boolean DEFAULT true,
    id_consulta_cab integer NOT NULL,
    CONSTRAINT diagnosticos_pkey PRIMARY KEY (id_diagnostico),
    CONSTRAINT chk_diagnostico_pieza_fdi CHECK (
        pieza_dental IS NULL OR pieza_dental ~ '^(1[1-8]|2[1-8]|3[1-8]|4[1-8]|5[1-5]|6[1-5]|7[1-5]|8[1-5])$'),
    CONSTRAINT chk_diagnostico_descripcion CHECK (btrim(descripcion_diagnostico) <> ''),
    CONSTRAINT diagnosticos_codigo_key UNIQUE (codigo),
    CONSTRAINT fk_diag_consulta FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON DELETE RESTRICT,
    CONSTRAINT fk_diag_medico FOREIGN KEY (id_medico) REFERENCES medico(id_medico),
    CONSTRAINT fk_diag_paciente FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente),
    CONSTRAINT fk_diag_tipo FOREIGN KEY (id_tipo_diagnostico) REFERENCES tipo_diagnostico(id_tipo_diagnostico),
    CONSTRAINT fk_diag_usuario_registro FOREIGN KEY (id_usuario_registro) REFERENCES usuarios(id_usuario) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_diag_consulta ON diagnosticos USING btree (id_consulta_cab);
CREATE INDEX IF NOT EXISTS idx_diag_fecha ON diagnosticos USING btree (fecha_diagnostico);
CREATE INDEX IF NOT EXISTS idx_diag_medico ON diagnosticos USING btree (id_medico);
CREATE INDEX IF NOT EXISTS idx_diag_paciente ON diagnosticos USING btree (id_paciente);
CREATE INDEX IF NOT EXISTS idx_diag_tipo ON diagnosticos USING btree (id_tipo_diagnostico);

CREATE TABLE IF NOT EXISTS ficha_medica_consulta (
    id_ficha_medica SERIAL,
    id_consulta_cab integer NOT NULL,
    presion_arterial character varying(20),
    temperatura numeric(4,2),
    frecuencia_cardiaca integer,
    frecuencia_respiratoria integer,
    peso numeric(5,2),
    talla numeric(5,2),
    imc numeric(5,2),
    examen_fisico_general text,
    examen_bucal text,
    observaciones_medico text,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    activo boolean DEFAULT true,
    CONSTRAINT ficha_medica_consulta_pkey PRIMARY KEY (id_ficha_medica),
    CONSTRAINT fk_ficha_consulta FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON DELETE RESTRICT,
    -- Rangos clínicos aprobados, presión SSS/DDD (sistólica > diastólica) y al menos un dato. En una base ya existente, chk_ficha_con_datos se
    -- agrega NOT VALID (schema_consultorio_etapa3.sql) para conservar una ficha vacía anterior a la etapa 3.
    CONSTRAINT chk_ficha_rangos CHECK (
        (temperatura IS NULL OR temperatura BETWEEN 30 AND 45)
        AND (frecuencia_cardiaca IS NULL OR frecuencia_cardiaca BETWEEN 20 AND 250)
        AND (frecuencia_respiratoria IS NULL OR frecuencia_respiratoria BETWEEN 5 AND 80)
        AND (peso IS NULL OR peso BETWEEN 1 AND 500)
        AND (talla IS NULL OR talla BETWEEN 30 AND 250)),
    CONSTRAINT chk_ficha_presion CHECK (
        presion_arterial IS NULL
        OR (presion_arterial ~ '^[0-9]{2,3}/[0-9]{2,3}$'
            AND split_part(presion_arterial, '/', 1)::int BETWEEN 50 AND 300
            AND split_part(presion_arterial, '/', 2)::int BETWEEN 30 AND 200
            AND split_part(presion_arterial, '/', 1)::int > split_part(presion_arterial, '/', 2)::int)),
    CONSTRAINT chk_ficha_con_datos CHECK (
        num_nonnulls(presion_arterial, temperatura, frecuencia_cardiaca, frecuencia_respiratoria, peso, talla,
                     examen_fisico_general, examen_bucal, observaciones_medico) > 0)
);
CREATE INDEX IF NOT EXISTS idx_ficha_consulta ON ficha_medica_consulta USING btree (id_consulta_cab);
CREATE UNIQUE INDEX IF NOT EXISTS uk_ficha_medica_consulta_activa ON ficha_medica_consulta USING btree (id_consulta_cab) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS odontograma (
    id_odontograma SERIAL,
    id_paciente integer NOT NULL,
    id_medico integer NOT NULL,
    fecha_registro date DEFAULT CURRENT_DATE NOT NULL,
    observaciones text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    id_consulta_cab integer NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT odontograma_pkey PRIMARY KEY (id_odontograma),
    CONSTRAINT odontograma_id_consulta_cab_fkey FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON DELETE RESTRICT,
    CONSTRAINT odontograma_id_medico_fkey FOREIGN KEY (id_medico) REFERENCES medico(id_medico) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT odontograma_id_paciente_fkey FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_odontograma_consulta ON odontograma USING btree (id_consulta_cab);
CREATE INDEX IF NOT EXISTS idx_odontograma_fecha ON odontograma USING btree (fecha_registro);
CREATE INDEX IF NOT EXISTS idx_odontograma_medico ON odontograma USING btree (id_medico);
CREATE INDEX IF NOT EXISTS idx_odontograma_paciente ON odontograma USING btree (id_paciente);
CREATE UNIQUE INDEX IF NOT EXISTS ux_odontograma_consulta_activo ON odontograma USING btree (id_consulta_cab) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS diagnostico_sintoma (
    id_diagnostico integer NOT NULL,
    id_sintoma integer NOT NULL,
    CONSTRAINT diagnostico_sintoma_pkey PRIMARY KEY (id_diagnostico, id_sintoma),
    CONSTRAINT diagnostico_sintoma_id_diagnostico_fkey FOREIGN KEY (id_diagnostico) REFERENCES diagnosticos(id_diagnostico) ON DELETE CASCADE,
    CONSTRAINT diagnostico_sintoma_id_sintoma_fkey FOREIGN KEY (id_sintoma) REFERENCES sintoma(id_sintoma) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS justificativo_medico (
    id_justificativo SERIAL,
    id_consulta_cab integer NOT NULL,
    id_diagnostico integer,
    dias_reposo integer NOT NULL,
    recomendaciones text,
    fecha_justificativo date DEFAULT CURRENT_DATE NOT NULL,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_justificativo_dias CHECK (dias_reposo BETWEEN 1 AND 365),
    CONSTRAINT justificativo_medico_dias_reposo_check CHECK ((dias_reposo > 0)),
    CONSTRAINT justificativo_medico_estado_check CHECK (estado IN ('pendiente', 'emitido', 'anulado')),
    CONSTRAINT justificativo_medico_pkey PRIMARY KEY (id_justificativo),
    CONSTRAINT justificativo_medico_id_consulta_cab_fkey FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON DELETE RESTRICT,
    CONSTRAINT justificativo_medico_id_diagnostico_fkey FOREIGN KEY (id_diagnostico) REFERENCES diagnosticos(id_diagnostico) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_justificativo_consulta ON justificativo_medico (id_consulta_cab);
COMMENT ON COLUMN justificativo_medico.estado IS 'pendiente (registrado, borrador) -> emitido (documento oficial) | anulado (definitivo).';

CREATE TABLE IF NOT EXISTS odontograma_detalle (
    id_odontograma_detalle SERIAL,
    id_odontograma integer NOT NULL,
    numero_diente integer NOT NULL,
    id_estado_dental integer NOT NULL,
    superficie character varying(2) NOT NULL,
    observacion text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT odontograma_detalle_pkey PRIMARY KEY (id_odontograma_detalle),
    CONSTRAINT chk_detalle_superficie CHECK (superficie IN ('O', 'V', 'L', 'M', 'D', 'T')),
    -- FDI: permanentes 11-18, 21-28, 31-38, 41-48; temporales 51-55, 61-65, 71-75, 81-85
    CONSTRAINT chk_detalle_pieza_fdi CHECK (
        numero_diente BETWEEN 11 AND 18 OR numero_diente BETWEEN 21 AND 28 OR numero_diente BETWEEN 31 AND 38
        OR numero_diente BETWEEN 41 AND 48 OR numero_diente BETWEEN 51 AND 55 OR numero_diente BETWEEN 61 AND 65
        OR numero_diente BETWEEN 71 AND 75 OR numero_diente BETWEEN 81 AND 85),
    CONSTRAINT odontograma_detalle_id_estado_dental_fkey FOREIGN KEY (id_estado_dental) REFERENCES estado_dental(id_estado_dental) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT odontograma_detalle_id_odontograma_fkey FOREIGN KEY (id_odontograma) REFERENCES odontograma(id_odontograma) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_detalle_diente ON odontograma_detalle USING btree (numero_diente);
CREATE INDEX IF NOT EXISTS idx_detalle_odontograma ON odontograma_detalle USING btree (id_odontograma);
CREATE UNIQUE INDEX IF NOT EXISTS uk_odontograma_detalle_activo ON odontograma_detalle USING btree (id_odontograma, numero_diente, superficie, id_estado_dental) WHERE (activo = true);

CREATE TABLE IF NOT EXISTS tratamientos (
    id_tratamiento SERIAL,
    codigo character varying(10),
    id_consulta_cab integer NOT NULL,
    id_diagnostico integer,
    id_paciente integer NOT NULL,
    id_medico integer NOT NULL,
    id_consultorio integer,
    id_funcionario integer,
    id_tipo_diagnostico integer,
    id_tipo_tratamiento integer NOT NULL,
    descripcion_tratamiento text NOT NULL,
    fecha_tratamiento date NOT NULL,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_tratamiento_descripcion CHECK ((btrim(descripcion_tratamiento) <> ''::text)) NOT VALID,
    CONSTRAINT chk_estado_trat CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'en_seguimiento'::character varying, 'finalizado'::character varying, 'cancelado'::character varying])::text[]))),
    CONSTRAINT tratamientos_pkey PRIMARY KEY (id_tratamiento),
    CONSTRAINT tratamientos_codigo_key UNIQUE (codigo),
    CONSTRAINT fk_trat_consulta FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab),
    CONSTRAINT fk_trat_consultorio FOREIGN KEY (id_consultorio) REFERENCES consultorio(codigo),
    CONSTRAINT fk_trat_diagnostico FOREIGN KEY (id_diagnostico) REFERENCES diagnosticos(id_diagnostico),
    CONSTRAINT fk_trat_funcionario FOREIGN KEY (id_funcionario) REFERENCES funcionario(id_funcionario) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_trat_medico FOREIGN KEY (id_medico) REFERENCES medico(id_medico),
    CONSTRAINT fk_trat_paciente FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente),
    CONSTRAINT fk_trat_tipo_diag FOREIGN KEY (id_tipo_diagnostico) REFERENCES tipo_diagnostico(id_tipo_diagnostico),
    CONSTRAINT fk_trat_tipo_trat FOREIGN KEY (id_tipo_tratamiento) REFERENCES tipos_tratamiento(id_tipo_tratamiento)
);
CREATE INDEX IF NOT EXISTS idx_trat_consulta ON tratamientos USING btree (id_consulta_cab);
CREATE INDEX IF NOT EXISTS idx_trat_diagnostico ON tratamientos USING btree (id_diagnostico);
CREATE INDEX IF NOT EXISTS idx_trat_fecha ON tratamientos USING btree (fecha_tratamiento);
CREATE INDEX IF NOT EXISTS idx_trat_medico ON tratamientos USING btree (id_medico);
CREATE INDEX IF NOT EXISTS idx_trat_paciente ON tratamientos USING btree (id_paciente);
CREATE INDEX IF NOT EXISTS idx_trat_tipo_trat ON tratamientos USING btree (id_tipo_tratamiento);

CREATE TABLE IF NOT EXISTS orden_analisis (
    id_orden_analisis SERIAL,
    id_consulta_cab integer NOT NULL,
    id_diagnostico integer,
    id_tratamiento integer,
    id_tipo_analisis integer NOT NULL,
    motivo_orden text NOT NULL,
    indicaciones text,
    fecha_orden date DEFAULT CURRENT_DATE NOT NULL,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT orden_analisis_estado_check CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'enviado'::character varying, 'en_proceso'::character varying, 'completado'::character varying, 'cancelado'::character varying])::text[]))),
    CONSTRAINT chk_orden_analisis_motivo CHECK (btrim(motivo_orden) <> '') NOT VALID,
    CONSTRAINT orden_analisis_pkey PRIMARY KEY (id_orden_analisis),
    CONSTRAINT orden_analisis_id_consulta_cab_fkey FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON DELETE RESTRICT,
    CONSTRAINT orden_analisis_id_diagnostico_fkey FOREIGN KEY (id_diagnostico) REFERENCES diagnosticos(id_diagnostico) ON DELETE RESTRICT,
    CONSTRAINT orden_analisis_id_tipo_analisis_fkey FOREIGN KEY (id_tipo_analisis) REFERENCES tipo_analisis(id_tipo_analisis) ON DELETE RESTRICT,
    CONSTRAINT orden_analisis_id_tratamiento_fkey FOREIGN KEY (id_tratamiento) REFERENCES tratamientos(id_tratamiento) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS orden_estudios (
    id_orden_estudio SERIAL,
    id_consulta_cab integer NOT NULL,
    id_diagnostico integer,
    id_tratamiento integer,
    id_tipo_estudio integer NOT NULL,
    motivo_orden text NOT NULL,
    indicaciones text,
    fecha_orden date DEFAULT CURRENT_DATE NOT NULL,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT orden_estudios_estado_check CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'enviado'::character varying, 'en_proceso'::character varying, 'completado'::character varying, 'cancelado'::character varying])::text[]))),
    CONSTRAINT chk_orden_estudio_motivo CHECK (btrim(motivo_orden) <> '') NOT VALID,
    CONSTRAINT orden_estudios_pkey PRIMARY KEY (id_orden_estudio),
    CONSTRAINT orden_estudios_id_consulta_cab_fkey FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON DELETE RESTRICT,
    CONSTRAINT orden_estudios_id_diagnostico_fkey FOREIGN KEY (id_diagnostico) REFERENCES diagnosticos(id_diagnostico) ON DELETE RESTRICT,
    CONSTRAINT orden_estudios_id_tipo_estudio_fkey FOREIGN KEY (id_tipo_estudio) REFERENCES tipo_estudio(id_tipo_estudio) ON DELETE RESTRICT,
    CONSTRAINT orden_estudios_id_tratamiento_fkey FOREIGN KEY (id_tratamiento) REFERENCES tratamientos(id_tratamiento) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS recetas (
    id_receta SERIAL,
    id_consulta_cab integer NOT NULL,
    id_diagnostico integer,
    id_tratamiento integer,
    indicaciones_generales text NOT NULL,
    fecha_receta date DEFAULT CURRENT_DATE NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_receta_indicaciones CHECK (btrim(indicaciones_generales) <> '') NOT VALID,
    CONSTRAINT recetas_pkey PRIMARY KEY (id_receta),
    CONSTRAINT recetas_id_consulta_cab_fkey FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON DELETE RESTRICT,
    CONSTRAINT recetas_id_diagnostico_fkey FOREIGN KEY (id_diagnostico) REFERENCES diagnosticos(id_diagnostico) ON DELETE RESTRICT,
    CONSTRAINT recetas_id_tratamiento_fkey FOREIGN KEY (id_tratamiento) REFERENCES tratamientos(id_tratamiento) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS sesiones_tratamiento (
    id_sesion SERIAL,
    id_tratamiento integer NOT NULL,
    numero_sesion integer NOT NULL,
    fecha_sesion date DEFAULT CURRENT_DATE NOT NULL,
    descripcion_procedimiento text NOT NULL,
    observaciones text,
    proxima_cita date,
    activo boolean DEFAULT true NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    id_consulta_cab integer NOT NULL,
    CONSTRAINT chk_sesion_descripcion CHECK ((btrim(descripcion_procedimiento) <> ''::text)) NOT VALID,
    CONSTRAINT chk_sesion_proxima_cita CHECK (((proxima_cita IS NULL) OR (proxima_cita >= fecha_sesion))) NOT VALID,
    CONSTRAINT sesiones_tratamiento_pkey PRIMARY KEY (id_sesion),
    CONSTRAINT fk_sesion_consulta FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT sesiones_tratamiento_id_tratamiento_fkey FOREIGN KEY (id_tratamiento) REFERENCES tratamientos(id_tratamiento) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_sesion_tratamiento_numero ON sesiones_tratamiento USING btree (id_tratamiento, numero_sesion) WHERE (activo = true);
CREATE INDEX IF NOT EXISTS idx_sesion_consulta ON sesiones_tratamiento USING btree (id_consulta_cab);

CREATE TABLE IF NOT EXISTS sesion_procedimientos (
    id_sesion_procedimiento SERIAL,
    id_sesion integer NOT NULL,
    id_tipo_procedimiento integer NOT NULL,
    activo boolean NOT NULL DEFAULT true,
    CONSTRAINT sesion_procedimientos_pkey PRIMARY KEY (id_sesion_procedimiento),
    CONSTRAINT sesion_procedimientos_id_sesion_fkey FOREIGN KEY (id_sesion) REFERENCES sesiones_tratamiento(id_sesion) ON DELETE RESTRICT,
    CONSTRAINT sesion_procedimientos_id_tipo_fkey FOREIGN KEY (id_tipo_procedimiento) REFERENCES tipo_procedimiento_medico(id_tipo_procedimiento) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_sesion_procedimiento_activo ON sesion_procedimientos (id_sesion, id_tipo_procedimiento) WHERE activo = true;
CREATE INDEX IF NOT EXISTS idx_sesion_procedimientos_tipo ON sesion_procedimientos (id_tipo_procedimiento);

CREATE TABLE IF NOT EXISTS receta_medicamento (
    id_receta_medicamento SERIAL,
    id_receta integer NOT NULL,
    id_medicamento integer NOT NULL,
    dosis character varying(100) NOT NULL,
    frecuencia character varying(100) NOT NULL,
    duracion character varying(100) NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT chk_receta_medicamento_textos CHECK (btrim(dosis) <> '' AND btrim(frecuencia) <> '' AND btrim(duracion) <> '') NOT VALID,
    CONSTRAINT receta_medicamento_pkey PRIMARY KEY (id_receta_medicamento),
    CONSTRAINT receta_medicamento_id_medicamento_fkey FOREIGN KEY (id_medicamento) REFERENCES medicamentos(id_medicamento) ON DELETE RESTRICT,
    CONSTRAINT receta_medicamento_id_receta_fkey FOREIGN KEY (id_receta) REFERENCES recetas(id_receta) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_receta_medicamento_activo ON receta_medicamento (id_receta, id_medicamento) WHERE activo = true;
CREATE INDEX IF NOT EXISTS idx_receta_medicamento_medicamento ON receta_medicamento (id_medicamento);

CREATE TABLE IF NOT EXISTS sesion_insumos (
    id_sesion_insumo SERIAL,
    id_sesion integer NOT NULL,
    id_insumo integer NOT NULL,
    cantidad integer NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT sesion_insumos_cantidad_check CHECK ((cantidad > 0)),
    CONSTRAINT chk_sesion_insumo_cantidad CHECK (((cantidad >= 1) AND (cantidad <= 999))),
    CONSTRAINT sesion_insumos_pkey PRIMARY KEY (id_sesion_insumo),
    CONSTRAINT sesion_insumos_id_insumo_fkey FOREIGN KEY (id_insumo) REFERENCES insumos(id_insumo) ON DELETE RESTRICT,
    CONSTRAINT sesion_insumos_id_sesion_fkey FOREIGN KEY (id_sesion) REFERENCES sesiones_tratamiento(id_sesion) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_sesion_insumo_activo ON sesion_insumos (id_sesion, id_insumo) WHERE activo = true;
CREATE INDEX IF NOT EXISTS idx_sesion_insumos_insumo ON sesion_insumos (id_insumo);

CREATE OR REPLACE FUNCTION fn_validar_sesion_consulta() RETURNS trigger AS $$
-- La consulta en la que se registra una sesión es del mismo paciente y del mismo médico que el tratamiento.
BEGIN
    IF NOT EXISTS (SELECT 1 FROM tratamientos t JOIN consultas_cab c ON c.id_consulta_cab = NEW.id_consulta_cab
                    WHERE t.id_tratamiento = NEW.id_tratamiento AND t.id_paciente = c.id_paciente AND t.id_medico = c.id_medico) THEN
        RAISE EXCEPTION 'La consulta de la sesión debe ser del mismo paciente y del mismo médico que el tratamiento.' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION fn_validar_sesion_consulta() IS 'Trigger: una sesión se registra en una consulta del mismo paciente y médico que su tratamiento.';

DROP TRIGGER IF EXISTS trg_validar_sesion_consulta ON sesiones_tratamiento;
CREATE TRIGGER trg_validar_sesion_consulta
    BEFORE INSERT ON sesiones_tratamiento
    FOR EACH ROW EXECUTE FUNCTION fn_validar_sesion_consulta();

CREATE OR REPLACE FUNCTION fn_validar_sesion_procedimiento() RETURNS trigger AS $$
-- Una sesión vigente tiene al menos un procedimiento. Se verifica al CONFIRMAR la transacción (la sesión y sus procedimientos se insertan juntos).
BEGIN
    IF NEW.activo AND NOT EXISTS (SELECT 1 FROM sesion_procedimientos WHERE id_sesion = NEW.id_sesion AND activo = true) THEN
        RAISE EXCEPTION 'La sesión % debe tener al menos un procedimiento.', NEW.numero_sesion USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION fn_validar_sesion_procedimiento() IS 'Trigger diferido: toda sesión vigente tiene al menos un procedimiento (sesion_procedimientos).';

DROP TRIGGER IF EXISTS trg_sesion_con_procedimiento ON sesiones_tratamiento;
CREATE CONSTRAINT TRIGGER trg_sesion_con_procedimiento
    AFTER INSERT OR UPDATE OF activo ON sesiones_tratamiento
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validar_sesion_procedimiento();

CREATE INDEX IF NOT EXISTS idx_receta_consulta ON recetas (id_consulta_cab);
CREATE INDEX IF NOT EXISTS idx_orden_estudios_consulta ON orden_estudios (id_consulta_cab);
CREATE INDEX IF NOT EXISTS idx_orden_analisis_consulta ON orden_analisis (id_consulta_cab);

CREATE OR REPLACE FUNCTION fn_validar_receta_medicamento() RETURNS trigger AS $$
-- Una receta vigente tiene al menos un medicamento vigente. Se verifica al CONFIRMAR la transacción (la receta y sus medicamentos se insertan juntos).
BEGIN
    IF NEW.activo AND NOT EXISTS (SELECT 1 FROM receta_medicamento WHERE id_receta = NEW.id_receta AND activo = true) THEN
        RAISE EXCEPTION 'La receta % debe tener al menos un medicamento.', NEW.id_receta USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION fn_validar_receta_medicamento() IS 'Trigger diferido: toda receta vigente tiene al menos un medicamento (receta_medicamento).';

DROP TRIGGER IF EXISTS trg_receta_con_medicamento ON recetas;
CREATE CONSTRAINT TRIGGER trg_receta_con_medicamento
    AFTER INSERT OR UPDATE OF activo ON recetas
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validar_receta_medicamento();

CREATE OR REPLACE FUNCTION fn_validar_diagnostico_sintoma() RETURNS trigger AS $$
-- Un diagnóstico vigente tiene al menos un síntoma. Se verifica al CONFIRMAR la transacción (el diagnóstico y sus síntomas se insertan juntos).
BEGIN
    IF NEW.activo AND NOT EXISTS (SELECT 1 FROM diagnostico_sintoma WHERE id_diagnostico = NEW.id_diagnostico) THEN
        RAISE EXCEPTION 'El diagnóstico % debe tener al menos un síntoma.', NEW.codigo USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION fn_validar_diagnostico_sintoma() IS 'Trigger diferido: todo diagnóstico vigente tiene al menos un síntoma (diagnostico_sintoma).';

DROP TRIGGER IF EXISTS trg_diagnostico_con_sintoma ON diagnosticos;
CREATE CONSTRAINT TRIGGER trg_diagnostico_con_sintoma
    AFTER INSERT OR UPDATE OF activo ON diagnosticos
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validar_diagnostico_sintoma();

DROP TRIGGER IF EXISTS update_odontograma_updated_at ON odontograma;
CREATE TRIGGER update_odontograma_updated_at BEFORE UPDATE ON odontograma
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Catálogo fijo de estados dentales del odontograma
INSERT INTO estado_dental (id_estado_dental, descripcion, color, simbolo, activo, aplica_a) VALUES
    (1, 'Sano', '#E8F5E9', 'S', true, 'PIEZA'),
    (2, 'Caries', '#D32F2F', 'Ca', true, 'SUPERFICIE'),
    (3, 'Obturación', '#757575', 'Ob', true, 'SUPERFICIE'),
    (4, 'Extracción Indicada', '#FF9800', 'Ei', true, 'PIEZA'),
    (5, 'Extraído', '#212121', 'Ex', true, 'PIEZA'),
    (6, 'Endodoncia', '#E91E63', 'En', true, 'PIEZA'),
    (7, 'Corona', '#FDD835', 'Co', true, 'PIEZA'),
    (8, 'Puente', '#AB47BC', 'Pu', true, 'PIEZA'),
    (9, 'Implante', '#26A69A', 'Im', true, 'PIEZA'),
    (10, 'Prótesis Parcial', '#5C6BC0', 'Pp', true, 'PIEZA'),
    (11, 'Prótesis Total', '#1976D2', 'Pt', true, 'PIEZA'),
    (12, 'Incrustación', '#8D6E63', 'In', true, 'SUPERFICIE'),
    (13, 'Fractura', '#F44336', 'Fr', true, 'SUPERFICIE'),
    (14, 'Movilidad', '#FF5722', 'Mo', true, 'PIEZA'),
    (15, 'Bolsa Periodontal', '#9C27B0', 'Bp', true, 'PIEZA'),
    (16, 'Retracción Gingival', '#EC407A', 'Rg', true, 'PIEZA'),
    (17, 'Sellador', '#4CAF50', 'Se', true, 'SUPERFICIE'),
    (18, 'Resina', '#00BCD4', 'Re', true, 'SUPERFICIE'),
    (19, 'Amalgama', '#607D8B', 'Am', true, 'SUPERFICIE'),
    (20, 'Diente Incluido', '#795548', 'Di', true, 'PIEZA'),
    (21, 'Diente Temporal', '#FFEB3B', 'Dt', true, 'PIEZA'),
    (22, 'Ausente Congénito', '#9E9E9E', 'Ac', true, 'PIEZA')
ON CONFLICT (descripcion) DO NOTHING;
SELECT setval(pg_get_serial_sequence('estado_dental','id_estado_dental'), (SELECT MAX(id_estado_dental) FROM estado_dental));
