"""
=====================================================
DAO: Justificativo Médico (Generar Justificativo Médico)

Reglas (ver documento_clinico.py para las comunes):
  - Estados: 'pendiente' (se registra así: borrador) -> 'emitido' (la acción "Generar" lo emite y recién ahí es el documento oficial) | 'anulado' (definitivo).
  - Se registra desde una consulta: lo crea SOLO el médico de esa consulta, con la consulta 'programada' / 'en_proceso' revalidada con la consulta bloqueada
    (FOR UPDATE). Paciente y médico se heredan; la fecha la fija el servidor. Vínculo opcional SOLO con un diagnóstico vigente de la misma consulta (FOR SHARE).
  - Emitir (permiso `estado`): solo el médico de la consulta, desde 'pendiente'; se permite con la consulta FINALIZADA (como las órdenes) y no con la cancelada
    ni anulada. Bloquea la consulta (FOR SHARE) y después el justificativo (FOR UPDATE).
  - Anular (definitivo): médico de la consulta y consulta abierta (no con la consulta finalizada), desde 'pendiente' o 'emitido'.
Dato de salud: la auditoría no recibe los días de reposo ni las recomendaciones; el PDF sí.
=====================================================
"""
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta
from app.dao.referenciales_consultorio.documento_clinico import (
    ESTADOS_ABIERTOS, PREFIJO_JUSTIFICATIVO, bloquear_consulta, datos_para_pdf, numero_documento)

ESTADOS = ('pendiente', 'emitido', 'anulado')

_SELECT = """
    SELECT j.id_justificativo, j.id_consulta_cab, cc.estado, j.id_diagnostico, d.codigo, j.dias_reposo, j.recomendaciones, j.fecha_justificativo, j.estado,
           j.fecha_registro, cc.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad, cc.id_medico, CONCAT(m.nombre, ' ', m.apellido)
    FROM justificativo_medico j
    JOIN consultas_cab cc ON j.id_consulta_cab = cc.id_consulta_cab
    JOIN paciente p ON cc.id_paciente = p.id_paciente
    JOIN medico m ON cc.id_medico = m.id_medico
    LEFT JOIN diagnosticos d ON d.id_diagnostico = j.id_diagnostico"""


def _justificativo(r):
    return {
        'id_justificativo': r[0], 'id_consulta_cab': r[1], 'numero_consulta': numero_consulta(r[1]), 'estado_consulta': r[2], 'id_diagnostico': r[3], 'codigo_diagnostico': r[4],
        'dias_reposo': r[5], 'recomendaciones': r[6], 'fecha_justificativo': r[7].isoformat() if r[7] else None, 'estado': r[8],
        'fecha_registro': r[9].isoformat() if r[9] else None, 'id_paciente': r[10], 'nombre_paciente': r[11], 'cedula_paciente': r[12], 'id_medico': r[13],
        'nombre_medico': r[14], 'numero': numero_documento(PREFIJO_JUSTIFICATIVO, r[0]),
    }


