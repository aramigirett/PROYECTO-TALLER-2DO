# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class MedicamentoDao(CatalogoDao):
    """
    Referencial `medicamentos` (Estándar de referenciales: borrado lógico, único parcial por nombre_comercial entre los activos,
    Estado / Reactivar). La baja se bloquea si lo usan: Renglones de recetas vigentes (anular una receta anula sus renglones).
    """
    TABLA = 'medicamentos'
    PK = 'id_medicamento'
    CLAVE = 'nombre_comercial'
    EXTRAS = ('presentacion',)
    NOMBRE = 'medicamento'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("SELECT 1 FROM receta_medicamento WHERE id_medicamento = %s AND activo = true LIMIT 1", (id_registro,))
        if cur.fetchone():
            return "No se puede dar de baja, el medicamento está en una o más recetas."
        return False
