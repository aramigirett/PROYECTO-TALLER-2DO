-- Migración 03: módulo INFORMES (una sola pantalla /informes, solo consulta, exclusiva del Administrador).
-- Idempotente y en una transacción. Se aplica con postgres y PGCLIENTENCODING=UTF8, DESPUÉS de un backup.
-- Qué hace:
--   1. Vistas v_inf_* con los datos agregables de cada pestaña (una fila por hecho; el API filtra por fecha / médico / condición con parámetros).
--      Ninguna expone datos clínicos de pacientes: las vistas de Consultorio solo traen ids, fechas y descripciones de catálogo.
--   2. GRANT SELECT de las vistas a odontoclinic_app (la app corre sin privilegios de DDL).
--   3. Acción 'CONSULTA' en el CHECK de auditoria_cambios (visita a un informe).
--   4. Módulo "Informes" y ventana `informes` en la tabla menu (solo Administrador).
BEGIN;

-- ============================ AGENDAMIENTO ============================
-- Una fila por cita (cita_detalle) de una cabecera ACTIVA. `categoria`:
--   ATENDIDA (Realizado) | CANCELADA | REPROGRAMADA | AUSENTE ("No Asistió" + Confirmado con fecha pasada y sin consulta) | PENDIENTE (el resto)
CREATE OR REPLACE VIEW v_inf_citas AS
SELECT d.id_cita_detalle, d.fecha_cita, d.hora_cita, d.id_estado_cita, e.descripcion AS estado_cita,
       ac.id_medico, m.nombre || ' ' || m.apellido AS medico,
       p.id_paciente, p.nombre || ' ' || p.apellido AS paciente, p.cedula_entidad AS ci_paciente,
       EXISTS (SELECT 1 FROM consultas_cab c WHERE c.id_cita = d.id_cita_detalle AND c.activo) AS tiene_consulta,
       CASE
           WHEN d.id_estado_cita = 3 THEN 'ATENDIDA'
           WHEN d.id_estado_cita = 4 THEN 'CANCELADA'
           WHEN d.id_estado_cita = 6 THEN 'REPROGRAMADA'
           WHEN d.id_estado_cita = 5 THEN 'AUSENTE'
           WHEN d.id_estado_cita = 2 AND d.fecha_cita < CURRENT_DATE
                AND NOT EXISTS (SELECT 1 FROM consultas_cab c WHERE c.id_cita = d.id_cita_detalle AND c.activo) THEN 'AUSENTE'
           ELSE 'PENDIENTE'
       END AS categoria
  FROM cita_detalle d
  JOIN cita_cabecera cc ON cc.id_cita_cabecera = d.id_cita_cabecera AND cc.estado = 'Activo'
  JOIN agenda_cabecera ac ON ac.id_agenda_cabecera = cc.id_agenda_cabecera
  JOIN medico m ON m.id_medico = ac.id_medico
  JOIN paciente p ON p.id_paciente = cc.id_paciente
  JOIN estado_cita e ON e.id_estado_cita = d.id_estado_cita;

-- ============================ CONSULTORIO (sin pacientes por nombre ni contenido clínico) ============================
-- Una fila por consulta activa que no está cancelada. `primera_consulta` = fecha de la primera consulta del paciente (para "pacientes nuevos").
CREATE OR REPLACE VIEW v_inf_consultas AS
SELECT c.id_consulta_cab, c.fecha_cita AS fecha, c.id_medico, m.nombre || ' ' || m.apellido AS medico, c.id_paciente, c.estado,
       MIN(c.fecha_cita) OVER (PARTITION BY c.id_paciente) AS primera_consulta
  FROM consultas_cab c
  JOIN medico m ON m.id_medico = c.id_medico
 WHERE c.activo AND c.estado <> 'cancelada';

CREATE OR REPLACE VIEW v_inf_diagnosticos AS
SELECT d.id_diagnostico, d.fecha_diagnostico AS fecha, d.id_medico, td.descripcion_diagnostico AS tipo
  FROM diagnosticos d
  JOIN tipo_diagnostico td ON td.id_tipo_diagnostico = d.id_tipo_diagnostico
 WHERE d.activo;

