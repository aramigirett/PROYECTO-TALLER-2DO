# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class TipoTratamientoDao(CatalogoDao):
    """
    Referencial `tipos_tratamiento` (Estándar de referenciales: borrado lógico, único parcial por descripcion entre los activos,
    Estado / Reactivar). La baja se bloquea si lo usan: Tratamientos no cancelados (los cancelados ya no lo usan: la baja es lógica y no rompe nada).
    """
    TABLA = 'tipos_tratamiento'
    PK = 'id_tipo_tratamiento'
    CLAVE = 'descripcion'
    EXTRAS = ('precio', 'iva')
    NOMBRE = 'tipo de tratamiento'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("SELECT 1 FROM tratamientos WHERE id_tipo_tratamiento = %s AND estado <> 'cancelado' LIMIT 1", (id_registro,))
        if cur.fetchone():
            return "No se puede dar de baja, el tipo de tratamiento está en uno o más tratamientos."
        return False
