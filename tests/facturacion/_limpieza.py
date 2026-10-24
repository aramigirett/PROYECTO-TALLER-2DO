"""Limpieza de auditoría para los tests.

auditoria_cambios y auditoria_acceso son inmutables (trigger trg_auditoria_inmutable): la aplicación nunca las
modifica ni las borra. Los tests, en cambio, borran SOLO los registros de auditoría que ellos mismos generaron (por
entidad e ID). Para eso saltan el trigger únicamente en SU conexión con SET session_replication_role = replica, que
exige superusuario (los tests corren como postgres) y se revierte solo al cerrar la conexión.

Se importa con: from tests.facturacion._limpieza import borrar_auditoria
"""


def borrar_auditoria(cur, entidad, ids):
    """Borra de auditoria_cambios los registros de `entidad` con id_registro en `ids`. Devuelve cuántos borró."""
    ids = list(ids)
    if not ids:
        return 0
    cur.execute("SET session_replication_role = replica")
    try:
        cur.execute("DELETE FROM auditoria_cambios WHERE entidad = %s AND id_registro = ANY(%s)", (entidad, ids))
        return cur.rowcount
    finally:
        cur.execute("RESET session_replication_role")
