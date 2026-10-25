# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class ConsultorioDao(CatalogoDao):
    """
    Referencial `consultorio` (PK `codigo`: borrado lógico, único parcial por nombre y por correo entre los activos, Estado /
    Reactivar). La baja se bloquea si tiene cajas activas, agendas vigentes, avisos vigentes, consultas o tratamientos en curso.
    Caja toma FOR SHARE sobre la fila al guardar (CajaDao._consultorio_existe).
    """
    TABLA = 'consultorio'
    PK = 'codigo'
    CLAVE = 'nombre_consultorio'
    EXTRAS = ('direccion', 'telefono', 'correo')
    FECHA = False
    NOMBRE = 'consultorio'

    def duplicado(self, valores, excluir_id=None):
        """'nombre' o 'correo' si ya hay un consultorio ACTIVO con ese valor (sin distinguir mayúsculas); si no, None."""
        if self.existeDuplicado(valores['nombre_consultorio'], excluir_id):
            return 'nombre'
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            sql = "SELECT 1 FROM consultorio WHERE activo = true AND LOWER(correo) = LOWER(%s)"
            params = [valores['correo']]
            if excluir_id:
                sql += " AND codigo != %s"
                params.append(excluir_id)
            cur.execute(sql, params)
            return 'correo' if cur.fetchone() else None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de consultorio: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def _motivo_en_uso(self, cur, id_registro):
        usos = (
            ("SELECT COUNT(*) FROM caja WHERE id_consultorio = %s AND activo = true", "caja(s) activa(s)"),
            ("SELECT COUNT(*) FROM agenda_cabecera WHERE id_consultorio = %s AND estado <> 'Inactivo'", "agenda(s) vigente(s)"),
            ("SELECT COUNT(*) FROM avisos_recordatorios WHERE codigo = %s AND estado <> 'Inactivo'", "aviso(s) vigente(s)"),
            ("SELECT COUNT(*) FROM consultas_cab WHERE id_consultorio = %s AND activo = true", "consulta(s)"),
            ("SELECT COUNT(*) FROM tratamientos WHERE id_consultorio = %s AND estado <> 'cancelado'", "tratamiento(s)"),
        )
        for sql, texto in usos:
            cur.execute(sql, (id_registro,))
            n = cur.fetchone()[0]
            if n:
                return f"No se puede anular, el consultorio tiene {n} {texto}."
        return False
