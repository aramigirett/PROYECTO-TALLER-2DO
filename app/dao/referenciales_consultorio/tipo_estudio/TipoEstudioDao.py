# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class TipoEstudioDao(CatalogoDao):
    """
    Referencial `tipo_estudio` (Estándar de referenciales: borrado lógico, único parcial por descripcion entre los activos,
    Estado / Reactivar). La baja se bloquea si lo usan: Órdenes de estudio no canceladas (cancelado = anulado).
    """
    TABLA = 'tipo_estudio'
    PK = 'id_tipo_estudio'
    CLAVE = 'descripcion'
    EXTRAS = ()
    NOMBRE = 'tipo de estudio'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("SELECT 1 FROM orden_estudios WHERE id_tipo_estudio = %s AND estado <> 'cancelado' LIMIT 1", (id_registro,))
        if cur.fetchone():
            return "No se puede dar de baja, el tipo de estudio está en una o más órdenes de estudio."
        return False
