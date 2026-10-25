from app.dao.referenciales_agendamiento.persona_dao import PersonaDao, DUPLICADO, INVALIDO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class FuncionarioDao(PersonaDao):
    """
    Funcionario (dato maestro con borrado lógico). Se anula solo si no tiene usuario de acceso activo ni trabajo en curso. La cédula es el
    CI/RUC de login del usuario vinculado: no puede repetirse entre médicos y funcionarios activos.
    """
    TABLA = 'funcionario'
    PK = 'id_funcionario'
    DOC = 'cedula'
    NOMBRE = 'funcionario'
    USUARIO = 'id_funcionario'
    CAMPOS = ('nombre', 'apellido', 'cedula', 'fecha_nacimiento', 'telefono', 'direccion', 'correo', 'id_cargo')
    PADRES = (('id_cargo', 'cargo', 'id_cargo', 'descripcion', 'cargo', 'cargo'),)
    DUPLICADOS = (('cedula', 'esa cédula'), ('correo', 'ese correo'))
    MINIMO = ('nombre', 'apellido', 'id_cargo', 'cargo')

    def _motivo_en_uso(self, cur, id_registro, quien):
        usos = (
            ("SELECT COUNT(*) FROM usuarios WHERE id_funcionario = %s AND activo = true", "tiene un usuario de acceso activo. Anule primero el usuario"),
            ("SELECT COUNT(*) FROM consultas_cab WHERE id_funcionario = %s AND activo = true AND estado IN ('programada', 'en_proceso')", "tiene {n} consulta(s) en curso"),
            ("SELECT COUNT(*) FROM avisos_recordatorios WHERE id_funcionario = %s AND estado <> 'Inactivo' AND estado_envio = 'Pendiente'", "tiene {n} aviso(s) pendiente(s)"),
        )
        for sql, texto in usos:
            n = self._cuenta(cur, sql, id_registro)
            if n:
                return f"No se puede anular al funcionario {quien}: " + texto.format(n=n) + "."
        return False
