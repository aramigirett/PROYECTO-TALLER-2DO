from flask import current_app as app
from app.conexion.Conexion import Conexion

class HistoriaClinicaDao:

    def getHistoriasClinicas(self):
        historiaclinicaSQL = """
        SELECT id, Motivo_Consulta, Antecedentes_Medicos, Antecedentes_Psicologicos, Historia_Familiar 
        FROM Historia_Clinica
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(historiaclinicaSQL)
            historiasclinicas = cur.fetchall()

            # Transformar los datos en una lista de diccionarios con todas las columnas correctas
            return [{'id': hc[0], 
                     'motivo_consulta': hc[1], 
                     'antecedentes_medicos': hc[2],
                     'antecedentes_psicologicos': hc[3],
                     'historia_familiar': hc[4]} 
                    for hc in historiasclinicas]

        except Exception as e:
            app.logger.error(f"Error al obtener todas las historias clinicas: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getHistoriaClinicaById(self, id):
        historiaclinicaSQL = """
        SELECT id, Motivo_Consulta, Antecedentes_Medicos, Antecedentes_Psicologicos, Historia_Familiar 
        FROM Historia_Clinica 
        WHERE id=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(historiaclinicaSQL, (id,))
            hc = cur.fetchone()

            if hc:
                return {
                    "id": hc[0],
                    "motivo_consulta": hc[1],
                    "antecedentes_medicos": hc[2],
                    "antecedentes_psicologicos": hc[3],
                    "historia_familiar": hc[4]
                }
            else:
                return None
        except Exception as e:
            app.logger.error(f"Error al obtener la historia clinica: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarHistoriaClinica(self, motivo_consulta, antecedentes_medicos, antecedentes_psicologicos, historia_familiar):
        insertHistoriaClinicaSQL = """
        INSERT INTO Historia_Clinica (Motivo_Consulta, Antecedentes_Medicos, Antecedentes_Psicologicos, Historia_Familiar) 
        VALUES (%s, %s, %s, %s) RETURNING id
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(insertHistoriaClinicaSQL, (motivo_consulta, antecedentes_medicos, antecedentes_psicologicos, historia_familiar))
            historiaclinica_id = cur.fetchone()[0]
            con.commit()
            return historiaclinica_id

        except Exception as e:
            app.logger.error(f"Error al insertar historia clinica: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def updateHistoriaClinica(self, id, motivo_consulta, antecedentes_medicos, antecedentes_psicologicos, historia_familiar):
        updateHistoriaClinicaSQL = """
        UPDATE Historia_Clinica
        SET Motivo_Consulta=%s, Antecedentes_Medicos=%s, Antecedentes_Psicologicos=%s, Historia_Familiar=%s
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateHistoriaClinicaSQL, (motivo_consulta, antecedentes_medicos, antecedentes_psicologicos, historia_familiar, id))
            filas_afectadas = cur.rowcount
            con.commit()

            return filas_afectadas > 0  # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar Historia Clinica: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteHistoriaClinica(self, id):
        deleteHistoriaClinicaSQL = """
        DELETE FROM Historia_Clinica
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(deleteHistoriaClinicaSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar Historia Clinica: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()