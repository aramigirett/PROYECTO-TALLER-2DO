"""
=====================================================
DAO: Tratamiento (Gestionar Tratamientos)

Reglas (Ver / Nuevo / Anular / Finalizar; no hay edición):
  - Se registra desde una consulta: lo crea SOLO el médico de esa consulta, con la consulta 'programada' o 'en_proceso', revalidado dentro de la
    transacción con la consulta bloqueada (FOR UPDATE). Paciente, médico y consultorio se heredan de la consulta; estado inicial 'pendiente'.
  - Tipo de tratamiento ACTIVO (FOR SHARE) y descripción obligatoria. Diagnóstico opcional: vigente y de la MISMA consulta (FOR SHARE).
  - Es la cabecera de las sesiones (SesionTratamientoDao): pendiente -> en_seguimiento (1.ª sesión) -> finalizado; 'cancelado' = anulado (definitivo).
  - Anular: médico del tratamiento, consulta (la que lo creó) abierta, sin sesiones vigentes y sin venta EMITIDA (Facturación). Se bloquea la consulta,
    después el tratamiento (mismo orden que las sesiones y la venta de tratamiento bloquea el mismo renglón: facturar y cancelar nunca ganan los dos).
  - Finalizar: solo el médico del tratamiento y desde 'en_seguimiento'; NO exige la consulta abierta (el tratamiento sigue en varias visitas).
  - Un médico solo lee lo suyo. Los tratamientos ya registrados se siguen mostrando aunque su tipo se haya anulado después.
Dato de salud: la auditoría no recibe la descripción.
Facturación (Venta de Tratamiento) lee: id_tratamiento, id_paciente, estado <> 'cancelado', fecha_tratamiento y id_tipo_tratamiento; no se tocan.

NOTA - columnas sin uso (`id_funcionario`, `id_tipo_diagnostico`, `codigo`): sin tocar a propósito.
=====================================================
"""
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta

ESTADOS_ABIERTOS = ('programada', 'en_proceso')

_SELECT = """
    SELECT t.id_tratamiento, t.id_consulta_cab, cc.estado, t.id_diagnostico, t.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad,
           t.id_medico, CONCAT(m.nombre, ' ', m.apellido), t.id_consultorio, co.nombre_consultorio, t.id_tipo_tratamiento, tt.descripcion,
           t.descripcion_tratamiento, t.fecha_tratamiento, t.estado, t.fecha_registro,
           (SELECT COUNT(*) FROM sesiones_tratamiento s WHERE s.id_tratamiento = t.id_tratamiento AND s.activo = true),
           (SELECT v.numero_factura FROM venta_det d JOIN venta_cab v ON v.id_venta = d.id_venta
             WHERE d.id_tratamiento = t.id_tratamiento AND v.estado = 'EMITIDA' LIMIT 1)
    FROM tratamientos t
    JOIN consultas_cab cc ON t.id_consulta_cab = cc.id_consulta_cab
    JOIN paciente p ON t.id_paciente = p.id_paciente
    JOIN medico m ON t.id_medico = m.id_medico
    JOIN tipos_tratamiento tt ON t.id_tipo_tratamiento = tt.id_tipo_tratamiento
    LEFT JOIN consultorio co ON t.id_consultorio = co.codigo"""   # sin filtrar activo del tipo: los viejos se siguen viendo


def _tratamiento(r):
    return {
        'id_tratamiento': r[0], 'id_consulta_cab': r[1], 'numero_consulta': numero_consulta(r[1]), 'estado_consulta': r[2], 'id_diagnostico': r[3],
        'id_paciente': r[4], 'nombre_paciente': r[5], 'cedula_paciente': r[6], 'id_medico': r[7], 'nombre_medico': r[8],
        'id_consultorio': r[9], 'nombre_consultorio': r[10], 'id_tipo_tratamiento': r[11], 'tipo_tratamiento': r[12],
        'descripcion_tratamiento': r[13], 'fecha_tratamiento': r[14].isoformat() if r[14] else None, 'estado': r[15],
        'fecha_registro': r[16].isoformat() if r[16] else None, 'cantidad_sesiones': r[17],
        'facturado': r[18] is not None, 'numero_factura': r[18],
    }


