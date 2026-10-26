-- RESET DE DATOS DE PRUEBA de odontosisbd (NO es una migración: no cambia el esquema y NO es idempotente en el sentido de "se puede olvidar";
-- cada corrida deja la base en el mismo estado inicial y borra lo que haya).
--
-- CUÁNDO: solo para empezar de cero una prueba de punta a punta. NUNCA sobre datos reales.
-- CÓMO (como postgres, con el servidor de la app detenido y DESPUÉS de un backup):
--     $env:PGCLIENTENCODING = 'UTF8'
--     psql -U postgres -d odontosisbd -v ON_ERROR_STOP=1 -f scripts/reset_datos_prueba.sql
--
-- QUÉ HACE (todo en UNA transacción: si algo falla o una verificación final no se cumple, no queda nada a medias):
--   1. Borra, tabla por tabla y en orden de dependencias (hijos antes que padres; sin TRUNCATE ... CASCADE), los movimientos de
--      Facturación, Consultorio y Agendamiento, las tablas de auditoría (inmutables: se desactiva su trigger solo dentro de esta
--      transacción y se vuelve a activar antes de confirmar) y los códigos 2FA.
--   2. Borra todos los usuarios que no sean el Administrador y todos los funcionarios, salvo el vinculado al Administrador.
--   3. Reinicia las secuencias de las tablas vaciadas (en usuarios y funcionario, la secuencia sigue desde el id que queda).
--   4. Stock de los ítems que controlan stock = 50 unidades (los servicios no controlan stock: quedan como están);
--      timbrado.numero_actual = 0 (el siguiente número de factura es el inicial del timbrado).
--
-- NO TOCA: referenciales (ciudades, cargo, consultorio, disponibilidad, especialidades, días, turnos, tipos, ítems, formas de cobro,
-- marcas, entidades, cuentas bancarias, cajas, depósitos, clientes, medicamentos, insumos, síntomas, estados...), médicos, pacientes,
-- roles, permisos, menú, empresa, timbrado (salvo la numeración) ni los umbrales de auditoría.
-- NO BORRA ARCHIVOS: los adjuntos del Historial Médico subidos a la carpeta `uploads/` quedan en disco (se limpian a mano).
BEGIN;

-- ---------------------------------------------------------------------------------------------------------------------
-- 0. Administrador a conservar (debe haber exactamente uno) y su funcionario (puede no tener)
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TEMP TABLE _reset_admin ON COMMIT DROP AS
SELECT u.id_usuario, u.id_funcionario
  FROM usuarios u JOIN roles r ON r.id_rol = u.id_rol
 WHERE r.nombre_rol = 'Administrador';

DO $$
BEGIN
    IF (SELECT count(*) FROM _reset_admin) <> 1 THEN
        RAISE EXCEPTION 'Se esperaba exactamente 1 usuario Administrador y hay %. No se borró nada.', (SELECT count(*) FROM _reset_admin);
    END IF;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- 1. Facturación (de los más dependientes a los menos)
-- ---------------------------------------------------------------------------------------------------------------------
DELETE FROM recaudacion_depositar;
DELETE FROM arqueo_caja_det;
DELETE FROM arqueo_caja;
DELETE FROM cobro_cheque;
DELETE FROM cobro_tarjeta;
DELETE FROM cobro_det;
DELETE FROM cobro_cab;
DELETE FROM nota_credito_debito_det;
DELETE FROM nota_credito_debito_cab;
DELETE FROM nota_remision_det;
DELETE FROM nota_remision_cab;
DELETE FROM venta_det;
DELETE FROM cuenta_cobrar;
DELETE FROM venta_cab;
DELETE FROM pedido_venta_det;
DELETE FROM pedido_venta_cab;
DELETE FROM apertura_cierre_caja;

-- ---------------------------------------------------------------------------------------------------------------------
-- 2. Consultorio (todo lo clínico; las ventas que cobraban tratamientos ya se borraron arriba)
-- ---------------------------------------------------------------------------------------------------------------------
DELETE FROM justificativo_medico;
DELETE FROM orden_analisis;
DELETE FROM orden_estudios;
DELETE FROM receta_medicamento;
DELETE FROM recetas;
DELETE FROM sesion_insumos;
DELETE FROM sesion_procedimientos;
DELETE FROM sesiones_tratamiento;
DELETE FROM tratamientos;
DELETE FROM diagnostico_sintoma;
DELETE FROM diagnosticos;
DELETE FROM odontograma_detalle;
DELETE FROM odontograma;
DELETE FROM ficha_medica_consulta;
DELETE FROM consultas_cab;

-- ---------------------------------------------------------------------------------------------------------------------
-- 3. Agendamiento (movimientos)
-- ---------------------------------------------------------------------------------------------------------------------
DELETE FROM avisos_recordatorios;
DELETE FROM historial_medico_paciente;
DELETE FROM cita_detalle;
DELETE FROM cita_cabecera;
DELETE FROM agenda_detalle;
DELETE FROM agenda_cabecera;

-- ---------------------------------------------------------------------------------------------------------------------
-- 4. Seguridad: códigos 2FA, auditorías (inmutables) y usuarios / funcionarios
-- ---------------------------------------------------------------------------------------------------------------------
DELETE FROM token_2fa;

ALTER TABLE auditoria_acceso  DISABLE TRIGGER trg_auditoria_inmutable;
ALTER TABLE auditoria_cambios DISABLE TRIGGER trg_auditoria_inmutable;
DELETE FROM auditoria_acceso;
DELETE FROM auditoria_cambios;
ALTER TABLE auditoria_acceso  ENABLE TRIGGER trg_auditoria_inmutable;
ALTER TABLE auditoria_cambios ENABLE TRIGGER trg_auditoria_inmutable;

