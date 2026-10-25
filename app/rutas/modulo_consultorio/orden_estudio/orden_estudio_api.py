"""API: Orden de Estudios (/api/v1/orden-estudios). Las reglas y los endpoints viven en orden_api_base.crear_orden_api (idéntica a la Orden de Análisis)."""
from app.dao.referenciales_consultorio.orden_estudio.OrdenEstudioDao import OrdenEstudioDao
from app.rutas.modulo_consultorio.orden_api_base import crear_orden_api
from app.rutas.modulo_consultorio.validadores_clinicos import validar_orden_estudio

ordenestudioapi = crear_orden_api(
    blueprint='ordenestudioapi', ventana='ordenestudio', ruta='/orden-estudios', dao_cls=OrdenEstudioDao, entidad='orden_estudios', pk='id_orden_estudio',
    tipo_col='id_tipo_estudio', nombre='orden de estudios', pdf_tipo='orden_estudio', validar=validar_orden_estudio)
