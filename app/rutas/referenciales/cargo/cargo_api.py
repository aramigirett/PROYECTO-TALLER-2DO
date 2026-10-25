from app.dao.referenciales.cargo.CargoDao import CargoDao
from app.rutas.modulo_consultorio.catalogo_api import crear_api_catalogo
from app.rutas.modulo_agendamiento.utils import normalizar_descripcion

# Referencial `cargo` (Estándar de referenciales). Descripción en MAYÚSCULAS.
# Validación espejo en facturacion-validadores.js.
cargoapi = crear_api_catalogo(
    blueprint='cargoapi', ventana='cargo', ruta='/cargos', dao_cls=CargoDao, entidad='cargo', nombre='cargo',
    clave='descripcion', etiqueta_clave='Descripción', clave_frase='esa descripción',
    validar_clave=lambda d: normalizar_descripcion(d),
)
