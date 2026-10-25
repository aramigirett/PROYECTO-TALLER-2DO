# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class EspecialidadDao(CatalogoDao):
    """
    Referencial `especialidades` (borrado lógico, único parcial por nombre entre las activas). La baja se bloquea si la tiene algún
    médico ACTIVO o una agenda vigente.
    """
    TABLA = 'especialidades'
    PK = 'id_especialidad'
    CLAVE = 'nombre_especialidad'
    FECHA = False
    NOMBRE = 'especialidad'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("SELECT COUNT(*) FROM medico WHERE id_especialidad = %s AND activo = true", (id_registro,))
        medicos = cur.fetchone()[0]
        if medicos:
            return f"No se puede anular, la especialidad está asignada a {medicos} médico(s)."
        cur.execute("SELECT COUNT(*) FROM agenda_cabecera WHERE id_especialidad = %s AND estado <> 'Inactivo'", (id_registro,))
        agendas = cur.fetchone()[0]
        if agendas:
            return f"No se puede anular, la especialidad está en {agendas} agenda(s) vigente(s)."
        return False
