"""
=====================================================
DAO: Diagnóstico (diagnosticos + diagnostico_sintoma)

Reglas (Gestionar Diagnóstico: Ver / Nuevo / Anular; no hay edición):
  - Se registra desde una consulta: la crea SOLO el médico de esa consulta, con la consulta 'programada' o 'en_proceso', revalidado dentro de la
    transacción con la consulta bloqueada (FOR UPDATE). Paciente y médico se heredan de la consulta; la fecha la fija el servidor.
  - Tipo de diagnóstico ACTIVO y AL MENOS UN síntoma, todos activos: se bloquean FOR SHARE (una baja concurrente espera).
  - Anular (definitiva): médico de la consulta, consulta abierta y SIN tratamiento vigente asociado (los cancelados no cuentan).
  - Los diagnósticos ya registrados se siguen mostrando aunque su tipo o sus síntomas se hayan anulado después (los JOIN no filtran `activo`).
Dato de salud: la auditoría no recibe tipo, síntomas, descripción, pieza ni observaciones.
=====================================================
"""
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta

ESTADOS_ABIERTOS = ('programada', 'en_proceso')

_SELECT = """
    SELECT d.id_diagnostico, d.codigo, d.id_consulta_cab, cc.estado, d.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad,
           d.id_medico, CONCAT(m.nombre, ' ', m.apellido), d.id_tipo_diagnostico, td.descripcion_diagnostico, td.tipo_diagnostico,
           d.descripcion_diagnostico, d.pieza_dental, d.fecha_diagnostico, d.observaciones, d.fecha_registro, d.activo
    FROM diagnosticos d
    JOIN consultas_cab cc ON d.id_consulta_cab = cc.id_consulta_cab
    JOIN paciente p ON d.id_paciente = p.id_paciente
    JOIN medico m ON d.id_medico = m.id_medico
    JOIN tipo_diagnostico td ON d.id_tipo_diagnostico = td.id_tipo_diagnostico"""   # sin filtrar activo: los viejos se siguen viendo


def _diagnostico(r, sintomas=None):
    d = {
        'id_diagnostico': r[0], 'codigo': r[1], 'id_consulta_cab': r[2], 'numero_consulta': numero_consulta(r[2]), 'estado_consulta': r[3],
        'id_paciente': r[4], 'nombre_paciente': r[5], 'cedula_paciente': r[6], 'id_medico': r[7], 'nombre_medico': r[8],
        'id_tipo_diagnostico': r[9], 'tipo_diagnostico': r[10], 'categoria_tipo': r[11],
        'descripcion_diagnostico': r[12], 'pieza_dental': r[13],
        'fecha_diagnostico': r[14].isoformat() if r[14] else None, 'observaciones': r[15],
        'fecha_registro': r[16].isoformat() if r[16] else None, 'activo': r[17],
    }
    if sintomas is not None:
        d['sintomas'] = sintomas
    return d