class TratamientoDao:

    # ------------------------------------------------------------------ lectura
    def listar(self, texto=None, estado=None, desde=None, hasta=None, id_medico=None, id_consulta=None, id_paciente=None, en_curso=False,
               pagina=1, por_pagina=25):
        """Tratamientos NO cancelados con filtros, paginados en el servidor. `en_curso` = pendientes y en seguimiento. Devuelve (filas, total)."""
        where, params = ["t.estado <> 'cancelado'", "cc.activo = true"], []
        if texto:
            where.append("(CONCAT(p.nombre, ' ', p.apellido) ILIKE %s OR p.cedula_entidad ILIKE %s OR tt.descripcion ILIKE %s)")
            params += [f'%{texto}%'] * 3
        if estado:
            where.append("t.estado = %s"); params.append(estado)
        if en_curso:
            where.append("t.estado IN ('pendiente', 'en_seguimiento')")
        if desde:
            where.append("t.fecha_tratamiento >= %s"); params.append(desde)
        if hasta:
            where.append("t.fecha_tratamiento <= %s"); params.append(hasta)
        if id_medico:
            where.append("t.id_medico = %s"); params.append(id_medico)
        if id_consulta:
            where.append("t.id_consulta_cab = %s"); params.append(id_consulta)
        if id_paciente:
            where.append("t.id_paciente = %s"); params.append(id_paciente)
        cond = ' AND '.join(where)
        por_pagina = max(1, min(int(por_pagina), 100))
        pagina = max(1, int(pagina))
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"""SELECT COUNT(*) FROM tratamientos t JOIN consultas_cab cc ON t.id_consulta_cab = cc.id_consulta_cab
                            JOIN paciente p ON t.id_paciente = p.id_paciente
                            JOIN tipos_tratamiento tt ON t.id_tipo_tratamiento = tt.id_tipo_tratamiento WHERE {cond}""", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(f"{_SELECT} WHERE {cond} ORDER BY t.fecha_tratamiento DESC, t.id_tratamiento DESC LIMIT %s OFFSET %s",
                        tuple(params) + (por_pagina, (pagina - 1) * por_pagina))
            return [_tratamiento(f) for f in cur.fetchall()], total
        except Exception as e:
            app.logger.error(f"Error al listar tratamientos: {str(e)}")
            return [], 0
        finally:
            cur.close()
            con.close()

    def getTratamientoById(self, id_tratamiento, solo_vigentes=True):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE t.id_tratamiento = %s" + (" AND t.estado <> 'cancelado'" if solo_vigentes else ""), (id_tratamiento,))
            r = cur.fetchone()
            return _tratamiento(r) if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener tratamiento: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getTratamientosByConsulta(self, id_consulta_cab):
        """Los tratamientos NO cancelados creados en una consulta (lookup del combo opcional de Receta y Órdenes)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT t.id_tratamiento, t.id_tipo_tratamiento, tt.descripcion, t.descripcion_tratamiento, t.estado
                           FROM tratamientos t JOIN tipos_tratamiento tt ON tt.id_tipo_tratamiento = t.id_tipo_tratamiento
                           WHERE t.id_consulta_cab = %s AND t.estado <> 'cancelado' ORDER BY t.id_tratamiento""", (id_consulta_cab,))
            return [{'id_tratamiento': r[0], 'id_tipo_tratamiento': r[1], 'tipo_tratamiento': r[2], 'descripcion_tratamiento': r[3], 'estado': r[4]}
                    for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener tratamientos de la consulta: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def guardarTratamiento(self, datos, id_medico_actor):
        """
        Crea el tratamiento en UNA transacción. `datos` ya viene validado (validar_tratamiento) y trae id_consulta_cab.
        Devuelve {'id_tratamiento', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT cc.activo, cc.estado, cc.id_medico, cc.id_paciente, cc.id_consultorio, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad
                           FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente
                           WHERE cc.id_consulta_cab = %s FOR UPDATE OF cc""", (datos['id_consulta_cab'],))
            consulta = cur.fetchone()
            if not consulta or not consulta[0]:
                con.rollback()
                return {'error': 'CONSULTA_NO_ENCONTRADA'}
            _, estado, id_medico, id_paciente, id_consultorio, paciente, cedula = consulta
            if id_medico_actor is None or id_medico_actor != id_medico:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if estado not in ESTADOS_ABIERTOS:
                con.rollback()
                return {'error': 'CONSULTA_NO_ABIERTA', 'estado': estado}
            # el tipo y el diagnóstico se bloquean FOR SHARE: una baja concurrente espera a que este tratamiento termine
            cur.execute("SELECT activo, descripcion FROM tipos_tratamiento WHERE id_tipo_tratamiento = %s FOR SHARE", (datos['id_tipo_tratamiento'],))
            tipo = cur.fetchone()
            if not tipo:
                con.rollback()
                return {'error': 'TIPO_NO_EXISTE'}
            if not tipo[0]:
                con.rollback()
                return {'error': 'TIPO_INACTIVO'}
            if datos.get('id_diagnostico'):
                cur.execute("SELECT activo, id_consulta_cab FROM diagnosticos WHERE id_diagnostico = %s FOR SHARE", (datos['id_diagnostico'],))
                dx = cur.fetchone()
                if not dx or not dx[0] or dx[1] != datos['id_consulta_cab']:
                    con.rollback()
                    return {'error': 'DIAGNOSTICO_INVALIDO'}
            cur.execute("""INSERT INTO tratamientos(id_consulta_cab, id_diagnostico, id_paciente, id_medico, id_consultorio, id_tipo_tratamiento,
                                                    descripcion_tratamiento, fecha_tratamiento, estado)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendiente') RETURNING id_tratamiento""",
                        (datos['id_consulta_cab'], datos.get('id_diagnostico'), id_paciente, id_medico, id_consultorio, datos['id_tipo_tratamiento'],
                         datos['descripcion_tratamiento'], datos['fecha_tratamiento']))
            nuevo = cur.fetchone()[0]
            con.commit()
            return {'id_tratamiento': nuevo, 'contexto': {'paciente': paciente, 'cedula': cedula, 'tipo': tipo[1]}}
        except Exception as e:
            app.logger.error(f"Error al guardar tratamiento: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anulación
    def anularTratamiento(self, id_tratamiento, id_medico_actor):
        """
        Anula (baja lógica definitiva: estado 'cancelado'). Bloquea la consulta y después el tratamiento. Rechaza si el actor no es su médico, la consulta que
        lo creó no está abierta, tiene sesiones vigentes (EN_USO) o una venta EMITIDA (FACTURADO).
        Devuelve {'ok', 'id_consulta_cab', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_consulta_cab FROM tratamientos WHERE id_tratamiento = %s AND estado <> 'cancelado'", (id_tratamiento,))
            fila = cur.fetchone()
            if not fila:
                con.rollback()
                return {'error': 'TRATAMIENTO_NO_ENCONTRADO'}
            id_consulta = fila[0]
            cur.execute("""SELECT cc.estado, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad
                           FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente
                           WHERE cc.id_consulta_cab = %s FOR UPDATE OF cc""", (id_consulta,))
            estado_consulta, paciente, cedula = cur.fetchone()
            cur.execute("""SELECT t.id_medico, tt.descripcion FROM tratamientos t JOIN tipos_tratamiento tt ON tt.id_tipo_tratamiento = t.id_tipo_tratamiento
                           WHERE t.id_tratamiento = %s AND t.estado <> 'cancelado' FOR UPDATE OF t""", (id_tratamiento,))
            trat = cur.fetchone()
            if not trat:
                con.rollback()
                return {'error': 'TRATAMIENTO_NO_ENCONTRADO'}
            if id_medico_actor is None or id_medico_actor != trat[0]:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if estado_consulta not in ESTADOS_ABIERTOS:
                con.rollback()
                return {'error': 'CONSULTA_NO_ABIERTA', 'estado': estado_consulta}
            cur.execute("""SELECT v.numero_factura FROM venta_det d JOIN venta_cab v ON v.id_venta = d.id_venta
                           WHERE d.id_tratamiento = %s AND v.estado = 'EMITIDA' LIMIT 1""", (id_tratamiento,))
            factura = cur.fetchone()
            if factura:
                con.rollback()
                return {'error': 'FACTURADO', 'numero_factura': factura[0]}
            cur.execute("SELECT 1 FROM sesiones_tratamiento WHERE id_tratamiento = %s AND activo = true LIMIT 1", (id_tratamiento,))
            if cur.fetchone():
                con.rollback()
                return {'error': 'EN_USO'}
            cur.execute("UPDATE tratamientos SET estado = 'cancelado' WHERE id_tratamiento = %s", (id_tratamiento,))
            con.commit()
            return {'ok': True, 'id_consulta_cab': id_consulta, 'contexto': {'paciente': paciente, 'cedula': cedula, 'tipo': trat[1]}}
        except Exception as e:
            app.logger.error(f"Error al anular tratamiento: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ finalizar
    def finalizarTratamiento(self, id_tratamiento, id_medico_actor):
        """
        Pasa el tratamiento de 'en_seguimiento' a 'finalizado' (solo su médico; no exige la consulta abierta). Un 'pendiente' no tiene sesiones: se anula.
        Devuelve {'ok', 'id_consulta_cab', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT t.id_medico, t.estado, t.id_consulta_cab, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad, tt.descripcion
                           FROM tratamientos t JOIN paciente p ON p.id_paciente = t.id_paciente
                           JOIN tipos_tratamiento tt ON tt.id_tipo_tratamiento = t.id_tipo_tratamiento
                           WHERE t.id_tratamiento = %s FOR UPDATE OF t""", (id_tratamiento,))
            t = cur.fetchone()
            if not t or t[1] == 'cancelado':
                con.rollback()
                return {'error': 'TRATAMIENTO_NO_ENCONTRADO'}
            if id_medico_actor is None or id_medico_actor != t[0]:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if t[1] == 'pendiente':
                con.rollback()
                return {'error': 'PENDIENTE_SIN_SESIONES'}
            if t[1] == 'finalizado':
                con.rollback()
                return {'error': 'YA_FINALIZADO'}
            cur.execute("UPDATE tratamientos SET estado = 'finalizado' WHERE id_tratamiento = %s", (id_tratamiento,))
            con.commit()
            return {'ok': True, 'id_consulta_cab': t[2], 'contexto': {'paciente': t[3], 'cedula': t[4], 'tipo': t[5]}}
        except Exception as e:
            app.logger.error(f"Error al finalizar tratamiento: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()
