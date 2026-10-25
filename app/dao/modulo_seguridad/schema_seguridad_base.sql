-- Esquema versionado de Seguridad (tablas que no tenían su CREATE TABLE vigente): roles, menu, usuarios, token_2fa y permisos (con id_menu),
-- en su estado actual. Requiere schema_agendamiento_base.sql antes (usuarios apunta a medico y funcionario). Idempotente. Se aplica como postgres
-- con PGCLIENTENCODING=UTF8. Los scripts viejos que crearon o alteraron estas tablas (schema_seguridad.sql, schema_permisos.sql y
-- schema_acceso_seguridad.sql, schema_ip_inactividad.sql, schema_datos_unica_fuente*.sql, la migración 02) quedan como histórico: sus cambios ya
-- están acá. auditoria_acceso, auditoria_cambios y sus triggers siguen en sus propios scripts.

BEGIN;

CREATE TABLE IF NOT EXISTS public.menu (
    id_menu integer NOT NULL,
    id_menu_padre integer,
    clave character varying(60),
    descripcion character varying(60) NOT NULL,
    ruta character varying(150),
    icono character varying(50),
    orden smallint DEFAULT 0 NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_menu_padre CHECK (((id_menu_padre IS NULL) OR (id_menu_padre <> id_menu)))
);

COMMENT ON TABLE public.menu IS 'Menú dinámico: módulos (sin padre) y ventanas (con padre). Los permisos se asignan por ventana y acción.';

CREATE SEQUENCE IF NOT EXISTS public.menu_id_menu_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.menu_id_menu_seq OWNED BY public.menu.id_menu;

CREATE TABLE IF NOT EXISTS public.permisos (
    id_permiso integer NOT NULL,
    id_rol integer NOT NULL,
    accion character varying(20) NOT NULL,
    id_menu integer NOT NULL,
    CONSTRAINT chk_permiso_accion CHECK (((accion)::text = ANY ((ARRAY['ver'::character varying, 'nuevo'::character varying, 'editar'::character varying, 'anular'::character varying, 'estado'::character varying, 'desbloquear'::character varying])::text[])))
);

CREATE SEQUENCE IF NOT EXISTS public.permisos_id_permiso_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.permisos_id_permiso_seq OWNED BY public.permisos.id_permiso;

CREATE TABLE IF NOT EXISTS public.roles (
    id_rol integer NOT NULL,
    nombre_rol character varying(20) NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT roles_nombre_rol_check CHECK (((nombre_rol)::text = ANY ((ARRAY['Administrador'::character varying, 'Medico'::character varying, 'Recepcion'::character varying, 'Cajero'::character varying])::text[])))
);

CREATE SEQUENCE IF NOT EXISTS public.roles_id_rol_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.roles_id_rol_seq OWNED BY public.roles.id_rol;

CREATE TABLE IF NOT EXISTS public.token_2fa (
    id_token integer NOT NULL,
    id_usuario integer NOT NULL,
    codigo character varying(6) NOT NULL,
    fecha_generacion timestamp without time zone DEFAULT now() NOT NULL,
    fecha_expiracion timestamp without time zone NOT NULL,
    usado boolean DEFAULT false NOT NULL,
    proposito character varying(20) DEFAULT 'LOGIN'::character varying NOT NULL,
    intentos_fallidos integer DEFAULT 0 NOT NULL,
    CONSTRAINT chk_token_proposito CHECK (((proposito)::text = ANY ((ARRAY['LOGIN'::character varying, 'RECUPERACION'::character varying])::text[])))
);

CREATE SEQUENCE IF NOT EXISTS public.token_2fa_id_token_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.token_2fa_id_token_seq OWNED BY public.token_2fa.id_token;

CREATE TABLE IF NOT EXISTS public.usuarios (
    id_usuario integer NOT NULL,
    password_hash character varying(255) NOT NULL,
    id_rol integer NOT NULL,
    id_funcionario integer,
    id_medico integer,
    activo boolean DEFAULT true NOT NULL,
    fecha_creacion timestamp without time zone DEFAULT now() NOT NULL,
    intentos_fallidos integer DEFAULT 0 NOT NULL,
    bloqueado boolean DEFAULT false NOT NULL,
    fecha_bloqueo timestamp without time zone,
    CONSTRAINT chk_usuario_persona_xor CHECK ((((id_funcionario IS NOT NULL) AND (id_medico IS NULL)) OR ((id_funcionario IS NULL) AND (id_medico IS NOT NULL))))
);

CREATE SEQUENCE IF NOT EXISTS public.usuarios_id_usuario_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.usuarios_id_usuario_seq OWNED BY public.usuarios.id_usuario;

ALTER TABLE ONLY public.menu ALTER COLUMN id_menu SET DEFAULT nextval('public.menu_id_menu_seq'::regclass);

ALTER TABLE ONLY public.permisos ALTER COLUMN id_permiso SET DEFAULT nextval('public.permisos_id_permiso_seq'::regclass);

