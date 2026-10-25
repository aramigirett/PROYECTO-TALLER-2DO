# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class TipoInsumoDao(CatalogoDao):
    """
    Referencial `insumos` (Estándar de referenciales: borrado lógico, único parcial por descripcion entre los activos,
    Estado / Reactivar). La baja se bloquea si lo usan: Insumos de sesiones de tratamiento vigentes (anular una sesión anula sus insumos).
    """
    TABLA = 'insumos'
    PK = 'id_insumo'
    CLAVE = 'descripcion'
    EXTRAS = ('presentacion',)
    NOMBRE = 'tipo de insumo'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("SELECT 1 FROM sesion_insumos WHERE id_insumo = %s AND activo = true LIMIT 1", (id_registro,))
        if cur.fetchone():
            return "No se puede dar de baja, el insumo está registrado en sesiones de tratamiento."
        return False
