"""
=====================================================
DAO: Orden de Análisis (Generar Orden de Análisis). Las reglas viven en OrdenBaseDao (idéntico a la Orden de Estudios; solo cambia el catálogo).
=====================================================
"""
from app.dao.referenciales_consultorio.documento_clinico import PREFIJO_ORDEN_ANALISIS
from app.dao.referenciales_consultorio.orden_base import OrdenBaseDao


class OrdenAnalisisDao(OrdenBaseDao):
    TABLA = 'orden_analisis'
    PK = 'id_orden_analisis'
    TIPO_TABLA = 'tipo_analisis'
    TIPO_PK = 'id_tipo_analisis'
    TIPO_COL = 'id_tipo_analisis'
    PREFIJO = PREFIJO_ORDEN_ANALISIS
