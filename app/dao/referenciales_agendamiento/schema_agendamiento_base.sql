-- Esquema versionado de Agendamiento (tablas que antes solo existían en la base): 15 tablas, sus secuencias, claves, índices y CHECK,
-- tal como estaban en la base real ANTES de la migración a Tabler. Idempotente (IF NOT EXISTS / DO con pg_constraint): se puede volver a
-- correr. Se aplica como postgres con PGCLIENTENCODING=UTF8. Orden de la base completa: ver docs/historial_seguridad_agendamiento.md
-- ("Reconstruir la base desde el repo"). Los cambios de la migración están en schema_agendamiento_etapa1.sql en adelante.
-- No inserta datos (los catálogos fijos están en schema_agendamiento_datos.sql).

BEGIN;

CREATE TABLE IF NOT EXISTS public.agenda_cabecera (
    id_agenda_cabecera integer NOT NULL,
    id_medico integer NOT NULL,
    id_especialidad integer NOT NULL,
    fecha_agenda date NOT NULL,
    estado character varying(20) DEFAULT 'Activo'::character varying NOT NULL,
    id_funcionario integer NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    observaciones text,
    id_consultorio integer NOT NULL,
    CONSTRAINT agenda_cabecera_estado_check CHECK (((estado)::text = ANY ((ARRAY['Activo'::character varying, 'Inactivo'::character varying])::text[])))
);

CREATE SEQUENCE IF NOT EXISTS public.agenda_cabecera_id_agenda_cabecera_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.agenda_cabecera_id_agenda_cabecera_seq OWNED BY public.agenda_cabecera.id_agenda_cabecera;

CREATE TABLE IF NOT EXISTS public.agenda_detalle (
    id_agenda_detalle integer NOT NULL,
    id_agenda_cabecera integer NOT NULL,
    id_disponibilidad_horaria integer NOT NULL,
    id_dia integer NOT NULL,
    id_turno integer NOT NULL,
    hora_inicio time without time zone NOT NULL,
    hora_fin time without time zone NOT NULL,
    cupos_disponibles integer NOT NULL,
    cupos_maximos integer NOT NULL,
    estado_detalle character varying(20) DEFAULT 'Disponible'::character varying NOT NULL,
    CONSTRAINT agenda_detalle_cupos_disponibles_check CHECK ((cupos_disponibles >= 0)),
    CONSTRAINT agenda_detalle_cupos_maximos_check CHECK ((cupos_maximos > 0)),
    CONSTRAINT agenda_detalle_estado_detalle_check CHECK (((estado_detalle)::text = ANY ((ARRAY['Disponible'::character varying, 'Agotado'::character varying, 'Cancelado'::character varying])::text[]))),
    CONSTRAINT chk_cupos_validos CHECK ((cupos_disponibles <= cupos_maximos))
);

CREATE SEQUENCE IF NOT EXISTS public.agenda_detalle_id_agenda_detalle_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.agenda_detalle_id_agenda_detalle_seq OWNED BY public.agenda_detalle.id_agenda_detalle;

CREATE TABLE IF NOT EXISTS public.avisos_recordatorios (
    id_aviso integer NOT NULL,
    id_paciente integer NOT NULL,
    id_funcionario integer NOT NULL,
    id_medico integer,
    codigo integer,
    fecha_cita date NOT NULL,
    hora_cita time without time zone NOT NULL,
    forma_envio character varying(20),
    mensaje text,
    estado_envio character varying(20) DEFAULT 'Pendiente'::character varying,
    estado_confirmacion character varying(20) DEFAULT 'Pendiente'::character varying,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    estado character varying(20) DEFAULT 'Activo'::character varying NOT NULL,
    CONSTRAINT avisos_recordatorios_estado_confirmacion_check CHECK (((estado_confirmacion)::text = ANY ((ARRAY['Pendiente'::character varying, 'Confirmado'::character varying, 'Cancelado'::character varying])::text[]))),
    CONSTRAINT avisos_recordatorios_estado_envio_check CHECK (((estado_envio)::text = ANY ((ARRAY['Pendiente'::character varying, 'Enviado'::character varying, 'Error'::character varying])::text[]))),
    CONSTRAINT avisos_recordatorios_forma_envio_check CHECK (((forma_envio)::text = ANY ((ARRAY['Gmail'::character varying, 'SMS'::character varying, 'WhatsApp'::character varying])::text[])))
);

