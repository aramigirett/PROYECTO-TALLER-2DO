from app.dao.referenciales_consultorio.tipo_insumo.TipoInsumoDao import TipoInsumoDao
from app.rutas.modulo_consultorio.catalogo_api import Campo, crear_api_catalogo
from app.rutas.modulo_consultorio.utils import normalizar_descripcion, validar_presentacion

# Referencial `insumos`. Descripción en MAYÚSCULAS (la normaliza el servidor) con el modo ampliado: letras con tildes y Ñ,
# números, espacios y . - / , % ( ) + &. Validación espejo en facturacion-validadores.js.
tipoinsumoapi = crear_api_catalogo(
    blueprint='tipoinsumoapi', ventana='tipoinsumo', ruta='/tipos-insumo', dao_cls=TipoInsumoDao, entidad='insumos', nombre='tipo de insumo',
    clave='descripcion', etiqueta_clave='Descripción', clave_frase='esa descripción',
    validar_clave=lambda d: normalizar_descripcion(d, 100, True),
    extras=[Campo('presentacion', 'Presentación', lambda d: validar_presentacion(d.get('presentacion')))],
)
