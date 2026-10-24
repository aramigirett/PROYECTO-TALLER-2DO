-- Usuarios de base de datos de la aplicación (mínimo privilegio) y del backup. Idempotente. Se corre como postgres.
-- Aplicar con PGCLIENTENCODING=UTF8 (o con crear_usuario_app.py, que además fija las contraseñas).
--
-- LAS CONTRASEÑAS NO VAN EN ESTE SCRIPT: los roles se crean sin contraseña (no pueden iniciar sesión hasta que se les fije
-- una) y crear_usuario_app.py la fija por la conexión, tomándola de una variable de entorno o pidiéndola al ejecutarlo.
-- A mano: \password odontoclinic_app   y   \password odontoclinic_backup   en psql.
--
-- odontoclinic_app (la usa la aplicación: DB_USER/DB_PASSWORD del .env)
--   * LOGIN; sin superusuario, CREATEDB, CREATEROLE, REPLICATION ni BYPASSRLS.
--   * SELECT/INSERT/UPDATE/DELETE en las tablas; SOLO SELECT en las vistas.
--   * USAGE y SELECT en las secuencias; EXECUTE en funciones y procedimientos.
--   * auditoria_cambios y auditoria_acceso: solo SELECT e INSERT (sin UPDATE ni DELETE: doble protección junto con el
--     trigger trg_auditoria_inmutable).
--   * Sin TRUNCATE, REFERENCES, TRIGGER ni CREATE: no puede cambiar el esquema.
--   * ALTER DEFAULT PRIVILEGES: lo que cree postgres de ahora en más (tablas, secuencias, funciones) le llega con los mismos
--     permisos. Las tablas de auditoría que se creen en el futuro hay que agregarlas a la lista de más abajo.
-- odontoclinic_backup (la usa el backup: BACKUP_DB_USER/BACKUP_DB_PASSWORD): LOGIN, solo lectura (pg_read_all_data).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'odontoclinic_app') THEN
        CREATE ROLE odontoclinic_app LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'odontoclinic_backup') THEN
        CREATE ROLE odontoclinic_backup LOGIN;
    END IF;
END;
$$;

-- Atributos (se reafirman en cada corrida)
ALTER ROLE odontoclinic_app    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
ALTER ROLE odontoclinic_backup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- Que nadie, salvo el dueño, pueda crear objetos en el esquema public (en PostgreSQL 14 PUBLIC lo puede por defecto)
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

DO $$
DECLARE
    v_db TEXT := current_database();
    r    RECORD;
    -- Tablas de auditoría: la aplicación solo las lee y les inserta
    v_auditoria TEXT[] := ARRAY['auditoria_cambios', 'auditoria_acceso'];
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO odontoclinic_app, odontoclinic_backup', v_db);
    GRANT USAGE ON SCHEMA public TO odontoclinic_app, odontoclinic_backup;

    -- Se parte de cero para que una corrida posterior también QUITE lo que sobre (idempotente y convergente)
    REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM odontoclinic_app;
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM odontoclinic_app;

    FOR r IN
        SELECT c.relname, c.relkind
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm')
    LOOP
        IF r.relkind IN ('v', 'm') THEN
            EXECUTE format('GRANT SELECT ON public.%I TO odontoclinic_app', r.relname);
        ELSIF r.relname = ANY (v_auditoria) THEN
            EXECUTE format('GRANT SELECT, INSERT ON public.%I TO odontoclinic_app', r.relname);
        ELSE
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO odontoclinic_app', r.relname);
        END IF;
    END LOOP;

    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO odontoclinic_app;
    GRANT EXECUTE ON ALL ROUTINES IN SCHEMA public TO odontoclinic_app;   -- funciones y procedimientos
END;
$$;

-- Objetos futuros creados por postgres en public
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO odontoclinic_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO odontoclinic_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT EXECUTE ON ROUTINES TO odontoclinic_app;

-- Backup: lectura de todo (tablas, vistas y secuencias), nada más
GRANT pg_read_all_data TO odontoclinic_backup;

COMMENT ON ROLE odontoclinic_app IS
    'Usuario de la aplicación OdontoClinic: DML sin UPDATE/DELETE en las auditorías, sin DDL ni superusuario.';
COMMENT ON ROLE odontoclinic_backup IS
    'Usuario del backup (pg_dump): solo lectura (pg_read_all_data).';