CREATE SEQUENCE IF NOT EXISTS public.avisos_recordatorios_id_aviso_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.avisos_recordatorios_id_aviso_seq OWNED BY public.avisos_recordatorios.id_aviso;

CREATE TABLE IF NOT EXISTS public.cargo (
    id_cargo integer NOT NULL,
    descripcion character varying(100) NOT NULL,
    activo boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS public.cargo_id_cargo_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.cargo_id_cargo_seq OWNED BY public.cargo.id_cargo;

CREATE TABLE IF NOT EXISTS public.cita_cabecera (
    id_cita_cabecera integer NOT NULL,
    id_paciente integer NOT NULL,
    id_agenda_cabecera integer NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    observaciones text,
    estado character varying(20) DEFAULT 'Activo'::character varying NOT NULL,
    id_funcionario integer NOT NULL,
    CONSTRAINT cita_cabecera_estado_check CHECK (((estado)::text = ANY ((ARRAY['Activo'::character varying, 'Inactivo'::character varying])::text[])))
);

CREATE SEQUENCE IF NOT EXISTS public.cita_cabecera_id_cita_cabecera_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.cita_cabecera_id_cita_cabecera_seq OWNED BY public.cita_cabecera.id_cita_cabecera;

CREATE TABLE IF NOT EXISTS public.cita_detalle (
    id_cita_detalle integer NOT NULL,
    id_cita_cabecera integer NOT NULL,
    id_agenda_detalle integer NOT NULL,
    fecha_cita date NOT NULL,
    hora_cita time without time zone NOT NULL,
    motivo_consulta text NOT NULL,
    id_estado_cita integer NOT NULL,
    fecha_cambio_estado timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS public.cita_detalle_id_cita_detalle_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.cita_detalle_id_cita_detalle_seq OWNED BY public.cita_detalle.id_cita_detalle;

CREATE TABLE IF NOT EXISTS public.ciudades (
    id_ciudad integer NOT NULL,
    descripcion character varying(100) NOT NULL,
    activo boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS public.ciudad_id_ciudad_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.ciudad_id_ciudad_seq OWNED BY public.ciudades.id_ciudad;

CREATE TABLE IF NOT EXISTS public.consultorio (
    codigo integer NOT NULL,
    nombre_consultorio character varying(150) NOT NULL,
    direccion character varying(255) NOT NULL,
    telefono character varying(30),
    correo character varying(150),
    activo boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS public.consultorio_codigo_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.consultorio_codigo_seq OWNED BY public.consultorio.codigo;

CREATE TABLE IF NOT EXISTS public.dias (
    id_dia integer NOT NULL,
    descripcion character varying(15) NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT chk_dias CHECK (((descripcion)::text = ANY ((ARRAY['LUNES'::character varying, 'MARTES'::character varying, 'MIERCOLES'::character varying, 'JUEVES'::character varying, 'VIERNES'::character varying, 'SABADO'::character varying, 'DOMINGO'::character varying])::text[])))
);

CREATE SEQUENCE IF NOT EXISTS public.dias_id_dia_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.dias_id_dia_seq OWNED BY public.dias.id_dia;

CREATE TABLE IF NOT EXISTS public.disponibilidad_horaria (
    id_disponibilidad integer NOT NULL,
    id_medico integer NOT NULL,
    id_dia integer NOT NULL,
    id_turno integer NOT NULL,
    dispo_hora_inicio time without time zone NOT NULL,
    dispo_hora_fin time without time zone NOT NULL,
    dispo_cupos integer NOT NULL,
    dispo_fecha date NOT NULL,
    CONSTRAINT chk_horario_valido CHECK ((dispo_hora_fin > dispo_hora_inicio)),
    CONSTRAINT disponibilidad_horaria_dispo_cupos_check CHECK ((dispo_cupos >= 0))
);

CREATE SEQUENCE IF NOT EXISTS public.disponibilidad_horaria_id_disponibilidad_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.disponibilidad_horaria_id_disponibilidad_seq OWNED BY public.disponibilidad_horaria.id_disponibilidad;

CREATE TABLE IF NOT EXISTS public.especialidades (
    id_especialidad integer NOT NULL,
    nombre_especialidad character varying(255) NOT NULL,
    activo boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS public.especialidades_id_especialidad_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.especialidades_id_especialidad_seq OWNED BY public.especialidades.id_especialidad;

CREATE TABLE IF NOT EXISTS public.estado_cita (
    id_estado_cita integer NOT NULL,
    descripcion character varying(50) NOT NULL,
    ocupa_cupo boolean DEFAULT true,
    activo boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS public.estado_cita_id_estado_cita_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.estado_cita_id_estado_cita_seq OWNED BY public.estado_cita.id_estado_cita;

CREATE TABLE IF NOT EXISTS public.funcionario (
    id_funcionario integer NOT NULL,
    nombre character varying(100) NOT NULL,
    apellido character varying(100) NOT NULL,
    cedula character varying(20) NOT NULL,
    fecha_nacimiento date,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    telefono character varying(20),
    direccion character varying(150),
    correo character varying(100),
    id_cargo integer NOT NULL,
    activo boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS public.funcionario_id_funcionario_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.funcionario_id_funcionario_seq OWNED BY public.funcionario.id_funcionario;

CREATE TABLE IF NOT EXISTS public.medico (
    id_medico integer NOT NULL,
    nombre character varying(255) NOT NULL,
    apellido character varying(255) NOT NULL,
    id_especialidad integer,
    num_registro character varying(255),
    cedula character varying(255),
    fecha_nacimiento date,
    fecha_registro date,
    telefono character varying(255),
    direccion text,
    correo character varying(255),
    id_ciudad integer,
    activo boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS public.medico_id_medico_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.medico_id_medico_seq OWNED BY public.medico.id_medico;

CREATE TABLE IF NOT EXISTS public.paciente (
    id_paciente integer NOT NULL,
    nombre character varying(100) NOT NULL,
    apellido character varying(100) NOT NULL,
    cedula_entidad character varying(20) NOT NULL,
    fecha_nacimiento date,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    telefono character varying(20),
    direccion character varying(150),
    correo character varying(100),
    id_ciudad integer NOT NULL,
    telefono_emergencia character varying(20),
    activo boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS public.paciente_id_paciente_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.paciente_id_paciente_seq OWNED BY public.paciente.id_paciente;

CREATE TABLE IF NOT EXISTS public.turnos (
    id_turno integer NOT NULL,
    descripcion character varying(60),
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT chk_turnos CHECK (((descripcion)::text = ANY ((ARRAY['MAÑANA'::character varying, 'TARDE'::character varying, 'NOCHE'::character varying])::text[])))
);

CREATE SEQUENCE IF NOT EXISTS public.turnos_id_turno_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.turnos_id_turno_seq OWNED BY public.turnos.id_turno;

ALTER TABLE ONLY public.agenda_cabecera ALTER COLUMN id_agenda_cabecera SET DEFAULT nextval('public.agenda_cabecera_id_agenda_cabecera_seq'::regclass);

ALTER TABLE ONLY public.agenda_detalle ALTER COLUMN id_agenda_detalle SET DEFAULT nextval('public.agenda_detalle_id_agenda_detalle_seq'::regclass);

ALTER TABLE ONLY public.avisos_recordatorios ALTER COLUMN id_aviso SET DEFAULT nextval('public.avisos_recordatorios_id_aviso_seq'::regclass);

ALTER TABLE ONLY public.cargo ALTER COLUMN id_cargo SET DEFAULT nextval('public.cargo_id_cargo_seq'::regclass);

ALTER TABLE ONLY public.cita_cabecera ALTER COLUMN id_cita_cabecera SET DEFAULT nextval('public.cita_cabecera_id_cita_cabecera_seq'::regclass);

ALTER TABLE ONLY public.cita_detalle ALTER COLUMN id_cita_detalle SET DEFAULT nextval('public.cita_detalle_id_cita_detalle_seq'::regclass);

ALTER TABLE ONLY public.ciudades ALTER COLUMN id_ciudad SET DEFAULT nextval('public.ciudad_id_ciudad_seq'::regclass);

ALTER TABLE ONLY public.consultorio ALTER COLUMN codigo SET DEFAULT nextval('public.consultorio_codigo_seq'::regclass);

ALTER TABLE ONLY public.dias ALTER COLUMN id_dia SET DEFAULT nextval('public.dias_id_dia_seq'::regclass);

ALTER TABLE ONLY public.disponibilidad_horaria ALTER COLUMN id_disponibilidad SET DEFAULT nextval('public.disponibilidad_horaria_id_disponibilidad_seq'::regclass);

ALTER TABLE ONLY public.especialidades ALTER COLUMN id_especialidad SET DEFAULT nextval('public.especialidades_id_especialidad_seq'::regclass);

ALTER TABLE ONLY public.estado_cita ALTER COLUMN id_estado_cita SET DEFAULT nextval('public.estado_cita_id_estado_cita_seq'::regclass);

ALTER TABLE ONLY public.funcionario ALTER COLUMN id_funcionario SET DEFAULT nextval('public.funcionario_id_funcionario_seq'::regclass);

ALTER TABLE ONLY public.medico ALTER COLUMN id_medico SET DEFAULT nextval('public.medico_id_medico_seq'::regclass);

ALTER TABLE ONLY public.paciente ALTER COLUMN id_paciente SET DEFAULT nextval('public.paciente_id_paciente_seq'::regclass);

ALTER TABLE ONLY public.turnos ALTER COLUMN id_turno SET DEFAULT nextval('public.turnos_id_turno_seq'::regclass);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'agenda_cabecera_pkey' AND conrelid = 'public.agenda_cabecera'::regclass) THEN
    ALTER TABLE ONLY public.agenda_cabecera
        ADD CONSTRAINT agenda_cabecera_pkey PRIMARY KEY (id_agenda_cabecera);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'agenda_detalle_pkey' AND conrelid = 'public.agenda_detalle'::regclass) THEN
    ALTER TABLE ONLY public.agenda_detalle
        ADD CONSTRAINT agenda_detalle_pkey PRIMARY KEY (id_agenda_detalle);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'avisos_recordatorios_pkey' AND conrelid = 'public.avisos_recordatorios'::regclass) THEN
    ALTER TABLE ONLY public.avisos_recordatorios
        ADD CONSTRAINT avisos_recordatorios_pkey PRIMARY KEY (id_aviso);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cargo_pkey' AND conrelid = 'public.cargo'::regclass) THEN
    ALTER TABLE ONLY public.cargo
        ADD CONSTRAINT cargo_pkey PRIMARY KEY (id_cargo);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cita_cabecera_pkey' AND conrelid = 'public.cita_cabecera'::regclass) THEN
    ALTER TABLE ONLY public.cita_cabecera
        ADD CONSTRAINT cita_cabecera_pkey PRIMARY KEY (id_cita_cabecera);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cita_detalle_pkey' AND conrelid = 'public.cita_detalle'::regclass) THEN
    ALTER TABLE ONLY public.cita_detalle
        ADD CONSTRAINT cita_detalle_pkey PRIMARY KEY (id_cita_detalle);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ciudad_pkey' AND conrelid = 'public.ciudades'::regclass) THEN
    ALTER TABLE ONLY public.ciudades
        ADD CONSTRAINT ciudad_pkey PRIMARY KEY (id_ciudad);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'consultorio_correo_key' AND conrelid = 'public.consultorio'::regclass) THEN
    ALTER TABLE ONLY public.consultorio
        ADD CONSTRAINT consultorio_correo_key UNIQUE (correo);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'consultorio_pkey' AND conrelid = 'public.consultorio'::regclass) THEN
    ALTER TABLE ONLY public.consultorio
        ADD CONSTRAINT consultorio_pkey PRIMARY KEY (codigo);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'dias_pkey' AND conrelid = 'public.dias'::regclass) THEN
    ALTER TABLE ONLY public.dias
        ADD CONSTRAINT dias_pkey PRIMARY KEY (id_dia);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'disponibilidad_horaria_pkey' AND conrelid = 'public.disponibilidad_horaria'::regclass) THEN
    ALTER TABLE ONLY public.disponibilidad_horaria
        ADD CONSTRAINT disponibilidad_horaria_pkey PRIMARY KEY (id_disponibilidad);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'especialidades_pkey' AND conrelid = 'public.especialidades'::regclass) THEN
    ALTER TABLE ONLY public.especialidades
        ADD CONSTRAINT especialidades_pkey PRIMARY KEY (id_especialidad);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'estado_cita_pkey' AND conrelid = 'public.estado_cita'::regclass) THEN
    ALTER TABLE ONLY public.estado_cita
        ADD CONSTRAINT estado_cita_pkey PRIMARY KEY (id_estado_cita);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'funcionario_cedula_key' AND conrelid = 'public.funcionario'::regclass) THEN
    ALTER TABLE ONLY public.funcionario
        ADD CONSTRAINT funcionario_cedula_key UNIQUE (cedula);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'funcionario_pkey' AND conrelid = 'public.funcionario'::regclass) THEN
    ALTER TABLE ONLY public.funcionario
        ADD CONSTRAINT funcionario_pkey PRIMARY KEY (id_funcionario);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'medico_cedula_key' AND conrelid = 'public.medico'::regclass) THEN
    ALTER TABLE ONLY public.medico
        ADD CONSTRAINT medico_cedula_key UNIQUE (cedula);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'medico_pkey' AND conrelid = 'public.medico'::regclass) THEN
    ALTER TABLE ONLY public.medico
        ADD CONSTRAINT medico_pkey PRIMARY KEY (id_medico);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'paciente_cedula_entidad_key' AND conrelid = 'public.paciente'::regclass) THEN
    ALTER TABLE ONLY public.paciente
        ADD CONSTRAINT paciente_cedula_entidad_key UNIQUE (cedula_entidad);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'paciente_pkey' AND conrelid = 'public.paciente'::regclass) THEN
    ALTER TABLE ONLY public.paciente
        ADD CONSTRAINT paciente_pkey PRIMARY KEY (id_paciente);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'turnos_pkey' AND conrelid = 'public.turnos'::regclass) THEN
    ALTER TABLE ONLY public.turnos
        ADD CONSTRAINT turnos_pkey PRIMARY KEY (id_turno);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uk_disponibilidad' AND conrelid = 'public.disponibilidad_horaria'::regclass) THEN
    ALTER TABLE ONLY public.disponibilidad_horaria
        ADD CONSTRAINT uk_disponibilidad UNIQUE (id_medico, dispo_fecha, dispo_hora_inicio, dispo_hora_fin);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_avisos_estado ON public.avisos_recordatorios USING btree (estado_envio);

