"""API: Orden de Análisis (/api/v1/orden-analisis). Las reglas y los endpoints viven en orden_api_base.crear_orden_api (idéntica a la Orden de Estudios)."""
from app.dao.referenciales_consultorio.orden_analisis.OrdenAnalisisDao import OrdenAnalisisDao
from app.rutas.modulo_consultorio.orden_api_base import crear_orden_api
from app.rutas.modulo_consultorio.validadores_clinicos import validar_orden_analisis

ordenanalisisapi = crear_orden_api(
    blueprint='ordenanalisisapi', ventana='ordenanalisis', ruta='/orden-analisis', dao_cls=OrdenAnalisisDao, entidad='orden_analisis', pk='id_orden_analisis',
    tipo_col='id_tipo_analisis', nombre='orden de análisis', pdf_tipo='orden_analisis', validar=validar_orden_analisis)
