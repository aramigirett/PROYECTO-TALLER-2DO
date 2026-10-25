from app.dao.referenciales.funcionario.FuncionarioDao import FuncionarioDao
from app.rutas.modulo_agendamiento.persona_api import crear_api_persona
from app.rutas.modulo_agendamiento.utils import validar_persona

# Funcionario (dato maestro con borrado lógico). La cédula es el CI/RUC de login del usuario vinculado: cambiarla pide confirmación y se audita
# en el tablero de accesos; no puede repetirse entre médicos y funcionarios activos. Solo el Administrador gestiona.
funcionarioapi = crear_api_persona(
    blueprint='funcionarioapi', ventana='funcionario', ruta='/funcionarios', dao_cls=FuncionarioDao, entidad='funcionario', nombre='funcionario',
    articulo='el', doc='cedula',
    validar=lambda d: validar_persona(d, 'cedula', padres=[('id_cargo', 'cargo')]),
    auditados={'nombre': 'Nombre', 'apellido': 'Apellido', 'cedula': 'Cédula', 'cargo': 'Cargo'},
)
