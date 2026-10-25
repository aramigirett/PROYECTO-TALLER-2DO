from app.dao.referenciales_agendamiento.paciente.PacienteDao import PacienteDao
from app.rutas.modulo_agendamiento.persona_api import crear_api_persona
from app.rutas.modulo_agendamiento.utils import validar_persona

# Paciente (dato maestro con borrado lógico). Nombre y apellido en MAYÚSCULAS; la fecha de alta la pone el servidor.
# Validación espejo en facturacion-validadores.js. Solo el Administrador anula (y reactiva).
pacienteapi = crear_api_persona(
    blueprint='pacienteapi', ventana='paciente', ruta='/pacientes', dao_cls=PacienteDao, entidad='paciente', nombre='paciente', articulo='el',
    doc='cedula_entidad',
    validar=lambda d: validar_persona(d, 'cedula_entidad', con_emergencia=True, padres=[('id_ciudad', 'ciudad')]),
    auditados={'nombre': 'Nombre', 'apellido': 'Apellido', 'cedula_entidad': 'Cédula', 'ciudades': 'Ciudad'},
)
