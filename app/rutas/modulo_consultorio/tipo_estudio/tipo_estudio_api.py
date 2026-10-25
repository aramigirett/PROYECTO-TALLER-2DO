from app.dao.referenciales_consultorio.tipo_estudio.TipoEstudioDao import TipoEstudioDao
from app.rutas.modulo_consultorio.catalogo_api import Campo, crear_api_catalogo
from app.rutas.modulo_consultorio.utils import normalizar_descripcion

# Referencial `tipo_estudio`. Descripción en MAYÚSCULAS (la normaliza el servidor) con el modo ampliado: letras con tildes y Ñ,
# números, espacios y . - / , % ( ) + &. Validación espejo en facturacion-validadores.js.
tipoestudioapi = crear_api_catalogo(
    blueprint='tipoestudioapi', ventana='tipoestudio', ruta='/tipos-estudio', dao_cls=TipoEstudioDao, entidad='tipo_estudio', nombre='tipo de estudio',
    clave='descripcion', etiqueta_clave='Descripción', clave_frase='esa descripción',
    validar_clave=lambda d: normalizar_descripcion(d, 100, True),
)
