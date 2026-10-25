# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class SintomaDao(CatalogoDao):
    """
    Referencial `sintoma` (Estándar de referenciales: borrado lógico, único parcial por descripción entre los activos,
    Estado / Reactivar). La baja se bloquea si lo usa algún diagnóstico vigente (`diagnostico_sintoma`).
    """
    TABLA = 'sintoma'
    PK = 'id_sintoma'
    CLAVE = 'descripcion_sintoma'
    FECHA = False
    NOMBRE = 'síntoma'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("""SELECT 1 FROM diagnostico_sintoma ds JOIN diagnosticos d ON d.id_diagnostico = ds.id_diagnostico
                       WHERE ds.id_sintoma = %s AND d.activo = true LIMIT 1""", (id_registro,))
        if cur.fetchone():
            return "No se puede dar de baja, el síntoma está en uno o más diagnósticos."
        return False
