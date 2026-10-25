from app.dao.referenciales.especialidad.EspecialidadDao import EspecialidadDao
from app.rutas.modulo_consultorio.catalogo_api import crear_api_catalogo
from app.rutas.modulo_agendamiento.utils import normalizar_descripcion

# Referencial `especialidades` (Estándar de referenciales). Nombre en MAYÚSCULAS (hasta 100 caracteres).
# Validación espejo en facturacion-validadores.js.
especiapi = crear_api_catalogo(
    blueprint='especiapi', ventana='especialidad', ruta='/especialidades', dao_cls=EspecialidadDao, entidad='especialidades', nombre='especialidad',
    clave='nombre_especialidad', etiqueta_clave='Nombre', clave_frase='ese nombre',
    validar_clave=lambda d: normalizar_descripcion(d, 100, False, 'nombre_especialidad', 'nombre'),
    femenino=True,
)
