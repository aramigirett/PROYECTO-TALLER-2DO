"""
=====================================================
DAO: Orden de Estudios (Generar Orden de Estudios). Las reglas viven en OrdenBaseDao (idéntico a la Orden de Análisis; solo cambia el catálogo).
=====================================================
"""
from app.dao.referenciales_consultorio.documento_clinico import PREFIJO_ORDEN_ESTUDIO
from app.dao.referenciales_consultorio.orden_base import OrdenBaseDao


class OrdenEstudioDao(OrdenBaseDao):
    TABLA = 'orden_estudios'
    PK = 'id_orden_estudio'
    TIPO_TABLA = 'tipo_estudio'
    TIPO_PK = 'id_tipo_estudio'
    TIPO_COL = 'id_tipo_estudio'
    PREFIJO = PREFIJO_ORDEN_ESTUDIO