CREATE OR REPLACE VIEW v_inf_tratamientos AS
SELECT t.id_tratamiento, t.fecha_tratamiento AS fecha, t.id_medico, t.estado, tt.descripcion AS tipo
  FROM tratamientos t
  JOIN tipos_tratamiento tt ON tt.id_tipo_tratamiento = t.id_tipo_tratamiento;

CREATE OR REPLACE VIEW v_inf_procedimientos AS
SELECT sp.id_sesion_procedimiento, s.fecha_sesion AS fecha, t.id_medico, tp.descripcion
  FROM sesion_procedimientos sp
  JOIN sesiones_tratamiento s ON s.id_sesion = sp.id_sesion AND s.activo
  JOIN tratamientos t ON t.id_tratamiento = s.id_tratamiento
  JOIN tipo_procedimiento_medico tp ON tp.id_tipo_procedimiento = sp.id_tipo_procedimiento
 WHERE sp.activo;

CREATE OR REPLACE VIEW v_inf_insumos AS
SELECT si.id_sesion_insumo, s.fecha_sesion AS fecha, t.id_medico, i.descripcion, si.cantidad
  FROM sesion_insumos si
  JOIN sesiones_tratamiento s ON s.id_sesion = si.id_sesion AND s.activo
  JOIN tratamientos t ON t.id_tratamiento = s.id_tratamiento
  JOIN insumos i ON i.id_insumo = si.id_insumo
 WHERE si.activo;

-- ============================ FACTURACIÓN ============================
-- Facturas y notas en una sola lista. Los importes de las notas van con SIGNO (crédito resta, débito suma); la condición de una nota es la de
-- la venta de su cuenta. Los totales del informe cuentan solo estado EMITIDA.
CREATE OR REPLACE VIEW v_inf_comprobantes AS
SELECT 'FACTURA'::text AS tipo, v.id_venta AS id_comprobante, v.fecha::date AS fecha, v.numero_factura AS numero,
       cl.nombre || COALESCE(' ' || cl.apellido, '') AS cliente, cl.ci_ruc, v.condicion, v.estado,
       v.total_exenta AS exenta, v.total_gravada_5 AS gravada_5, v.total_gravada_10 AS gravada_10,
       v.iva_5, v.iva_10, v.total
  FROM venta_cab v
  JOIN cliente cl ON cl.id_cliente = v.id_cliente
UNION ALL
SELECT CASE n.tipo_nota WHEN 'CREDITO' THEN 'NOTA DE CRÉDITO' ELSE 'NOTA DE DÉBITO' END, n.id_nota, n.fecha::date, n.numero_nota,
       cl.nombre || COALESCE(' ' || cl.apellido, ''), cl.ci_ruc, v.condicion, n.estado,
       n.total_exenta * s.signo, n.total_gravada_5 * s.signo, n.total_gravada_10 * s.signo,
       n.iva_5 * s.signo, n.iva_10 * s.signo, n.total * s.signo
  FROM nota_credito_debito_cab n
  CROSS JOIN LATERAL (SELECT CASE n.tipo_nota WHEN 'CREDITO' THEN -1 ELSE 1 END AS signo) s
  JOIN cuenta_cobrar cc ON cc.id_cuenta = n.id_cuenta
  JOIN venta_cab v ON v.id_venta = cc.id_venta
  JOIN cliente cl ON cl.id_cliente = v.id_cliente;

-- Una fila por forma de cobro de cada cobro EMITIDO (condición = la de la venta de la cuenta).
CREATE OR REPLACE VIEW v_inf_cobros AS
SELECT d.id_cobro_det, c.id_cobro, c.fecha::date AS fecha, fc.descripcion AS forma_cobro, d.monto, v.condicion
  FROM cobro_cab c
  JOIN cobro_det d ON d.id_cobro = c.id_cobro
  JOIN forma_cobro fc ON fc.id_forma_cobro = d.id_forma_cobro
  JOIN cuenta_cobrar cc ON cc.id_cuenta = c.id_cuenta
  JOIN venta_cab v ON v.id_venta = cc.id_venta
 WHERE c.estado = 'EMITIDO';

