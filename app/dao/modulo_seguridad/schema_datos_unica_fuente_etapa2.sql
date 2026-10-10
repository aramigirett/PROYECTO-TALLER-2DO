-- Una sola fuente de verdad para cédula y correo - ETAPA 2.
-- Elimina las copias muertas usuarios.ci_ruc / usuarios.correo (el sistema ya lee ambos
-- de la persona vinculada desde la etapa 1). Idempotente. Hacer pg_dump antes.
-- Sin CASCADE a propósito: si algún objeto (vista, índice propio) todavía las usa, falla
-- en vez de borrarlo en silencio.
ALTER TABLE usuarios DROP COLUMN IF EXISTS ci_ruc;
ALTER TABLE usuarios DROP COLUMN IF EXISTS correo;
