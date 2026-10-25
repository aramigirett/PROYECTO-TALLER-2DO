# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class CiudadDao(CatalogoDao):
    """
    Referencial `ciudades` (Estándar de referenciales: borrado lógico, único parcial por descripción entre los activos, Estado /
    Reactivar). La baja se bloquea si la usa algún paciente o médico ACTIVO.
    """
    TABLA = 'ciudades'
    PK = 'id_ciudad'
    CLAVE = 'descripcion'
    FECHA = False
    NOMBRE = 'ciudad'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("SELECT COUNT(*) FROM paciente WHERE id_ciudad = %s AND activo = true", (id_registro,))
        pacientes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM medico WHERE id_ciudad = %s AND activo = true", (id_registro,))
        medicos = cur.fetchone()[0]
        if pacientes or medicos:
            partes = []
            if pacientes:
                partes.append(f"{pacientes} paciente(s)")
            if medicos:
                partes.append(f"{medicos} médico(s)")
            return "No se puede anular, la ciudad está asignada a " + " y ".join(partes) + "."
        return False