class JustificativoMedicoDao:

    # ------------------------------------------------------------------ lectura
    def listar(self, texto=None, estado=None, desde=None, hasta=None, id_medico=None, id_consulta=None, pagina=1, por_pagina=25):
        """Justificativos NO anulados (salvo que se pida el estado) con filtros, paginados en el servidor. Devuelve (filas, total)."""
        where, params = ["cc.activo = true"], []
        if estado:
            where.append("j.estado = %s"); params.append(estado)
        else:
            where.append("j.estado <> 'anulado'")
        if texto:
            where.append("(CONCAT(p.nombre, ' ', p.apellido) ILIKE %s OR p.cedula_entidad ILIKE %s)")
            params += [f'%{texto}%'] * 2
        if desde:
            where.append("j.fecha_justificativo >= %s"); params.append(desde)
        if hasta:
            where.append("j.fecha_justificativo <= %s"); params.append(hasta)
        if id_medico:
            where.append("cc.id_medico = %s"); params.append(id_medico)
        if id_consulta:
            where.append("j.id_consulta_cab = %s"); params.append(id_consulta)
        cond = ' AND '.join(where)
        por_pagina = max(1, min(int(por_pagina), 100))
        pagina = max(1, int(pagina))
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"""SELECT COUNT(*) FROM justificativo_medico j JOIN consultas_cab cc ON j.id_consulta_cab = cc.id_consulta_cab
                            JOIN paciente p ON cc.id_paciente = p.id_paciente WHERE {cond}""", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(f"{_SELECT} WHERE {cond} ORDER BY j.fecha_justificativo DESC, j.id_justificativo DESC LIMIT %s OFFSET %s", tuple(params) + (por_pagina, (pagina - 1) * por_pagina))
            return [_justificativo(f) for f in cur.fetchall()], total
        except Exception as e:
            app.logger.error(f"Error al listar justificativos: {str(e)}")
            return [], 0
        finally:
            cur.close()
            con.close()

    def getJustificativoById(self, id_justificativo, solo_vigentes=True):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE j.id_justificativo = %s" + (" AND j.estado <> 'anulado'" if solo_vigentes else ""), (id_justificativo,))
            r = cur.fetchone()
            return _justificativo(r) if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener justificativo: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getParaPdf(self, id_justificativo):
        """El justificativo (aunque esté anulado: se descarga con la marca) con la clínica y el médico (especialidad, N.º de registro) para el PDF."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE j.id_justificativo = %s", (id_justificativo,))
            r = cur.fetchone()
            if not r:
                return None
            d = _justificativo(r)
            d['empresa'], d['medico'] = datos_para_pdf(cur, r[1])
            return d
        except Exception as e:
            app.logger.error(f"Error al leer el justificativo para el PDF: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def guardarJustificativo(self, datos, id_medico_actor):
        """
        Registra el justificativo en estado 'pendiente' en UNA transacción. `datos` ya viene validado (validar_justificativo) y trae id_consulta_cab.
        Devuelve {'id_justificativo', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            consulta = bloquear_consulta(cur, datos['id_consulta_cab'], 'UPDATE')
            if not consulta:
                con.rollback()
                return {'error': 'CONSULTA_NO_ENCONTRADA'}
            if id_medico_actor is None or id_medico_actor != consulta['id_medico']:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if consulta['estado'] not in ESTADOS_ABIERTOS:
                con.rollback()
                return {'error': 'CONSULTA_NO_ABIERTA', 'estado': consulta['estado']}
            if datos.get('id_diagnostico'):
                cur.execute("SELECT activo, id_consulta_cab FROM diagnosticos WHERE id_diagnostico = %s FOR SHARE", (datos['id_diagnostico'],))
                dx = cur.fetchone()
                if not dx or not dx[0] or dx[1] != datos['id_consulta_cab']:
                    con.rollback()
                    return {'error': 'DIAGNOSTICO_INVALIDO'}
            cur.execute("""INSERT INTO justificativo_medico(id_consulta_cab, id_diagnostico, dias_reposo, recomendaciones, fecha_justificativo, estado)
                           VALUES (%s, %s, %s, %s, CURRENT_DATE, 'pendiente') RETURNING id_justificativo""",
                        (datos['id_consulta_cab'], datos.get('id_diagnostico'), datos['dias_reposo'], datos.get('recomendaciones')))
            nuevo = cur.fetchone()[0]
            con.commit()
            return {'id_justificativo': nuevo, 'contexto': {'paciente': consulta['paciente'], 'cedula': consulta['cedula']}}
        except Exception as e:
            app.logger.error(f"Error al guardar justificativo: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ emitir ("Generar Justificativo")
    def emitirJustificativo(self, id_justificativo, id_medico_actor):
        """
        Pasa el justificativo de 'pendiente' a 'emitido' (documento oficial). Solo el médico de la consulta; se permite con la consulta finalizada, no con la cancelada
        ni anulada. Devuelve {'ok', 'id_consulta_cab', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_consulta_cab FROM justificativo_medico WHERE id_justificativo = %s", (id_justificativo,))
            fila = cur.fetchone()
            if not fila:
                con.rollback()
                return {'error': 'JUSTIFICATIVO_NO_ENCONTRADO'}
            id_consulta = fila[0]
            consulta = bloquear_consulta(cur, id_consulta, 'SHARE')
            cur.execute("SELECT estado FROM justificativo_medico WHERE id_justificativo = %s FOR UPDATE", (id_justificativo,))
            estado = cur.fetchone()[0]
            if estado == 'anulado':
                con.rollback()
                return {'error': 'JUSTIFICATIVO_NO_ENCONTRADO'}
            if not consulta:
                con.rollback()
                return {'error': 'CONSULTA_NO_ENCONTRADA'}
            if id_medico_actor is None or id_medico_actor != consulta['id_medico']:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if consulta['estado'] == 'cancelada':
                con.rollback()
                return {'error': 'CONSULTA_CANCELADA'}
            if estado == 'emitido':
                con.rollback()
                return {'error': 'YA_EMITIDO'}
            cur.execute("UPDATE justificativo_medico SET estado = 'emitido' WHERE id_justificativo = %s", (id_justificativo,))
            con.commit()
            return {'ok': True, 'id_consulta_cab': id_consulta, 'contexto': {'paciente': consulta['paciente'], 'cedula': consulta['cedula']}}
        except Exception as e:
            app.logger.error(f"Error al emitir justificativo: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anulación
    def anularJustificativo(self, id_justificativo, id_medico_actor):
        """
        Anula (definitivo) un justificativo pendiente o emitido. Bloquea la consulta y después el justificativo. Rechaza si el actor no es el médico de la consulta o
        la consulta no está abierta (finalizada incluida). Devuelve {'ok', 'anterior', 'id_consulta_cab', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_consulta_cab FROM justificativo_medico WHERE id_justificativo = %s AND estado <> 'anulado'", (id_justificativo,))
            fila = cur.fetchone()
            if not fila:
                con.rollback()
                return {'error': 'JUSTIFICATIVO_NO_ENCONTRADO'}
            id_consulta = fila[0]
            consulta = bloquear_consulta(cur, id_consulta, 'UPDATE')
            cur.execute("SELECT estado FROM justificativo_medico WHERE id_justificativo = %s FOR UPDATE", (id_justificativo,))
            estado = cur.fetchone()[0]
            if estado == 'anulado':
                con.rollback()
                return {'error': 'JUSTIFICATIVO_NO_ENCONTRADO'}
            if not consulta:
                con.rollback()
                return {'error': 'CONSULTA_NO_ENCONTRADA'}
            if id_medico_actor is None or id_medico_actor != consulta['id_medico']:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if consulta['estado'] not in ESTADOS_ABIERTOS:
                con.rollback()
                return {'error': 'CONSULTA_NO_ABIERTA', 'estado': consulta['estado']}
            cur.execute("UPDATE justificativo_medico SET estado = 'anulado' WHERE id_justificativo = %s", (id_justificativo,))
            con.commit()
            return {'ok': True, 'anterior': estado, 'id_consulta_cab': id_consulta, 'contexto': {'paciente': consulta['paciente'], 'cedula': consulta['cedula']}}
        except Exception as e:
            app.logger.error(f"Error al anular justificativo: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()