class DiagnosticoDao:

    # ------------------------------------------------------------------ lectura
    def _sintomas(self, cur, ids_diagnostico):
        if not ids_diagnostico:
            return {}
        cur.execute("""SELECT ds.id_diagnostico, s.id_sintoma, s.descripcion_sintoma FROM diagnostico_sintoma ds
                       JOIN sintoma s ON s.id_sintoma = ds.id_sintoma WHERE ds.id_diagnostico = ANY(%s) ORDER BY s.descripcion_sintoma""",
                    (list(ids_diagnostico),))
        por_dx = {}
        for dx, i, desc in cur.fetchall():
            por_dx.setdefault(dx, []).append({'id_sintoma': i, 'descripcion_sintoma': desc})
        return por_dx

    def _filas(self, sql, params, con_sintomas=True):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            filas = cur.fetchall()
            sint = self._sintomas(cur, [f[0] for f in filas]) if con_sintomas else {}
            return [_diagnostico(f, sint.get(f[0], []) if con_sintomas else None) for f in filas]
        except Exception as e:
            app.logger.error(f"Error al leer diagnósticos: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def listar(self, texto=None, desde=None, hasta=None, id_medico=None, id_consulta=None, id_paciente=None, pagina=1, por_pagina=25):
        """Diagnósticos VIGENTES con filtros, paginados en el servidor. Devuelve (filas, total)."""
        where, params = ["d.activo = true", "cc.activo = true"], []
        if texto:
            where.append("(d.codigo ILIKE %s OR CONCAT(p.nombre, ' ', p.apellido) ILIKE %s OR p.cedula_entidad ILIKE %s)")
            params += [f'%{texto}%'] * 3
        if desde:
            where.append("d.fecha_diagnostico >= %s"); params.append(desde)
        if hasta:
            where.append("d.fecha_diagnostico <= %s"); params.append(hasta)
        if id_medico:
            where.append("cc.id_medico = %s"); params.append(id_medico)
        if id_consulta:
            where.append("d.id_consulta_cab = %s"); params.append(id_consulta)
        if id_paciente:
            where.append("d.id_paciente = %s"); params.append(id_paciente)
        cond = ' AND '.join(where)
        por_pagina = max(1, min(int(por_pagina), 100))
        pagina = max(1, int(pagina))
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"""SELECT COUNT(*) FROM diagnosticos d JOIN consultas_cab cc ON d.id_consulta_cab = cc.id_consulta_cab
                            JOIN paciente p ON d.id_paciente = p.id_paciente WHERE {cond}""", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(f"{_SELECT} WHERE {cond} ORDER BY d.fecha_diagnostico DESC, d.id_diagnostico DESC LIMIT %s OFFSET %s",
                        tuple(params) + (por_pagina, (pagina - 1) * por_pagina))
            filas = cur.fetchall()
            sint = self._sintomas(cur, [f[0] for f in filas])
            return [_diagnostico(f, sint.get(f[0], [])) for f in filas], total
        except Exception as e:
            app.logger.error(f"Error al listar diagnósticos: {str(e)}")
            return [], 0
        finally:
            cur.close()
            con.close()

    def getDiagnosticoById(self, id_diagnostico, solo_vigentes=True):
        filas = self._filas(_SELECT + " WHERE d.id_diagnostico = %s" + (" AND d.activo = true" if solo_vigentes else ""), (id_diagnostico,))
        return filas[0] if filas else None

    def getDiagnosticosByConsulta(self, id_consulta_cab):
        """Los diagnósticos VIGENTES de una consulta (lookup de los combos de Tratamiento, Receta, Órdenes y Justificativo)."""
        return self._filas(_SELECT + " WHERE d.id_consulta_cab = %s AND d.activo = true ORDER BY d.id_diagnostico", (id_consulta_cab,))

    # ------------------------------------------------------------------ alta
    def guardarDiagnostico(self, datos, id_usuario, id_medico_actor):
        """
        Crea el diagnóstico con sus síntomas en UNA transacción. `datos` ya viene validado (validar_diagnostico) y trae id_consulta_cab.
        Devuelve {'id_diagnostico', 'codigo', 'contexto'} o {'error': CÓDIGO, 'detalle': ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT cc.activo, cc.estado, cc.id_medico, cc.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad
                           FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente
                           WHERE cc.id_consulta_cab = %s FOR UPDATE OF cc""", (datos['id_consulta_cab'],))
            consulta = cur.fetchone()
            if not consulta or not consulta[0]:
                con.rollback()
                return {'error': 'CONSULTA_NO_ENCONTRADA'}
            _, estado, id_medico, id_paciente, paciente, cedula = consulta
            if id_medico_actor is None or id_medico_actor != id_medico:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if estado not in ESTADOS_ABIERTOS:
                con.rollback()
                return {'error': 'CONSULTA_NO_ABIERTA', 'estado': estado}

            # el tipo y los síntomas se bloquean FOR SHARE (en orden, sin deadlocks): una baja concurrente espera a que este diagnóstico termine
            cur.execute("SELECT activo FROM tipo_diagnostico WHERE id_tipo_diagnostico = %s FOR SHARE", (datos['id_tipo_diagnostico'],))
            tipo = cur.fetchone()
            if not tipo:
                con.rollback()
                return {'error': 'TIPO_NO_EXISTE'}
            if not tipo[0]:
                con.rollback()
                return {'error': 'TIPO_INACTIVO'}
            ids = sorted(set(datos['sintomas']))
            cur.execute("SELECT id_sintoma, descripcion_sintoma, activo FROM sintoma WHERE id_sintoma = ANY(%s) ORDER BY id_sintoma FOR SHARE", (ids,))
            sintomas = cur.fetchall()
            if len(sintomas) != len(ids):
                con.rollback()
                return {'error': 'SINTOMA_NO_EXISTE'}
            inactivos = [s[1] for s in sintomas if not s[2]]
            if inactivos:
                con.rollback()
                return {'error': 'SINTOMA_INACTIVO', 'detalle': ', '.join(inactivos)}

            # código DX-0001: se calcula en la misma transacción que el INSERT (bloqueo asesor: sin duplicados)
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('diagnosticos_codigo'))")
            cur.execute(r"""SELECT COALESCE(MAX(CAST(SUBSTRING(codigo FROM 'DX-(\d+)') AS INTEGER)), 0) + 1
                            FROM diagnosticos WHERE codigo LIKE 'DX-%'""")
            codigo = f"DX-{str(cur.fetchone()[0]).zfill(4)}"
            cur.execute("""
                INSERT INTO diagnosticos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_diagnostico, descripcion_diagnostico,
                                         pieza_dental, fecha_diagnostico, observaciones, id_usuario_registro)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, %s, %s) RETURNING id_diagnostico""",
                        (codigo, datos['id_consulta_cab'], id_paciente, id_medico, datos['id_tipo_diagnostico'],
                         datos['descripcion_diagnostico'], str(datos['pieza_dental']) if datos.get('pieza_dental') else None,
                         datos.get('observaciones'), id_usuario))
            id_dx = cur.fetchone()[0]
            for i in ids:
                cur.execute("INSERT INTO diagnostico_sintoma (id_diagnostico, id_sintoma) VALUES (%s, %s)", (id_dx, i))
            con.commit()
            return {'id_diagnostico': id_dx, 'codigo': codigo, 'contexto': {'paciente': paciente, 'cedula': cedula}}
        except psycopg2.errors.CheckViolation as e:
            con.rollback()
            app.logger.error(f"Regla de la base violada al guardar el diagnóstico: {str(e)}")
            return {'error': 'DATOS_INVALIDOS'}
        except Exception as e:
            app.logger.error(f"Error al guardar diagnóstico: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anular
    def anularDiagnostico(self, id_diagnostico, id_medico_actor):
        """
        Anula (baja lógica, definitiva) el diagnóstico. Bloquea la consulta y después el diagnóstico (mismo orden que el alta), y rechaza si
        el actor no es el médico de la consulta, la consulta no está abierta o hay un tratamiento VIGENTE asociado.
        Devuelve {'ok', 'codigo', 'id_consulta_cab', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_consulta_cab FROM diagnosticos WHERE id_diagnostico = %s AND activo = true", (id_diagnostico,))
            fila = cur.fetchone()
            if not fila:
                con.rollback()
                return {'error': 'DIAGNOSTICO_NO_ENCONTRADO'}
            id_consulta = fila[0]
            cur.execute("""SELECT cc.estado, cc.id_medico, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad
                           FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente
                           WHERE cc.id_consulta_cab = %s FOR UPDATE OF cc""", (id_consulta,))
            estado, id_medico, paciente, cedula = cur.fetchone()
            cur.execute("SELECT codigo FROM diagnosticos WHERE id_diagnostico = %s AND activo = true FOR UPDATE", (id_diagnostico,))
            dx = cur.fetchone()
            if not dx:
                con.rollback()
                return {'error': 'DIAGNOSTICO_NO_ENCONTRADO'}
            if id_medico_actor is None or id_medico_actor != id_medico:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if estado not in ESTADOS_ABIERTOS:
                con.rollback()
                return {'error': 'CONSULTA_NO_ABIERTA', 'estado': estado}
            cur.execute("SELECT 1 FROM tratamientos WHERE id_diagnostico = %s AND estado <> 'cancelado' LIMIT 1", (id_diagnostico,))
            if cur.fetchone():
                con.rollback()
                return {'error': 'EN_USO'}
            cur.execute("UPDATE diagnosticos SET activo = false WHERE id_diagnostico = %s", (id_diagnostico,))
            con.commit()
            return {'ok': True, 'codigo': dx[0], 'id_consulta_cab': id_consulta, 'contexto': {'paciente': paciente, 'cedula': cedula}}
        except Exception as e:
            app.logger.error(f"Error al anular diagnóstico: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()
