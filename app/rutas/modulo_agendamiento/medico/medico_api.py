from app.dao.referenciales_agendamiento.medico.MedicoDao import MedicoDao
from app.rutas.modulo_agendamiento.persona_api import crear_api_persona
from app.rutas.modulo_agendamiento.utils import validar_persona

# Médico (dato maestro con borrado lógico). La cédula es el CI/RUC de login del usuario vinculado: cambiarla pide confirmación y se audita
# en el tablero de accesos; no puede repetirse entre médicos y funcionarios activos. Solo el Administrador gestiona.
medicoapi = crear_api_persona(
    blueprint='medicoapi', ventana='medico', ruta='/medico', dao_cls=MedicoDao, entidad='medico', nombre='médico', articulo='el', doc='cedula',
    validar=lambda d: validar_persona(d, 'cedula', con_registro=True, padres=[('id_especialidad', 'especialidad'), ('id_ciudad', 'ciudad')]),
    auditados={'nombre': 'Nombre', 'apellido': 'Apellido', 'cedula': 'Cédula', 'num_registro': 'N.º de registro',
               'especialidades': 'Especialidad', 'ciudades': 'Ciudad'},
)
