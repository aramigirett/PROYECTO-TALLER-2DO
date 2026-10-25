from app.dao.referenciales_consultorio.tipo_tratamiento.TipoTratamientoDao import TipoTratamientoDao
from app.rutas.modulo_consultorio.catalogo_api import Campo, crear_api_catalogo
from app.rutas.modulo_consultorio.utils import normalizar_descripcion, validar_precio, validar_iva

MSG_PRECIO = 'El precio debe ser un número entero mayor a 0.'


def _precio(data):
    # Un único mensaje para cualquier precio inválido (vacío, decimal, texto, <= 0, fuera de rango)
    valor, error = validar_precio(data.get('precio'))
    return valor, (MSG_PRECIO if error else None)


# Referencial `tipos_tratamiento`. Descripción en MAYÚSCULAS (la normaliza el servidor) con el modo ampliado: letras con tildes y Ñ,
# números, espacios y . - / , % ( ) + &. Validación espejo en facturacion-validadores.js.
tipotratamientoapi = crear_api_catalogo(
    blueprint='tipotratamientoapi', ventana='tipotratamiento', ruta='/tipos-tratamiento', dao_cls=TipoTratamientoDao, entidad='tipos_tratamiento', nombre='tipo de tratamiento',
    clave='descripcion', etiqueta_clave='Descripción', clave_frase='esa descripción',
    validar_clave=lambda d: normalizar_descripcion(d, 100, True),
    extras=[Campo('precio', 'Precio', _precio), Campo('iva', 'IVA', lambda d: validar_iva(d.get('iva')))],
)
