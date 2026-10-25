from app.dao.referenciales_consultorio.tipo_diagnostico.TipoDiagnosticoDao import TipoDiagnosticoDao
from app.rutas.modulo_consultorio.catalogo_api import Campo, crear_api_catalogo
from app.rutas.modulo_consultorio.utils import normalizar_descripcion

# Referencial `tipo_diagnostico`. La URL sigue siendo /diagnosticos (la consume también Gestión de Diagnósticos para su combo).
# Descripción y tipo en MAYÚSCULAS, modo ampliado (tildes, Ñ, números y . - / , % ( ) + &). Validación espejo en facturacion-validadores.js.
tipodiagnosticoapi = crear_api_catalogo(
    blueprint='tipodiagnosticoapi', ventana='tipodiagnostico', ruta='/diagnosticos', dao_cls=TipoDiagnosticoDao,
    entidad='tipo_diagnostico', nombre='tipo de diagnóstico', clave='descripcion_diagnostico', etiqueta_clave='Descripción',
    clave_frase='esa descripción',
    validar_clave=lambda d: normalizar_descripcion(d, 100, True, 'descripcion_diagnostico'),
    extras=[Campo('tipo_diagnostico', 'Tipo de diagnóstico',
                  lambda d: normalizar_descripcion(d, 100, True, 'tipo_diagnostico', 'tipo de diagnóstico', 'El'))],
)
