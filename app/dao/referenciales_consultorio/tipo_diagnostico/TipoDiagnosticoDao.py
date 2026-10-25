# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class TipoDiagnosticoDao(CatalogoDao):
    """
    Referencial `tipo_diagnostico` (Estándar de referenciales: borrado lógico, único parcial por descripción entre los activos,
    Estado / Reactivar). Lleva además el tipo (categoría) del diagnóstico. La baja se bloquea si lo usan diagnósticos vigentes
    o tratamientos no cancelados.
    """
    TABLA = 'tipo_diagnostico'
    PK = 'id_tipo_diagnostico'
    CLAVE = 'descripcion_diagnostico'
    EXTRAS = ('tipo_diagnostico',)
    FECHA = False
    NOMBRE = 'tipo de diagnóstico'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("SELECT 1 FROM diagnosticos WHERE id_tipo_diagnostico = %s AND activo = true LIMIT 1", (id_registro,))
        if cur.fetchone():
            return "No se puede dar de baja, el tipo de diagnóstico está en uno o más diagnósticos."
        cur.execute("SELECT 1 FROM tratamientos WHERE id_tipo_diagnostico = %s AND estado <> 'cancelado' LIMIT 1", (id_registro,))
        if cur.fetchone():
            return "No se puede dar de baja, el tipo de diagnóstico está en uno o más tratamientos."
        return False
