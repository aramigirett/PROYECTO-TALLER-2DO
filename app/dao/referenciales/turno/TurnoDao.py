# Data Access Object - DAO
from app.dao.referenciales_consultorio.CatalogoDao import CatalogoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class TurnoDao(CatalogoDao):
    """
    Referencial `turnos` (borrado lógico, único parcial por descripción entre los activos, Estado / Reactivar). La baja se bloquea
    si lo usa una disponibilidad horaria vigente o un horario de agenda no cancelado.
    """
    TABLA = 'turnos'
    PK = 'id_turno'
    CLAVE = 'descripcion'
    FECHA = False
    NOMBRE = 'turno'

    def _motivo_en_uso(self, cur, id_registro):
        cur.execute("SELECT COUNT(*) FROM disponibilidad_horaria WHERE id_turno = %s AND activo = true", (id_registro,))
        disponibilidades = cur.fetchone()[0]
        if disponibilidades:
            return f"No se puede anular, el turno está en {disponibilidades} disponibilidad(es) horaria(s)."
        cur.execute("""SELECT COUNT(*) FROM agenda_detalle d JOIN agenda_cabecera c ON c.id_agenda_cabecera = d.id_agenda_cabecera
                       WHERE d.id_turno = %s AND d.estado_detalle <> 'Cancelado' AND c.estado <> 'Inactivo'""", (id_registro,))
        horarios = cur.fetchone()[0]
        if horarios:
            return f"No se puede anular, el turno está en {horarios} horario(s) de agenda vigente(s)."
        return False
