"""
=====================================================
DAO: Ficha Médica de Consulta
Descripción: ficha_medica_consulta (signos vitales y examen físico). UNA ficha activa por consulta.

Reglas (todas se revalidan DENTRO de la transacción, con la consulta bloqueada FOR UPDATE):
  - la consulta existe, está activa y en 'programada' o 'en_proceso' (si pasó a 'cancelada' o 'finalizada' mientras se cargaba, 409);
  - crear, editar y anular solo lo hace el médico de esa consulta (el Administrador y Recepción solo leen);
  - una sola ficha activa por consulta; no se guardan fichas vacías (los valores ya vienen validados por validadores_clinicos).
Dato de salud: ningún método de la auditoría recibe estos valores.
=====================================================
"""
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta

COLUMNAS = ('presion_arterial', 'temperatura', 'frecuencia_cardiaca', 'frecuencia_respiratoria', 'peso', 'talla', 'imc',
            'examen_fisico_general', 'examen_bucal', 'observaciones_medico')
ESTADOS_ABIERTOS = ('programada', 'en_proceso')


def _num(v):
    return float(v) if v is not None else None


def _ficha(f):
    return {
        'id_ficha_medica': f[0], 'id_consulta_cab': f[1], 'presion_arterial': f[2], 'temperatura': _num(f[3]),
        'frecuencia_cardiaca': f[4], 'frecuencia_respiratoria': f[5], 'peso': _num(f[6]), 'talla': _num(f[7]), 'imc': _num(f[8]),
        'examen_fisico_general': f[9], 'examen_bucal': f[10], 'observaciones_medico': f[11],
        'fecha_registro': f[12].isoformat() if f[12] else None,
    }


SELECT_FICHA = """
    SELECT fm.id_ficha_medica, fm.id_consulta_cab, fm.presion_arterial, fm.temperatura, fm.frecuencia_cardiaca,
           fm.frecuencia_respiratoria, fm.peso, fm.talla, fm.imc, fm.examen_fisico_general, fm.examen_bucal,
           fm.observaciones_medico, fm.fecha_registro
    FROM ficha_medica_consulta fm"""


