from app.dao.referenciales_agendamiento.persona_dao import PersonaDao, DUPLICADO, INVALIDO, NO_EXISTE, YA_ACTIVO  # noqa: F401


class PacienteDao(PersonaDao):
    """
    Paciente (dato maestro con borrado lógico). Se anula solo si no tiene trabajo en curso; su historia clínica y sus citas realizadas
    se conservan. Cliente (Facturación) toma FOR SHARE sobre la fila al guardarse.
    """
    TABLA = 'paciente'
    PK = 'id_paciente'
    DOC = 'cedula_entidad'
    NOMBRE = 'paciente'
    CAMPOS = ('nombre', 'apellido', 'cedula_entidad', 'fecha_nacimiento', 'telefono', 'telefono_emergencia', 'direccion', 'correo', 'id_ciudad')
    PADRES = (('id_ciudad', 'ciudades', 'id_ciudad', 'descripcion', 'ciudades', 'ciudad'),)
    DUPLICADOS = (('cedula_entidad', 'esa cédula'), ('correo', 'ese correo'))
    MINIMO = ('nombre', 'apellido', 'cedula_entidad', 'fecha_nacimiento')

    def _motivo_en_uso(self, cur, id_registro, quien):
        usos = (
            ("SELECT COUNT(*) FROM cliente WHERE id_paciente = %s AND activo = true", "está registrado como cliente"),
            ("""SELECT COUNT(*) FROM cita_detalle cd JOIN cita_cabecera cc ON cc.id_cita_cabecera = cd.id_cita_cabecera
                JOIN estado_cita ec ON ec.id_estado_cita = cd.id_estado_cita
                WHERE cc.id_paciente = %s AND cc.estado <> 'Inactivo' AND ec.descripcion IN ('Reservado', 'Confirmado')""", "tiene {n} cita(s) pendiente(s)"),
            ("SELECT COUNT(*) FROM consultas_cab WHERE id_paciente = %s AND activo = true AND estado IN ('programada', 'en_proceso')", "tiene {n} consulta(s) en curso"),
            ("SELECT COUNT(*) FROM tratamientos WHERE id_paciente = %s AND estado IN ('pendiente', 'en_seguimiento')", "tiene {n} tratamiento(s) en curso"),
            ("SELECT COUNT(*) FROM avisos_recordatorios WHERE id_paciente = %s AND estado <> 'Inactivo' AND estado_envio = 'Pendiente'", "tiene {n} aviso(s) pendiente(s)"),
        )
        for sql, texto in usos:
            n = self._cuenta(cur, sql, id_registro)
            if n:
                return f"No se puede anular al paciente {quien}: " + texto.format(n=n) + "."
        return False
