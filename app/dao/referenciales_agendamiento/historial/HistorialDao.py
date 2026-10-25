# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

INVALIDO = "INVALIDO"

_COLUMNAS = """h.id_historial, h.id_paciente, (p.nombre || ' ' || p.apellido) AS nombre_paciente, h.tipo_documento, h.descripcion, h.tipo_alergia,
       h.gravedad_alergia, h.nombre_medicamento, h.dosis_medicamento, h.frecuencia_medicamento, h.fecha_inicio_medicamento, h.archivo_url,
       h.archivo_nombre, h.archivo_tipo, h.archivo_tamano, h.fecha_registro, h.estado"""
_FROM = "FROM historial_medico_paciente h JOIN paciente p ON p.id_paciente = h.id_paciente"


def _fila(h, con_ruta=False):
    d = {'id_historial': h[0], 'id_paciente': h[1], 'nombre_paciente': h[2], 'tipo_documento': h[3], 'descripcion': h[4], 'tipo_alergia': h[5],
         'gravedad_alergia': h[6], 'nombre_medicamento': h[7], 'dosis_medicamento': h[8], 'frecuencia_medicamento': h[9],
         'fecha_inicio_medicamento': h[10].isoformat() if h[10] else None, 'tiene_archivo': bool(h[11]), 'archivo_nombre': h[12],
         'archivo_tipo': h[13], 'archivo_tamano': h[14], 'fecha_registro': h[15].isoformat() if h[15] else None, 'estado': h[16]}
    if con_ruta:
        d['archivo_ruta'] = h[11]   # solo uso interno (la descarga): nunca se manda a la pantalla
    return d


class HistorialMedicoDao:
    """
    Documentos del historial médico de un paciente (antecedentes, alergias, medicamentos habituales, estudios). Se registra y se anula (baja lógica
    por `estado`, definitiva: no se reactiva); no se modifica. El acceso por rol lo decide la API (el médico, solo a los pacientes que atendió).
    Al guardar toma FOR SHARE sobre el paciente y lo rechaza si está anulado.
    """

    def getHistorialByPaciente(self, id_paciente, tipo_documento=None):
        sql = f"SELECT {_COLUMNAS} {_FROM} WHERE h.id_paciente = %s AND h.estado = 'activo'"
        params = [id_paciente]
        if tipo_documento:
            sql += " AND h.tipo_documento = %s"; params.append(tipo_documento)
        sql += " ORDER BY h.fecha_registro DESC, h.id_historial DESC"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            return [_fila(h) for h in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener historial del paciente: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getHistorialById(self, id_historial, con_ruta=False, incluir_inactivos=False):
        sql = f"SELECT {_COLUMNAS} {_FROM} WHERE h.id_historial = %s" + ("" if incluir_inactivos else " AND h.estado = 'activo'")
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_historial,))
            h = cur.fetchone()
            return _fila(h, con_ruta) if h else None
        except Exception as e:
            app.logger.error(f"Error al obtener historial por ID: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarHistorial(self, datos, id_usuario):
        """Returns: ID nuevo; ("INVALIDO", campo, mensaje) si el paciente no existe o está anulado; None ante otro error."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT activo FROM paciente WHERE id_paciente = %s FOR SHARE", (datos['id_paciente'],))
            f = cur.fetchone()
            if f is None or not f[0]:
                con.rollback()
                return (INVALIDO, 'id_paciente', 'El paciente seleccionado no existe o está anulado.')
            cur.execute("""
                INSERT INTO historial_medico_paciente(id_paciente, tipo_documento, descripcion, tipo_alergia, gravedad_alergia, nombre_medicamento,
                    dosis_medicamento, frecuencia_medicamento, fecha_inicio_medicamento, archivo_url, archivo_nombre, archivo_tipo, archivo_tamano, id_usuario_registro)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id_historial""",
                (datos['id_paciente'], datos['tipo_documento'], datos['descripcion'], datos.get('tipo_alergia'), datos.get('gravedad_alergia'),
                 datos.get('nombre_medicamento'), datos.get('dosis_medicamento'), datos.get('frecuencia_medicamento'), datos.get('fecha_inicio_medicamento'),
                 datos.get('archivo_url'), datos.get('archivo_nombre'), datos.get('archivo_tipo'), datos.get('archivo_tamano'), id_usuario))
            nuevo = cur.fetchone()[0]
            con.commit()
            return nuevo
        except Exception as e:
            app.logger.error(f"Error al guardar historial: {str(e)}")
            con.rollback()
            return None
        finally:
            cur.close()
            con.close()

    def deleteHistorial(self, id_historial, id_usuario):
        """Anula (baja lógica definitiva) un documento. Returns: bool."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""UPDATE historial_medico_paciente SET estado = 'inactivo', fecha_modificacion = NOW(), id_usuario_modificacion = %s
                           WHERE id_historial = %s AND estado = 'activo'""", (id_usuario, id_historial))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al anular historial: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def contarDocumentosPorTipo(self, id_paciente):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT tipo_documento, COUNT(*) FROM historial_medico_paciente WHERE id_paciente = %s AND estado = 'activo' GROUP BY tipo_documento", (id_paciente,))
            return {c[0]: c[1] for c in cur.fetchall()}
        except Exception as e:
            app.logger.error(f"Error al contar documentos: {str(e)}")
            return {}
        finally:
            cur.close()
            con.close()

    # ---- acceso por rol ----
    def pacientesAtendidos(self, id_medico=None):
        """
        Pacientes ACTIVOS para elegir en la pantalla: con id_medico, solo los que ese médico atendió (tiene una consulta no cancelada con él);
        sin id_medico (Administrador, que solo lee), todos. Trae la cantidad de documentos vigentes.
        """
        sql = """SELECT p.id_paciente, p.nombre, p.apellido, p.cedula_entidad,
                        (SELECT COUNT(*) FROM historial_medico_paciente h WHERE h.id_paciente = p.id_paciente AND h.estado = 'activo')
                 FROM paciente p WHERE p.activo = true"""
        params = []
        if id_medico:
            sql += """ AND EXISTS (SELECT 1 FROM consultas_cab c WHERE c.id_paciente = p.id_paciente AND c.id_medico = %s AND c.activo = true AND c.estado <> 'cancelada')"""
            params.append(id_medico)
        sql += " ORDER BY p.apellido, p.nombre, p.id_paciente"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            return [{'id_paciente': r[0], 'nombre': r[1], 'apellido': r[2], 'cedula_entidad': r[3], 'documentos': r[4]} for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener los pacientes del historial: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def esPacienteAtendido(self, id_medico, id_paciente):
        """True si el médico tiene una consulta no cancelada con ese paciente (puede ver y registrar su historial)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM consultas_cab WHERE id_paciente = %s AND id_medico = %s AND activo = true AND estado <> 'cancelada' LIMIT 1", (id_paciente, id_medico))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar el paciente atendido: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()