DELETE FROM usuarios    WHERE id_usuario NOT IN (SELECT id_usuario FROM _reset_admin);
DELETE FROM funcionario WHERE id_funcionario NOT IN (SELECT id_funcionario FROM _reset_admin WHERE id_funcionario IS NOT NULL);

-- ---------------------------------------------------------------------------------------------------------------------
-- 5. Secuencias de las tablas vaciadas
-- ---------------------------------------------------------------------------------------------------------------------
DO $$
DECLARE
    t   TEXT;
    seq TEXT;
    col TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'recaudacion_depositar', 'arqueo_caja_det', 'arqueo_caja', 'cobro_cheque', 'cobro_tarjeta', 'cobro_det', 'cobro_cab',
        'nota_credito_debito_det', 'nota_credito_debito_cab', 'nota_remision_det', 'nota_remision_cab', 'venta_det', 'cuenta_cobrar', 'venta_cab',
        'pedido_venta_det', 'pedido_venta_cab', 'apertura_cierre_caja',
        'justificativo_medico', 'orden_analisis', 'orden_estudios', 'receta_medicamento', 'recetas', 'sesion_insumos', 'sesion_procedimientos',
        'sesiones_tratamiento', 'tratamientos', 'diagnosticos', 'odontograma_detalle', 'odontograma', 'ficha_medica_consulta', 'consultas_cab',
        'avisos_recordatorios', 'historial_medico_paciente', 'cita_detalle', 'cita_cabecera', 'agenda_detalle', 'agenda_cabecera',
        'token_2fa', 'auditoria_acceso', 'auditoria_cambios'
    ] LOOP
        FOR seq, col IN
            SELECT pg_get_serial_sequence(format('public.%I', t), a.attname), a.attname
              FROM pg_attribute a
             WHERE a.attrelid = format('public.%I', t)::regclass AND a.attnum > 0 AND NOT a.attisdropped
               AND pg_get_serial_sequence(format('public.%I', t), a.attname) IS NOT NULL
        LOOP
            EXECUTE format('ALTER SEQUENCE %s RESTART WITH 1', seq);
        END LOOP;
    END LOOP;

    -- Tablas que conservan una fila: la secuencia sigue desde el id que queda
    FOREACH t IN ARRAY ARRAY['usuarios', 'funcionario'] LOOP
        SELECT pg_get_serial_sequence(format('public.%I', t), a.attname), a.attname INTO seq, col
          FROM pg_attribute a
         WHERE a.attrelid = format('public.%I', t)::regclass AND a.attnum > 0 AND NOT a.attisdropped
           AND pg_get_serial_sequence(format('public.%I', t), a.attname) IS NOT NULL;
        EXECUTE format('SELECT setval(%L, COALESCE((SELECT MAX(%I) FROM %I), 0) + 1, false)', seq, col, t);
    END LOOP;
END $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- 6. Stock inicial de prueba y numeración del timbrado
-- ---------------------------------------------------------------------------------------------------------------------
UPDATE items SET cantidad_disponible = 50
 WHERE id_tipo_item IN (SELECT id_tipo_item FROM tipo_items WHERE controla_stock);
UPDATE timbrado SET numero_actual = 0;

-- ---------------------------------------------------------------------------------------------------------------------
-- 7. Verificación final: si algo no quedó como se espera, la transacción se revierte entera
-- ---------------------------------------------------------------------------------------------------------------------
DO $$
DECLARE
    t TEXT;
    n BIGINT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'recaudacion_depositar', 'arqueo_caja_det', 'arqueo_caja', 'cobro_cheque', 'cobro_tarjeta', 'cobro_det', 'cobro_cab',
        'nota_credito_debito_det', 'nota_credito_debito_cab', 'nota_remision_det', 'nota_remision_cab', 'venta_det', 'cuenta_cobrar', 'venta_cab',
        'pedido_venta_det', 'pedido_venta_cab', 'apertura_cierre_caja',
        'justificativo_medico', 'orden_analisis', 'orden_estudios', 'receta_medicamento', 'recetas', 'sesion_insumos', 'sesion_procedimientos',
        'sesiones_tratamiento', 'tratamientos', 'diagnostico_sintoma', 'diagnosticos', 'odontograma_detalle', 'odontograma', 'ficha_medica_consulta',
        'consultas_cab', 'avisos_recordatorios', 'historial_medico_paciente', 'cita_detalle', 'cita_cabecera', 'agenda_detalle', 'agenda_cabecera',
        'token_2fa', 'auditoria_acceso', 'auditoria_cambios'
    ] LOOP
        EXECUTE format('SELECT count(*) FROM %I', t) INTO n;
        IF n <> 0 THEN
            RAISE EXCEPTION 'La tabla % no quedó vacía (% filas). Se revierte todo.', t, n;
        END IF;
    END LOOP;
    IF (SELECT count(*) FROM usuarios) <> 1 OR NOT EXISTS (SELECT 1 FROM usuarios u JOIN _reset_admin a USING (id_usuario)) THEN
        RAISE EXCEPTION 'Debe quedar solo el usuario Administrador. Se revierte todo.';
    END IF;
    IF (SELECT count(*) FROM funcionario) > 1 THEN
        RAISE EXCEPTION 'Debe quedar a lo sumo el funcionario del Administrador. Se revierte todo.';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_auditoria_inmutable' AND tgenabled = 'D') THEN
        RAISE EXCEPTION 'El trigger de inmutabilidad de la auditoría quedó desactivado. Se revierte todo.';
    END IF;
    IF EXISTS (SELECT 1 FROM timbrado WHERE numero_actual <> 0) THEN
        RAISE EXCEPTION 'El timbrado no quedó en su numeración inicial. Se revierte todo.';
    END IF;
END $$;

COMMIT;
