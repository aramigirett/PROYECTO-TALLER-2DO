from app.dao.referenciales_agendamiento.persona_dao import PersonaDao, DUPLICADO, INVALIDO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class MedicoDao(PersonaDao):
    """
    Médico (dato maestro con borrado lógico). Se anula solo si no tiene usuario de acceso activo ni trabajo en curso. La cédula es el CI/RUC de
    login del usuario vinculado: no puede repetirse entre médicos y funcionarios activos.
    """
    TABLA = 'medico'
    PK = 'id_medico'
    DOC = 'cedula'
    NOMBRE = 'médico'
    USUARIO = 'id_medico'
    CAMPOS = ('nombre', 'apellido', 'id_especialidad', 'num_registro', 'cedula', 'fecha_nacimiento', 'telefono', 'direccion', 'correo', 'id_ciudad')
    PADRES = (('id_especialidad', 'especialidades', 'id_especialidad', 'nombre_especialidad', 'especialidades', 'especialidad'),
              ('id_ciudad', 'ciudades', 'id_ciudad', 'descripcion', 'ciudades', 'ciudad'))
    DUPLICADOS = (('cedula', 'esa cédula'), ('num_registro', 'ese N.º de registro'))
    MINIMO = ('nombre', 'apellido', 'id_especialidad', 'especialidades')

    def _motivo_en_uso(self, cur, id_registro, quien):
        usos = (
            ("SELECT COUNT(*) FROM usuarios WHERE id_medico = %s AND activo = true", "tiene un usuario de acceso activo. Anule primero el usuario"),
            ("SELECT COUNT(*) FROM agenda_cabecera WHERE id_medico = %s AND estado <> 'Inactivo' AND fecha_agenda >= CURRENT_DATE", "tiene {n} agenda(s) vigente(s)"),
            ("SELECT COUNT(*) FROM disponibilidad_horaria WHERE id_medico = %s AND activo = true AND dispo_fecha >= CURRENT_DATE", "tiene {n} disponibilidad(es) horaria(s) vigente(s)"),
            ("SELECT COUNT(*) FROM consultas_cab WHERE id_medico = %s AND activo = true AND estado IN ('programada', 'en_proceso')", "tiene {n} consulta(s) en curso"),
            ("SELECT COUNT(*) FROM tratamientos WHERE id_medico = %s AND estado IN ('pendiente', 'en_seguimiento')", "tiene {n} tratamiento(s) en curso"),
            ("SELECT COUNT(*) FROM avisos_recordatorios WHERE id_medico = %s AND estado <> 'Inactivo' AND estado_envio = 'Pendiente'", "tiene {n} aviso(s) pendiente(s)"),
        )
        for sql, texto in usos:
            n = self._cuenta(cur, sql, id_registro)
            if n:
                return f"No se puede anular al médico {quien}: " + texto.format(n=n) + "."
        return False
