# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class CargoDao:

    def getCargos(self):
        cargoSQL = """
        SELECT id_cargo, descripcion
        FROM cargo
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(cargoSQL)
            cargos = cur.fetchall()  # Trae todos los cargos
            return [{'id_cargo': cargo[0], 'descripcion': cargo[1]} for cargo in cargos]

        except Exception as e:
            app.logger.error(f"Error al obtener todos los cargos: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getCargoById(self, id_cargo):
        cargoSQL = """
        SELECT id_cargo, descripcion
        FROM cargo
        WHERE id_cargo=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(cargoSQL, (id_cargo,))
            cargoEncontrado = cur.fetchone()
            if cargoEncontrado:
                return {
                    "id_cargo": cargoEncontrado[0],
                    "descripcion": cargoEncontrado[1]
                }
            else:
                return None

        except Exception as e:
            app.logger.error(f"Error al obtener cargo: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion):
        """
        Verifica si ya existe un cargo con la misma descripcion (ignorando mayúsculas/minúsculas)
        """
        sql = """
        SELECT 1 FROM cargo WHERE UPPER(descripcion) = UPPER(%s)
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion,))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de cargo: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarCargo(self, descripcion):
        insertCargoSQL = """
        INSERT INTO cargo(descripcion) VALUES(%s) RETURNING id_cargo
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(insertCargoSQL, (descripcion,))
            cargo_id = cur.fetchone()[0]
            con.commit()
            return cargo_id

        except Exception as e:
            app.logger.error(f"Error al insertar cargo: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def updateCargo(self, id_cargo, descripcion):
        updateCargoSQL = """
        UPDATE cargo
        SET descripcion=%s
        WHERE id_cargo=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(updateCargoSQL, (descripcion, id_cargo,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0

        except Exception as e:
            app.logger.error(f"Error al actualizar cargo: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteCargo(self, id_cargo):
        deleteCargoSQL = """
        DELETE FROM cargo
        WHERE id_cargo=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(deleteCargoSQL, (id_cargo,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0

        except Exception as e:
            app.logger.error(f"Error al eliminar cargo: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()