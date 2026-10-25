-- Esquema versionado del Historial Médico del Paciente. Requiere schema_seguridad_base.sql antes (apunta a usuarios). Idempotente.
-- Se aplica como postgres con PGCLIENTENCODING=UTF8.

BEGIN;

CREATE TABLE IF NOT EXISTS public.historial_medico_paciente (
    id_historial integer NOT NULL,
    id_paciente integer NOT NULL,
    tipo_documento character varying(50) NOT NULL,
    descripcion text NOT NULL,
    tipo_alergia character varying(50),
    gravedad_alergia character varying(20),
    nombre_medicamento character varying(100),
    dosis_medicamento character varying(50),
    frecuencia_medicamento character varying(50),
    fecha_inicio_medicamento date,
    archivo_url character varying(255),
    archivo_nombre character varying(255),
    archivo_tipo character varying(50),
    archivo_tamano integer,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    id_usuario_registro integer,
    fecha_modificacion timestamp without time zone,
    id_usuario_modificacion integer,
    estado character varying(20) DEFAULT 'activo'::character varying,
    CONSTRAINT chk_estado CHECK (((estado)::text = ANY ((ARRAY['activo'::character varying, 'inactivo'::character varying])::text[]))),
    CONSTRAINT chk_tipo_documento CHECK (((tipo_documento)::text = ANY ((ARRAY['antecedente'::character varying, 'alergia'::character varying, 'medicamento_habitual'::character varying, 'estudio'::character varying, 'otro'::character varying])::text[])))
);

COMMENT ON TABLE public.historial_medico_paciente IS 'Almacena el historial médico general del paciente (antecedentes, alergias, medicamentos habituales, estudios)';

COMMENT ON COLUMN public.historial_medico_paciente.tipo_documento IS 'Tipo: antecedente, alergia, medicamento_habitual, estudio, otro';

COMMENT ON COLUMN public.historial_medico_paciente.estado IS 'Estado del registro: activo o inactivo';

CREATE SEQUENCE IF NOT EXISTS public.historial_medico_paciente_id_historial_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.historial_medico_paciente_id_historial_seq OWNED BY public.historial_medico_paciente.id_historial;

ALTER TABLE ONLY public.historial_medico_paciente ALTER COLUMN id_historial SET DEFAULT nextval('public.historial_medico_paciente_id_historial_seq'::regclass);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'historial_medico_paciente_pkey' AND conrelid = 'public.historial_medico_paciente'::regclass) THEN
    ALTER TABLE ONLY public.historial_medico_paciente
        ADD CONSTRAINT historial_medico_paciente_pkey PRIMARY KEY (id_historial);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_historial_fecha ON public.historial_medico_paciente USING btree (fecha_registro);

CREATE INDEX IF NOT EXISTS idx_historial_paciente ON public.historial_medico_paciente USING btree (id_paciente);

CREATE INDEX IF NOT EXISTS idx_historial_tipo ON public.historial_medico_paciente USING btree (tipo_documento);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_historial_paciente' AND conrelid = 'public.historial_medico_paciente'::regclass) THEN
    ALTER TABLE ONLY public.historial_medico_paciente
        ADD CONSTRAINT fk_historial_paciente FOREIGN KEY (id_paciente) REFERENCES public.paciente(id_paciente) ON DELETE CASCADE;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_historial_usuario_modificacion' AND conrelid = 'public.historial_medico_paciente'::regclass) THEN
    ALTER TABLE ONLY public.historial_medico_paciente
        ADD CONSTRAINT fk_historial_usuario_modificacion FOREIGN KEY (id_usuario_modificacion) REFERENCES public.usuarios(id_usuario) ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_historial_usuario_registro' AND conrelid = 'public.historial_medico_paciente'::regclass) THEN
    ALTER TABLE ONLY public.historial_medico_paciente
        ADD CONSTRAINT fk_historial_usuario_registro FOREIGN KEY (id_usuario_registro) REFERENCES public.usuarios(id_usuario) ON DELETE RESTRICT;
  END IF;
END $$;

COMMIT;
