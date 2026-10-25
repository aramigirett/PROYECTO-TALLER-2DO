from app.dao.referenciales_consultorio.medicamento.MedicamentoDao import MedicamentoDao
from app.rutas.modulo_consultorio.catalogo_api import Campo, crear_api_catalogo
from app.rutas.modulo_consultorio.utils import normalizar_descripcion, validar_presentacion

# Referencial `medicamentos`. Descripción en MAYÚSCULAS (la normaliza el servidor) con el modo ampliado: letras con tildes y Ñ,
# números, espacios y . - / , % ( ) + &. Validación espejo en facturacion-validadores.js.
medicamentoapi = crear_api_catalogo(
    blueprint='medicamentoapi', ventana='medicamento', ruta='/medicamentos', dao_cls=MedicamentoDao, entidad='medicamentos', nombre='medicamento',
    clave='nombre_comercial', etiqueta_clave='Nombre comercial', clave_frase='ese nombre comercial',
    validar_clave=lambda d: normalizar_descripcion(d, 100, True, 'nombre_comercial', 'nombre comercial', 'El'),
    extras=[Campo('presentacion', 'Presentación', lambda d: validar_presentacion(d.get('presentacion')))],
)
