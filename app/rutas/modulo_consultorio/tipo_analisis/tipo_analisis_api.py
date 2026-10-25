from app.dao.referenciales_consultorio.tipo_analisis.TipoAnalisisDao import TipoAnalisisDao
from app.rutas.modulo_consultorio.catalogo_api import Campo, crear_api_catalogo
from app.rutas.modulo_consultorio.utils import normalizar_descripcion

# Referencial `tipo_analisis`. Descripción en MAYÚSCULAS (la normaliza el servidor) con el modo ampliado: letras con tildes y Ñ,
# números, espacios y . - / , % ( ) + &. Validación espejo en facturacion-validadores.js.
tipoanalisisapi = crear_api_catalogo(
    blueprint='tipoanalisisapi', ventana='tipoanalisis', ruta='/tipos-analisis', dao_cls=TipoAnalisisDao, entidad='tipo_analisis', nombre='tipo de análisis',
    clave='descripcion', etiqueta_clave='Descripción', clave_frase='esa descripción',
    validar_clave=lambda d: normalizar_descripcion(d, 100, True),
)
