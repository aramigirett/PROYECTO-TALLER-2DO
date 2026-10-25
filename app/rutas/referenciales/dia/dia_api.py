from app.dao.referenciales.dia.DiaDao import DiaDao
from app.rutas.modulo_consultorio.catalogo_api import crear_api_catalogo
from app.rutas.modulo_agendamiento.utils import validar_dia

# Referencial `dias` (Estándar de referenciales). Solo admite uno de los 7 días de la semana (la base conserva el CHECK); el alta rechaza un día que ya exista activo.
# Validación espejo en facturacion-validadores.js.
diaapi = crear_api_catalogo(
    blueprint='diaapi', ventana='dia', ruta='/dias', dao_cls=DiaDao, entidad='dias', nombre='día',
    clave='descripcion', etiqueta_clave='Día', clave_frase='ese día',
    validar_clave=validar_dia,
)
