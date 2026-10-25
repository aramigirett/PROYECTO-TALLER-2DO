from app.dao.referenciales_consultorio.tipo_procedimiento_medico.TipoProcedimientoMedicoDao import TipoProcedimientoMedicoDao
from app.rutas.modulo_consultorio.catalogo_api import Campo, crear_api_catalogo
from app.rutas.modulo_consultorio.utils import normalizar_descripcion

# Referencial `tipo_procedimiento_medico`. Descripción en MAYÚSCULAS (la normaliza el servidor) con el modo ampliado: letras con tildes y Ñ,
# números, espacios y . - / , % ( ) + &. Validación espejo en facturacion-validadores.js.
tipoprocedimientomedicoapi = crear_api_catalogo(
    blueprint='tipoprocedimientomedicoapi', ventana='tipoprocedimientomedico', ruta='/tipos-procedimiento-medico', dao_cls=TipoProcedimientoMedicoDao, entidad='tipo_procedimiento_medico', nombre='tipo de procedimiento médico',
    clave='descripcion', etiqueta_clave='Descripción', clave_frase='esa descripción',
    validar_clave=lambda d: normalizar_descripcion(d, 100, True),
)
