from app.dao.referenciales_agendamiento.consultorio.ConsultorioDao import ConsultorioDao
from app.rutas.modulo_consultorio.catalogo_api import Campo, crear_api_catalogo
from app.rutas.modulo_agendamiento.utils import MAX_DIRECCION, normalizar_descripcion, validar_correo, validar_texto, validar_telefono

# Referencial `consultorio` (PK `codigo`, Estándar de referenciales). Nombre en MAYÚSCULAS; dirección, teléfono (celular o línea baja, se guarda
# solo con dígitos y el 0 inicial) y correo obligatorios. Validación espejo en facturacion-validadores.js.
consultorioapi = crear_api_catalogo(
    blueprint='consultorioapi', ventana='consultorio', ruta='/consultorios', dao_cls=ConsultorioDao, entidad='consultorio', nombre='consultorio',
    clave='nombre_consultorio', etiqueta_clave='Nombre', clave_frase='ese nombre',
    validar_clave=lambda d: normalizar_descripcion(d, 100, True, 'nombre_consultorio', 'nombre', 'El'),
    extras=[
        Campo('direccion', 'Dirección', lambda d: validar_texto(d.get('direccion'), 'dirección', MAX_DIRECCION)),
        Campo('telefono', 'Teléfono', lambda d: validar_telefono(d.get('telefono'))),
        Campo('correo', 'Correo', lambda d: validar_correo(d.get('correo'))),
    ],
)
