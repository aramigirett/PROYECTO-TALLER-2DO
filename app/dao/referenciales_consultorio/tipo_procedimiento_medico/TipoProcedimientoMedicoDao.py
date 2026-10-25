# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class TipoProcedimientoMedicoDao(CatalogoDao):
    """
    Referencial `tipo_procedimiento_medico` (Estándar de referenciales: borrado lógico, único parcial por descripcion entre los activos,
    Estado / Reactivar). La baja se bloquea si lo usan: Sesiones de tratamiento vigentes.
    """
    TABLA = 'tipo_procedimiento_medico'
    PK = 'id_tipo_procedimiento'
    CLAVE = 'descripcion'
    EXTRAS = ()
    NOMBRE = 'tipo de procedimiento médico'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("SELECT 1 FROM sesiones_tratamiento WHERE id_tipo_procedimiento = %s AND activo = true LIMIT 1", (id_registro,))
        if cur.fetchone():
            return "No se puede dar de baja, el tipo de procedimiento está registrado en sesiones de tratamiento."
        return False