ALTER TABLE ONLY public.roles ALTER COLUMN id_rol SET DEFAULT nextval('public.roles_id_rol_seq'::regclass);

ALTER TABLE ONLY public.token_2fa ALTER COLUMN id_token SET DEFAULT nextval('public.token_2fa_id_token_seq'::regclass);

ALTER TABLE ONLY public.usuarios ALTER COLUMN id_usuario SET DEFAULT nextval('public.usuarios_id_usuario_seq'::regclass);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'menu_pkey' AND conrelid = 'public.menu'::regclass) THEN
    ALTER TABLE ONLY public.menu
        ADD CONSTRAINT menu_pkey PRIMARY KEY (id_menu);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'permisos_pkey' AND conrelid = 'public.permisos'::regclass) THEN
    ALTER TABLE ONLY public.permisos
        ADD CONSTRAINT permisos_pkey PRIMARY KEY (id_permiso);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'roles_nombre_rol_key' AND conrelid = 'public.roles'::regclass) THEN
    ALTER TABLE ONLY public.roles
        ADD CONSTRAINT roles_nombre_rol_key UNIQUE (nombre_rol);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'roles_pkey' AND conrelid = 'public.roles'::regclass) THEN
    ALTER TABLE ONLY public.roles
        ADD CONSTRAINT roles_pkey PRIMARY KEY (id_rol);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'token_2fa_pkey' AND conrelid = 'public.token_2fa'::regclass) THEN
    ALTER TABLE ONLY public.token_2fa
        ADD CONSTRAINT token_2fa_pkey PRIMARY KEY (id_token);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_permiso_rol_menu_accion' AND conrelid = 'public.permisos'::regclass) THEN
    ALTER TABLE ONLY public.permisos
        ADD CONSTRAINT uq_permiso_rol_menu_accion UNIQUE (id_rol, id_menu, accion);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'usuarios_pkey' AND conrelid = 'public.usuarios'::regclass) THEN
    ALTER TABLE ONLY public.usuarios
        ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id_usuario);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_token_2fa_vigentes ON public.token_2fa USING btree (id_usuario, proposito) WHERE (usado = false);

CREATE UNIQUE INDEX IF NOT EXISTS ux_menu_clave_activo ON public.menu USING btree (clave) WHERE ((activo = true) AND (clave IS NOT NULL));

CREATE UNIQUE INDEX IF NOT EXISTS ux_menu_padre_descripcion_activo ON public.menu USING btree (COALESCE(id_menu_padre, 0), upper((descripcion)::text)) WHERE (activo = true);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'menu_id_menu_padre_fkey' AND conrelid = 'public.menu'::regclass) THEN
    ALTER TABLE ONLY public.menu
        ADD CONSTRAINT menu_id_menu_padre_fkey FOREIGN KEY (id_menu_padre) REFERENCES public.menu(id_menu) ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'permisos_id_menu_fkey' AND conrelid = 'public.permisos'::regclass) THEN
    ALTER TABLE ONLY public.permisos
        ADD CONSTRAINT permisos_id_menu_fkey FOREIGN KEY (id_menu) REFERENCES public.menu(id_menu) ON DELETE RESTRICT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'permisos_id_rol_fkey' AND conrelid = 'public.permisos'::regclass) THEN
    ALTER TABLE ONLY public.permisos
        ADD CONSTRAINT permisos_id_rol_fkey FOREIGN KEY (id_rol) REFERENCES public.roles(id_rol);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'token_2fa_id_usuario_fkey' AND conrelid = 'public.token_2fa'::regclass) THEN
    ALTER TABLE ONLY public.token_2fa
        ADD CONSTRAINT token_2fa_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuarios(id_usuario);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'usuarios_id_funcionario_fkey' AND conrelid = 'public.usuarios'::regclass) THEN
    ALTER TABLE ONLY public.usuarios
        ADD CONSTRAINT usuarios_id_funcionario_fkey FOREIGN KEY (id_funcionario) REFERENCES public.funcionario(id_funcionario);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'usuarios_id_medico_fkey' AND conrelid = 'public.usuarios'::regclass) THEN
    ALTER TABLE ONLY public.usuarios
        ADD CONSTRAINT usuarios_id_medico_fkey FOREIGN KEY (id_medico) REFERENCES public.medico(id_medico);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'usuarios_id_rol_fkey' AND conrelid = 'public.usuarios'::regclass) THEN
    ALTER TABLE ONLY public.usuarios
        ADD CONSTRAINT usuarios_id_rol_fkey FOREIGN KEY (id_rol) REFERENCES public.roles(id_rol);
  END IF;
END $$;

-- Los 4 roles del sistema (los fija el CHECK de roles.nombre_rol)
INSERT INTO roles (nombre_rol)
SELECT v FROM (VALUES ('Administrador'), ('Medico'), ('Recepcion'), ('Cajero')) AS x(v)
 WHERE NOT EXISTS (SELECT 1 FROM roles r WHERE r.nombre_rol = x.v);

COMMIT;
