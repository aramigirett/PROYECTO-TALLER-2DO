from app.dao.referenciales_consultorio.sintomas.SintomasDao import SintomaDao
from app.rutas.modulo_consultorio.catalogo_api import crear_api_catalogo
from app.rutas.modulo_consultorio.utils import normalizar_descripcion

# Referencial `sintoma`. Descripción en MAYÚSCULAS, modo ampliado (tildes, Ñ, números y . - / , % ( ) + &).
# Validación espejo en facturacion-validadores.js.
sintomaapi = crear_api_catalogo(
    blueprint='sintomaapi', ventana='sintoma', ruta='/sintomas', dao_cls=SintomaDao, entidad='sintoma', nombre='síntoma',
    clave='descripcion_sintoma', etiqueta_clave='Descripción', clave_frase='esa descripción',
    validar_clave=lambda d: normalizar_descripcion(d, 100, True, 'descripcion_sintoma'),
)