CREATE INDEX IF NOT EXISTS idx_avisos_fecha ON public.avisos_recordatorios USING btree (fecha_cita);

CREATE INDEX IF NOT EXISTS idx_avisos_funcionario ON public.avisos_recordatorios USING btree (id_funcionario);

CREATE INDEX IF NOT EXISTS idx_avisos_paciente ON public.avisos_recordatorios USING btree (id_paciente);

CREATE INDEX IF NOT EXISTS idx_consultorio_nombre ON public.consultorio USING btree (nombre_consultorio);

CREATE UNIQUE INDEX IF NOT EXISTS uk_cabecera_disponibilidad ON public.agenda_detalle USING btree (id_agenda_cabecera, id_disponibilidad_horaria) WHERE ((estado_detalle)::text <> 'Cancelado'::text);

CREATE UNIQUE INDEX IF NOT EXISTS uk_medico_fecha ON public.agenda_cabecera USING btree (id_medico, fecha_agenda) WHERE ((estado)::text <> 'Inactivo'::text);

CREATE UNIQUE INDEX IF NOT EXISTS ux_cargo_descripcion_activo ON public.cargo USING btree (upper((descripcion)::text)) WHERE (activo = true);

CREATE UNIQUE INDEX IF NOT EXISTS ux_ciudades_descripcion_activo ON public.ciudades USING btree (upper((descripcion)::text)) WHERE (activo = true);

