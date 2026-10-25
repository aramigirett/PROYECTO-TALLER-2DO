# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class CargoDao(CatalogoDao):
    """
    Referencial `cargo` (borrado lógico, único parcial por descripción entre los activos). La baja se bloquea si lo tiene algún
    funcionario ACTIVO.
    """
    TABLA = 'cargo'
    PK = 'id_cargo'
    CLAVE = 'descripcion'
    FECHA = False
    NOMBRE = 'cargo'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("SELECT COUNT(*) FROM funcionario WHERE id_cargo = %s AND activo = true", (id_registro,))
        n = cur.fetchone()[0]
        if n:
            return f"No se puede anular, el cargo está asignado a {n} funcionario(s)."
        return False
