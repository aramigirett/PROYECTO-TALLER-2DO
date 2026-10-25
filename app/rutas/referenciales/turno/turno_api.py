from app.dao.referenciales.turno.TurnoDao import TurnoDao
from app.rutas.modulo_consultorio.catalogo_api import crear_api_catalogo
from app.rutas.modulo_agendamiento.utils import normalizar_descripcion

# Referencial `turnos` (Estándar de referenciales). ABM completo: la base soltó el CHECK de los 3 turnos fijos.
# Validación espejo en facturacion-validadores.js.
turnoapi = crear_api_catalogo(
    blueprint='turnoapi', ventana='turno', ruta='/turnos', dao_cls=TurnoDao, entidad='turnos', nombre='turno',
    clave='descripcion', etiqueta_clave='Descripción', clave_frase='esa descripción',
    validar_clave=lambda d: normalizar_descripcion(d),
)