-- Cuentas a cobrar (el saldo ya incluye notas de crédito y débito: lo aplica trg_aplicar_nota).
CREATE OR REPLACE VIEW v_inf_cuentas_cobrar AS
SELECT cc.id_cuenta, v.fecha::date AS fecha, v.numero_factura, cl.nombre || COALESCE(' ' || cl.apellido, '') AS cliente, cl.ci_ruc,
       v.condicion, cc.monto_total, cc.saldo, cc.fecha_vencimiento, cc.estado,
       GREATEST(CURRENT_DATE - cc.fecha_vencimiento, 0) AS dias_vencida
  FROM cuenta_cobrar cc
  JOIN venta_cab v ON v.id_venta = cc.id_venta
  JOIN cliente cl ON cl.id_cliente = cc.id_cliente;

-- ============================ AUDITORÍA (accesos) ============================
-- `resultado_informe`: EXITOSO (LOGIN EXITOSO) | FALLIDO (LOGIN / 2FA con resultado distinto de EXITOSO) | OTRO.
CREATE OR REPLACE VIEW v_inf_accesos AS
SELECT a.id_auditoria, a.fecha_hora, a.fecha_hora::date AS fecha, a.accion, a.resultado, a.ip, a.id_usuario, a.ci_ruc_ingresado,
       CASE
           WHEN a.accion = 'LOGIN' AND a.resultado = 'EXITOSO' THEN 'EXITOSO'
           WHEN a.accion IN ('LOGIN', 'VERIFICACION_2FA') AND a.resultado <> 'EXITOSO' THEN 'FALLIDO'
           ELSE 'OTRO'
       END AS resultado_informe
  FROM auditoria_acceso a;

-- ============================ PERMISOS DE LA APLICACIÓN ============================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'odontoclinic_app') THEN
        -- los privilegios por defecto de postgres dan INSERT / UPDATE / DELETE a lo nuevo: las vistas son solo lectura
        REVOKE ALL ON v_inf_citas, v_inf_consultas, v_inf_diagnosticos, v_inf_tratamientos, v_inf_procedimientos, v_inf_insumos,
                      v_inf_comprobantes, v_inf_cobros, v_inf_cuentas_cobrar, v_inf_accesos FROM odontoclinic_app;
        GRANT SELECT ON v_inf_citas, v_inf_consultas, v_inf_diagnosticos, v_inf_tratamientos, v_inf_procedimientos, v_inf_insumos,
                        v_inf_comprobantes, v_inf_cobros, v_inf_cuentas_cobrar, v_inf_accesos TO odontoclinic_app;
    END IF;
END $$;

-- ============================ AUDITORÍA DE CAMBIOS: acción CONSULTA ============================
DO $$
DECLARE nombre text;
BEGIN
    SELECT conname INTO nombre FROM pg_constraint
     WHERE conrelid = 'auditoria_cambios'::regclass AND contype = 'c' AND pg_get_constraintdef(oid) LIKE '%EXPORTACION%' AND pg_get_constraintdef(oid) NOT LIKE '%CONSULTA%';
    IF nombre IS NOT NULL THEN
        EXECUTE format('ALTER TABLE auditoria_cambios DROP CONSTRAINT %I', nombre);
        ALTER TABLE auditoria_cambios ADD CONSTRAINT auditoria_cambios_accion_check
            CHECK (accion IN ('ALTA', 'MODIFICACION', 'BAJA', 'REACTIVACION', 'CIERRE', 'EXPORTACION', 'CONSULTA'));
    END IF;
END $$;

-- ============================ MENÚ ============================
INSERT INTO menu (id_menu_padre, clave, descripcion, ruta, icono, orden)
SELECT NULL, NULL, 'Informes', NULL, 'fa-chart-line', 8
 WHERE NOT EXISTS (SELECT 1 FROM menu x WHERE x.id_menu_padre IS NULL AND x.clave IS NULL AND UPPER(x.descripcion) = 'INFORMES');

INSERT INTO menu (id_menu_padre, clave, descripcion, ruta, icono, orden, visible_en_menu, solo_admin)
SELECT p.id_menu, 'informes', 'Informes', 'informes.informesIndex', 'fa-chart-line', 10, true, true
  FROM menu p
 WHERE p.id_menu_padre IS NULL AND p.clave IS NULL AND UPPER(p.descripcion) = 'INFORMES' AND p.activo
   AND NOT EXISTS (SELECT 1 FROM menu x WHERE x.clave = 'informes' AND x.activo);

COMMIT;
