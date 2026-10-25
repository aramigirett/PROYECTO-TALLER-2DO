from app.dao.referenciales.ciudad.CiudadDao import CiudadDao
from app.rutas.modulo_consultorio.catalogo_api import crear_api_catalogo
from app.rutas.modulo_agendamiento.utils import normalizar_descripcion

# Referencial `ciudades` (Estándar de referenciales). Descripción en MAYÚSCULAS.
# Validación espejo en facturacion-validadores.js.
ciuapi = crear_api_catalogo(
    blueprint='ciuapi', ventana='ciudad', ruta='/ciudades', dao_cls=CiudadDao, entidad='ciudades', nombre='ciudad',
    clave='descripcion', etiqueta_clave='Descripción', clave_frase='esa descripción',
    validar_clave=lambda d: normalizar_descripcion(d),
    femenino=True,
)
