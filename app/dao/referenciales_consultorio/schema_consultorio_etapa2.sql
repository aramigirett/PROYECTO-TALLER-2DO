-- Módulo Consultorio, etapa 2: Tipo Diagnóstico y Síntomas pasan al estándar de referenciales (borrado lógico, MAYÚSCULAS).
-- Idempotente; se corre como postgres (PGCLIENTENCODING=UTF8). Las tablas ya tienen `activo` y su único parcial por UPPER(descripción)
-- (ux_tipo_diagnostico_descripcion_activo, ux_sintoma_descripcion_activo; ver schema_consultorio_base.sql): solo falta pasar a
-- MAYÚSCULAS lo cargado antes, porque desde ahora la API guarda así. No puede chocar con el único (ya comparaba sin distinguir mayúsculas).
BEGIN;
UPDATE tipo_diagnostico
   SET descripcion_diagnostico = UPPER(descripcion_diagnostico), tipo_diagnostico = UPPER(tipo_diagnostico)
 WHERE descripcion_diagnostico <> UPPER(descripcion_diagnostico) OR tipo_diagnostico <> UPPER(tipo_diagnostico);
UPDATE sintoma
   SET descripcion_sintoma = UPPER(descripcion_sintoma)
 WHERE descripcion_sintoma <> UPPER(descripcion_sintoma);
COMMIT;
