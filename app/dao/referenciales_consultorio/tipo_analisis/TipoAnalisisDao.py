# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class TipoAnalisisDao(CatalogoDao):
    """
    Referencial `tipo_analisis` (Estándar de referenciales: borrado lógico, único parcial por descripcion entre los activos,
    Estado / Reactivar). La baja se bloquea si lo usan: Órdenes de análisis no canceladas (cancelado = anulado).
    """
    TABLA = 'tipo_analisis'
    PK = 'id_tipo_analisis'
    CLAVE = 'descripcion'
    EXTRAS = ()
    NOMBRE = 'tipo de análisis'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("SELECT 1 FROM orden_analisis WHERE id_tipo_analisis = %s AND estado <> 'cancelado' LIMIT 1", (id_registro,))
        if cur.fetchone():
            return "No se puede dar de baja, el tipo de análisis está en una o más órdenes de análisis."
        return False
