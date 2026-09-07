"""
=====================================================
DAO: Tratamiento (Gestionar Tratamientos)
Descripción: Cabecera de tratamiento clínico, parte de una Consulta activa.
=====================================================

NOTA - columnas fantasma de `tratamientos` (sin tocar a propósito, documentadas):
- `id_funcionario`: sin FK real hacia funcionario(id_funcionario). No es parte
  de los campos que pide el CUS de este movimiento; no se sabe todavía qué
  movimiento futuro la va a necesitar. Cuando se defina, agregar la FK con
  el mismo criterio usado en el resto del proyecto (RESTRICT).
- `codigo`: varchar(10) UNIQUE, nullable. No se usa ni se popula acá.

NOTA - `estaEnUso()` todavía no existe: la validación real de si un
tratamiento tiene sesiones/procedimientos asociados depende de
`sesion_insumos` (tabla de "Gestionar Procedimientos e Insumos Utilizados"),
que no existe en la base todavía. Cuando se programe ese movimiento, agregar
esa validación antes de permitir ANULAR, igual que se hizo en las
referenciales (TipoInsumoDao, TipoProcedimientoMedicoDao, etc.).
"""
from flask import current_app as app
from app.conexion.Conexion import Conexion

class TratamientoDao:

    def getTratamientos(self):
        """
        Obtiene todos los tratamientos, ocultando por defecto los anulados
        (estado='cancelado'), mismo criterio que Cita/Agenda/Odontograma.
        """
        sql = """
        SELECT
            t.id_tratamiento,
            t.id_consulta_cab,
            t.id_diagnostico,
            t.id_paciente,
            (p.nombre || ' ' || p.apellido) AS nombre_paciente,
            t.id_medico,
            (m.nombre || ' ' || m.apellido) AS nombre_medico,
            t.id_consultorio,
            co.nombre_consultorio,
            t.id_tipo_tratamiento,
            tt.descripcion AS tipo_tratamiento,
            t.descripcion_tratamiento,
            t.fecha_tratamiento,
            t.estado,
            t.fecha_registro
        FROM tratamientos t
        JOIN paciente p ON t.id_paciente = p.id_paciente
        JOIN medico m ON t.id_medico = m.id_medico
        LEFT JOIN consultorio co ON t.id_consultorio = co.codigo
        JOIN tipos_tratamiento tt ON t.id_tipo_tratamiento = tt.id_tipo_tratamiento
        WHERE t.estado <> 'cancelado'
        ORDER BY t.fecha_tratamiento DESC, t.id_tratamiento DESC
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            return [
                {
                    'id_tratamiento': r[0],
                    'id_consulta_cab': r[1],
                    'id_diagnostico': r[2],
                    'id_paciente': r[3],
                    'nombre_paciente': r[4],
                    'id_medico': r[5],
                    'nombre_medico': r[6],
                    'id_consultorio': r[7],
                    'nombre_consultorio': r[8],
                    'id_tipo_tratamiento': r[9],
                    'tipo_tratamiento': r[10],
                    'descripcion_tratamiento': r[11],
                    'fecha_tratamiento': str(r[12]) if r[12] else None,
                    'estado': r[13],
                    'fecha_registro': str(r[14]) if r[14] else None
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener tratamientos: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getTratamientoById(self, id_tratamiento):
        """Obtiene un tratamiento específico por ID (sin filtrar por estado)."""
        sql = """
        SELECT
            t.id_tratamiento,
            t.id_consulta_cab,
            t.id_diagnostico,
            t.id_paciente,
            (p.nombre || ' ' || p.apellido) AS nombre_paciente,
            t.id_medico,
            (m.nombre || ' ' || m.apellido) AS nombre_medico,
            t.id_consultorio,
            co.nombre_consultorio,
            t.id_tipo_tratamiento,
            tt.descripcion AS tipo_tratamiento,
            t.descripcion_tratamiento,
            t.fecha_tratamiento,
            t.estado,
            t.fecha_registro
        FROM tratamientos t
        JOIN paciente p ON t.id_paciente = p.id_paciente
        JOIN medico m ON t.id_medico = m.id_medico
        LEFT JOIN consultorio co ON t.id_consultorio = co.codigo
        JOIN tipos_tratamiento tt ON t.id_tipo_tratamiento = tt.id_tipo_tratamiento
        WHERE t.id_tratamiento = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tratamiento,))
            r = cur.fetchone()
            if r:
                return {
                    'id_tratamiento': r[0],
                    'id_consulta_cab': r[1],
                    'id_diagnostico': r[2],
                    'id_paciente': r[3],
                    'nombre_paciente': r[4],
                    'id_medico': r[5],
                    'nombre_medico': r[6],
                    'id_consultorio': r[7],
                    'nombre_consultorio': r[8],
                    'id_tipo_tratamiento': r[9],
                    'tipo_tratamiento': r[10],
                    'descripcion_tratamiento': r[11],
                    'fecha_tratamiento': str(r[12]) if r[12] else None,
                    'estado': r[13],
                    'fecha_registro': str(r[14]) if r[14] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener tratamiento: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarTratamiento(self, datos):
        """
        Registra un nuevo tratamiento a partir de una Consulta activa
        (activo=true y estado en 'programada'/'en_proceso').

        Paciente, Médico y Consultorio NO se toman del formulario: se
        derivan siempre de la consulta, igual que ConsultaDao.guardarConsulta
        con Paciente/Médico/Consultorio respecto de la Cita.

        Si viene id_diagnostico, se valida que pertenezca a esa misma
        consulta (vía consultas_detalle) antes de aceptarlo.

        Retorna un dict:
          {'id_tratamiento': N}  en éxito
          {'error': 'CONSULTA_NO_ENCONTRADA' | 'CONSULTA_NO_ACTIVA' |
                     'DIAGNOSTICO_INVALIDO' | 'ERROR_INTERNO'}
        """
        id_consulta_cab = datos.get('id_consulta_cab')
        id_diagnostico = datos.get('id_diagnostico')

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("""
                SELECT id_paciente, id_medico, id_consultorio, estado, activo
                FROM consultas_cab
                WHERE id_consulta_cab = %s
            """, (id_consulta_cab,))
            consulta = cur.fetchone()

            if not consulta:
                return {'error': 'CONSULTA_NO_ENCONTRADA'}

            id_paciente, id_medico, id_consultorio, estado_consulta, activo_consulta = consulta

            if not activo_consulta or estado_consulta not in ('programada', 'en_proceso'):
                return {'error': 'CONSULTA_NO_ACTIVA'}

            if id_diagnostico:
                cur.execute("""
                    SELECT 1
                    FROM diagnosticos d
                    JOIN consultas_detalle cd ON d.id_consulta_detalle = cd.id_consulta_detalle
                    WHERE d.id_diagnostico = %s AND cd.id_consulta_cab = %s
                """, (id_diagnostico, id_consulta_cab))
                if not cur.fetchone():
                    return {'error': 'DIAGNOSTICO_INVALIDO'}

            cur.execute("""
                INSERT INTO tratamientos(
                    id_consulta_cab, id_diagnostico, id_paciente, id_medico,
                    id_consultorio, id_tipo_tratamiento, descripcion_tratamiento,
                    fecha_tratamiento, estado
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendiente')
                RETURNING id_tratamiento
            """, (
                id_consulta_cab, id_diagnostico, id_paciente, id_medico,
                id_consultorio, datos.get('id_tipo_tratamiento'),
                datos.get('descripcion_tratamiento'), datos.get('fecha_tratamiento')
            ))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return {'id_tratamiento': nuevo_id}

        except Exception as e:
            app.logger.error(f"Error al guardar tratamiento: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}

        finally:
            cur.close()
            con.close()

    def deleteTratamiento(self, id_tratamiento):
        """
        Anula (baja lógica) un tratamiento: pasa su estado a 'cancelado'.

        Returns:
            bool: True si se anuló, False si no existía o ya estaba cancelado.
        """
        sql = """
        UPDATE tratamientos
        SET estado = 'cancelado'
        WHERE id_tratamiento = %s AND estado <> 'cancelado'
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tratamiento,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al anular tratamiento: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