CREATE UNIQUE INDEX IF NOT EXISTS ux_dias_descripcion_activo ON public.dias USING btree (upper((descripcion)::text)) WHERE (activo = true);

CREATE UNIQUE INDEX IF NOT EXISTS ux_especialidades_nombre_activo ON public.especialidades USING btree (upper((nombre_especialidad)::text)) WHERE (activo = true);

CREATE UNIQUE INDEX IF NOT EXISTS ux_estado_cita_descripcion_activo ON public.estado_cita USING btree (upper((descripcion)::text)) WHERE (activo = true);

CREATE UNIQUE INDEX IF NOT EXISTS ux_turnos_descripcion_activo ON public.turnos USING btree (upper((descripcion)::text)) WHERE (activo = true);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'agenda_cabecera_id_especialidad_fkey' AND conrelid = 'public.agenda_cabecera'::regclass) THEN
    ALTER TABLE ONLY public.agenda_cabecera
        ADD CONSTRAINT agenda_cabecera_id_especialidad_fkey FOREIGN KEY (id_especialidad) REFERENCES public.especialidades(id_especialidad) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'agenda_cabecera_id_medico_fkey' AND conrelid = 'public.agenda_cabecera'::regclass) THEN
    ALTER TABLE ONLY public.agenda_cabecera
        ADD CONSTRAINT agenda_cabecera_id_medico_fkey FOREIGN KEY (id_medico) REFERENCES public.medico(id_medico) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'agenda_detalle_id_agenda_cabecera_fkey' AND conrelid = 'public.agenda_detalle'::regclass) THEN
    ALTER TABLE ONLY public.agenda_detalle
        ADD CONSTRAINT agenda_detalle_id_agenda_cabecera_fkey FOREIGN KEY (id_agenda_cabecera) REFERENCES public.agenda_cabecera(id_agenda_cabecera) ON UPDATE CASCADE ON DELETE CASCADE;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'agenda_detalle_id_dia_fkey' AND conrelid = 'public.agenda_detalle'::regclass) THEN
    ALTER TABLE ONLY public.agenda_detalle
        ADD CONSTRAINT agenda_detalle_id_dia_fkey FOREIGN KEY (id_dia) REFERENCES public.dias(id_dia) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'agenda_detalle_id_disponibilidad_horaria_fkey' AND conrelid = 'public.agenda_detalle'::regclass) THEN
    ALTER TABLE ONLY public.agenda_detalle
        ADD CONSTRAINT agenda_detalle_id_disponibilidad_horaria_fkey FOREIGN KEY (id_disponibilidad_horaria) REFERENCES public.disponibilidad_horaria(id_disponibilidad) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'agenda_detalle_id_turno_fkey' AND conrelid = 'public.agenda_detalle'::regclass) THEN
    ALTER TABLE ONLY public.agenda_detalle
        ADD CONSTRAINT agenda_detalle_id_turno_fkey FOREIGN KEY (id_turno) REFERENCES public.turnos(id_turno) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cita_cabecera_id_agenda_cabecera_fkey' AND conrelid = 'public.cita_cabecera'::regclass) THEN
    ALTER TABLE ONLY public.cita_cabecera
        ADD CONSTRAINT cita_cabecera_id_agenda_cabecera_fkey FOREIGN KEY (id_agenda_cabecera) REFERENCES public.agenda_cabecera(id_agenda_cabecera) ON UPDATE CASCADE ON DELETE CASCADE;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cita_cabecera_id_funcionario_fkey' AND conrelid = 'public.cita_cabecera'::regclass) THEN
    ALTER TABLE ONLY public.cita_cabecera
        ADD CONSTRAINT cita_cabecera_id_funcionario_fkey FOREIGN KEY (id_funcionario) REFERENCES public.funcionario(id_funcionario) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cita_cabecera_id_paciente_fkey' AND conrelid = 'public.cita_cabecera'::regclass) THEN
    ALTER TABLE ONLY public.cita_cabecera
        ADD CONSTRAINT cita_cabecera_id_paciente_fkey FOREIGN KEY (id_paciente) REFERENCES public.paciente(id_paciente) ON UPDATE CASCADE ON DELETE CASCADE;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cita_detalle_id_agenda_detalle_fkey' AND conrelid = 'public.cita_detalle'::regclass) THEN
    ALTER TABLE ONLY public.cita_detalle
        ADD CONSTRAINT cita_detalle_id_agenda_detalle_fkey FOREIGN KEY (id_agenda_detalle) REFERENCES public.agenda_detalle(id_agenda_detalle) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cita_detalle_id_cita_cabecera_fkey' AND conrelid = 'public.cita_detalle'::regclass) THEN
    ALTER TABLE ONLY public.cita_detalle
        ADD CONSTRAINT cita_detalle_id_cita_cabecera_fkey FOREIGN KEY (id_cita_cabecera) REFERENCES public.cita_cabecera(id_cita_cabecera) ON UPDATE CASCADE ON DELETE CASCADE;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cita_detalle_id_estado_cita_fkey' AND conrelid = 'public.cita_detalle'::regclass) THEN
    ALTER TABLE ONLY public.cita_detalle
        ADD CONSTRAINT cita_detalle_id_estado_cita_fkey FOREIGN KEY (id_estado_cita) REFERENCES public.estado_cita(id_estado_cita) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'disponibilidad_horaria_id_dia_fkey' AND conrelid = 'public.disponibilidad_horaria'::regclass) THEN
    ALTER TABLE ONLY public.disponibilidad_horaria
        ADD CONSTRAINT disponibilidad_horaria_id_dia_fkey FOREIGN KEY (id_dia) REFERENCES public.dias(id_dia) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'disponibilidad_horaria_id_medico_fkey' AND conrelid = 'public.disponibilidad_horaria'::regclass) THEN
    ALTER TABLE ONLY public.disponibilidad_horaria
        ADD CONSTRAINT disponibilidad_horaria_id_medico_fkey FOREIGN KEY (id_medico) REFERENCES public.medico(id_medico) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'disponibilidad_horaria_id_turno_fkey' AND conrelid = 'public.disponibilidad_horaria'::regclass) THEN
    ALTER TABLE ONLY public.disponibilidad_horaria
        ADD CONSTRAINT disponibilidad_horaria_id_turno_fkey FOREIGN KEY (id_turno) REFERENCES public.turnos(id_turno) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_agenda_consultorio' AND conrelid = 'public.agenda_cabecera'::regclass) THEN
    ALTER TABLE ONLY public.agenda_cabecera
        ADD CONSTRAINT fk_agenda_consultorio FOREIGN KEY (id_consultorio) REFERENCES public.consultorio(codigo) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_consultorio' AND conrelid = 'public.avisos_recordatorios'::regclass) THEN
    ALTER TABLE ONLY public.avisos_recordatorios
        ADD CONSTRAINT fk_consultorio FOREIGN KEY (codigo) REFERENCES public.consultorio(codigo) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_funcionario' AND conrelid = 'public.avisos_recordatorios'::regclass) THEN
    ALTER TABLE ONLY public.avisos_recordatorios
        ADD CONSTRAINT fk_funcionario FOREIGN KEY (id_funcionario) REFERENCES public.funcionario(id_funcionario) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_funcionario_cargo' AND conrelid = 'public.funcionario'::regclass) THEN
    ALTER TABLE ONLY public.funcionario
        ADD CONSTRAINT fk_funcionario_cargo FOREIGN KEY (id_cargo) REFERENCES public.cargo(id_cargo) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_medico' AND conrelid = 'public.avisos_recordatorios'::regclass) THEN
    ALTER TABLE ONLY public.avisos_recordatorios
        ADD CONSTRAINT fk_medico FOREIGN KEY (id_medico) REFERENCES public.medico(id_medico) ON UPDATE CASCADE ON DELETE SET NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_paciente' AND conrelid = 'public.avisos_recordatorios'::regclass) THEN
    ALTER TABLE ONLY public.avisos_recordatorios
        ADD CONSTRAINT fk_paciente FOREIGN KEY (id_paciente) REFERENCES public.paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_paciente_ciudad' AND conrelid = 'public.paciente'::regclass) THEN
    ALTER TABLE ONLY public.paciente
        ADD CONSTRAINT fk_paciente_ciudad FOREIGN KEY (id_ciudad) REFERENCES public.ciudades(id_ciudad) ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'medico_id_ciudad_fkey' AND conrelid = 'public.medico'::regclass) THEN
    ALTER TABLE ONLY public.medico
        ADD CONSTRAINT medico_id_ciudad_fkey FOREIGN KEY (id_ciudad) REFERENCES public.ciudades(id_ciudad) ON DELETE SET NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'medico_id_especialidad_fkey' AND conrelid = 'public.medico'::regclass) THEN
    ALTER TABLE ONLY public.medico
        ADD CONSTRAINT medico_id_especialidad_fkey FOREIGN KEY (id_especialidad) REFERENCES public.especialidades(id_especialidad) ON DELETE RESTRICT;
  END IF;
END $$;

COMMIT;
