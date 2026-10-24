-- Elimina la tabla `paises`: tenía una sola fila (PARAGUAY), sin código ISO y sin ninguna referencia. El país permitido
-- para el acceso ahora se configura en .env (PAIS_PERMITIDO, código ISO). Idempotente; aplicar con PGCLIENTENCODING=UTF8.
-- Se niega a borrar si algo la referencia (FK, vista o función): DROP sin CASCADE a propósito.
DO $$
DECLARE
    v_refs TEXT;
BEGIN
    IF to_regclass('public.paises') IS NULL THEN
        RAISE NOTICE 'La tabla paises ya no existe; nada que hacer.';
        RETURN;
    END IF;

    SELECT string_agg(conrelid::regclass::text || ' (' || conname || ')', ', ')
      INTO v_refs
      FROM pg_constraint
     WHERE contype = 'f' AND confrelid = 'public.paises'::regclass;
    IF v_refs IS NOT NULL THEN
        RAISE EXCEPTION 'No se elimina paises: la referencian las claves foráneas %', v_refs;
    END IF;

    SELECT string_agg(DISTINCT c.relname, ', ')
      INTO v_refs
      FROM pg_depend d
      JOIN pg_rewrite r ON r.oid = d.objid
      JOIN pg_class c ON c.oid = r.ev_class
     WHERE d.refobjid = 'public.paises'::regclass AND c.oid <> 'public.paises'::regclass;
    IF v_refs IS NOT NULL THEN
        RAISE EXCEPTION 'No se elimina paises: la usan las vistas %', v_refs;
    END IF;

    DROP TABLE public.paises;
    RAISE NOTICE 'Tabla paises eliminada.';
END;
$$;