class FichaMedicaDao:

    # ------------------------------------------------------------------ lectura
    def getFichaByConsulta(self, id_consulta_cab):
        """La ficha ACTIVA de una consulta (solo puede haber una)."""
        return self._uno(SELECT_FICHA + " WHERE fm.id_consulta_cab = %s AND fm.activo = true", (id_consulta_cab,))

    def getFichaById(self, id_ficha_medica):
        return self._uno(SELECT_FICHA + " WHERE fm.id_ficha_medica = %s AND fm.activo = true", (id_ficha_medica,))

    def _uno(self, sql, params):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            f = cur.fetchone()
            return _ficha(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener la ficha médica: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def listar(self, texto=None, desde=None, hasta=None, id_medico=None, pagina=1, por_pagina=25):
        """
        Listado de fichas ACTIVAS para la pantalla de Fichas Médicas: identifica la ficha (consulta, paciente, médico, fecha) y dice cuántos
        datos tiene cargados. NO trae ningún valor clínico: el detalle se pide por ID. Devuelve (filas, total).
        """
        where, params = ["fm.activo = true", "cc.activo = true"], []
        if texto:
            where.append("(CONCAT(p.nombre, ' ', p.apellido) ILIKE %s OR p.cedula_entidad ILIKE %s)")
            params += [f'%{texto}%', f'%{texto}%']
        if desde:
            where.append("cc.fecha_cita >= %s"); params.append(desde)
        if hasta:
            where.append("cc.fecha_cita <= %s"); params.append(hasta)
        if id_medico:
            where.append("cc.id_medico = %s"); params.append(id_medico)
        cond = ' AND '.join(where)
        por_pagina = max(1, min(int(por_pagina), 100))
        pagina = max(1, int(pagina))
        join = """FROM ficha_medica_consulta fm
                  JOIN consultas_cab cc ON fm.id_consulta_cab = cc.id_consulta_cab
                  JOIN paciente p ON cc.id_paciente = p.id_paciente
                  JOIN medico m ON cc.id_medico = m.id_medico"""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT COUNT(*) {join} WHERE {cond}", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(f"""
                SELECT fm.id_ficha_medica, fm.id_consulta_cab, cc.fecha_cita, cc.estado, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad,
                       cc.id_medico, CONCAT(m.nombre, ' ', m.apellido), fm.fecha_registro,
                       num_nonnulls(fm.presion_arterial, fm.temperatura, fm.frecuencia_cardiaca, fm.frecuencia_respiratoria, fm.peso, fm.talla,
                                    fm.examen_fisico_general, fm.examen_bucal, fm.observaciones_medico)
                {join} WHERE {cond}
                ORDER BY cc.fecha_cita DESC, fm.fecha_registro DESC, fm.id_ficha_medica DESC LIMIT %s OFFSET %s""",
                        tuple(params) + (por_pagina, (pagina - 1) * por_pagina))
            return [{
                'id_ficha_medica': f[0], 'id_consulta_cab': f[1], 'numero_consulta': numero_consulta(f[1]),
                'fecha_consulta': f[2].isoformat() if f[2] else None, 'estado_consulta': f[3],
                'nombre_paciente': f[4], 'cedula_paciente': f[5], 'id_medico': f[6], 'nombre_medico': f[7],
                'fecha_registro': f[8].isoformat() if f[8] else None, 'datos_cargados': f[9],
            } for f in cur.fetchall()], total
        except Exception as e:
            app.logger.error(f"Error al listar fichas médicas: {str(e)}")
            return [], 0
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ escritura
    def _consulta_bloqueada(self, cur, id_consulta_cab, id_medico_actor):
        """
        Bloquea la consulta y revalida las reglas comunes. Devuelve (info, None) o (None, {'error': CÓDIGO, ...}).
        info = {'estado', 'id_medico', 'paciente', 'cedula'}.
        """
        cur.execute("""SELECT cc.activo, cc.estado, cc.id_medico, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad
                       FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente
                       WHERE cc.id_consulta_cab = %s FOR UPDATE OF cc""", (id_consulta_cab,))
        fila = cur.fetchone()
        if not fila or not fila[0]:
            return None, {'error': 'CONSULTA_NO_ENCONTRADA'}
        _, estado, id_medico, paciente, cedula = fila
        if id_medico_actor is None or id_medico_actor != id_medico:
            return None, {'error': 'NO_ES_SU_MEDICO'}
        if estado not in ESTADOS_ABIERTOS:
            return None, {'error': 'CONSULTA_NO_ABIERTA', 'estado': estado}
        return {'estado': estado, 'id_medico': id_medico, 'paciente': paciente, 'cedula': cedula}, None

    def guardarFicha(self, id_consulta_cab, valores, id_medico_actor):
        """Crea la ficha. Devuelve {'id_ficha_medica', 'contexto'} o {'error': CÓDIGO}."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            info, err = self._consulta_bloqueada(cur, id_consulta_cab, id_medico_actor)
            if err:
                con.rollback()
                return err
            cur.execute("SELECT 1 FROM ficha_medica_consulta WHERE id_consulta_cab = %s AND activo = true", (id_consulta_cab,))
            if cur.fetchone():
                con.rollback()
                return {'error': 'FICHA_YA_EXISTE'}
            cur.execute(f"""INSERT INTO ficha_medica_consulta(id_consulta_cab, {', '.join(COLUMNAS)})
                            VALUES (%s, {', '.join(['%s'] * len(COLUMNAS))}) RETURNING id_ficha_medica""",
                        (id_consulta_cab, *[valores.get(c) for c in COLUMNAS]))
            id_ficha = cur.fetchone()[0]
            con.commit()
            return {'id_ficha_medica': id_ficha, 'contexto': info}
        except psycopg2.errors.UniqueViolation:
            con.rollback()   # dos altas simultáneas: gana una
            return {'error': 'FICHA_YA_EXISTE'}
        except Exception as e:
            app.logger.error(f"Error al guardar la ficha médica: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    def _ficha_de_consulta(self, cur, id_ficha_medica):
        cur.execute("SELECT id_consulta_cab FROM ficha_medica_consulta WHERE id_ficha_medica = %s AND activo = true", (id_ficha_medica,))
        r = cur.fetchone()
        return r[0] if r else None

    def updateFicha(self, id_ficha_medica, valores, id_medico_actor):
        """
        Edita la ficha (excepción del CUS: corrige la misma ficha mientras la consulta sigue abierta). Si no cambia nada devuelve
        {'sin_cambios': True} sin tocar la base. Devuelve {'ok': True, 'id_consulta_cab', 'contexto'} o {'error': CÓDIGO}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            id_consulta = self._ficha_de_consulta(cur, id_ficha_medica)
            if id_consulta is None:
                con.rollback()
                return {'error': 'FICHA_NO_ENCONTRADA'}
            info, err = self._consulta_bloqueada(cur, id_consulta, id_medico_actor)
            if err:
                con.rollback()
                return err
            cur.execute(f"SELECT {', '.join(COLUMNAS)} FROM ficha_medica_consulta WHERE id_ficha_medica = %s AND activo = true FOR UPDATE",
                        (id_ficha_medica,))
            actual = cur.fetchone()
            if actual is None:   # la anularon mientras tanto
                con.rollback()
                return {'error': 'FICHA_NO_ENCONTRADA'}
            nuevos = [valores.get(c) for c in COLUMNAS]
            if all(_igual(a, n) for a, n in zip(actual, nuevos)):
                con.rollback()
                return {'sin_cambios': True, 'id_consulta_cab': id_consulta, 'contexto': info}
            cur.execute(f"UPDATE ficha_medica_consulta SET {', '.join(c + ' = %s' for c in COLUMNAS)} WHERE id_ficha_medica = %s",
                        (*nuevos, id_ficha_medica))
            con.commit()
            return {'ok': True, 'id_consulta_cab': id_consulta, 'contexto': info}
        except Exception as e:
            app.logger.error(f"Error al actualizar la ficha médica: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    def deleteFicha(self, id_ficha_medica, id_medico_actor):
        """Anula (baja lógica) la ficha. Devuelve {'ok': True, 'id_consulta_cab', 'contexto'} o {'error': CÓDIGO}."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            id_consulta = self._ficha_de_consulta(cur, id_ficha_medica)
            if id_consulta is None:
                con.rollback()
                return {'error': 'FICHA_NO_ENCONTRADA'}
            info, err = self._consulta_bloqueada(cur, id_consulta, id_medico_actor)
            if err:
                con.rollback()
                return err
            cur.execute("UPDATE ficha_medica_consulta SET activo = false WHERE id_ficha_medica = %s AND activo = true", (id_ficha_medica,))
            if cur.rowcount == 0:
                con.rollback()
                return {'error': 'FICHA_NO_ENCONTRADA'}
            con.commit()
            return {'ok': True, 'id_consulta_cab': id_consulta, 'contexto': info}
        except Exception as e:
            app.logger.error(f"Error al anular la ficha médica: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()


def _igual(a, b):
    """Compara el valor guardado (Decimal/int/str/None) con el nuevo ignorando el tipo numérico."""
    if a is None or b is None:
        return a is None and b is None
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)
