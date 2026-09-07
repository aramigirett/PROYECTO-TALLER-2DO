# Catálogo fijo de pantallas buscables desde el buscador general (CUS "Mantener Menú").
# Cada entrada: etiqueta visible, endpoint de Flask (para url_for), ícono FontAwesome,
# módulo al que pertenece (para agrupar en el resultado) y permiso_requerido.
#
# permiso_requerido = None  -> visible para cualquier usuario logueado (hoy estas
#   pantallas no tienen restricción de rol en el código).
# permiso_requerido = "<nombre>" -> solo visible si el rol del usuario tiene ese
#   permiso cargado en la tabla `permisos`, o si el usuario es Administrador
#   (Administrador siempre ve todo, igual que con @require_admin).

CATALOGO_MENU = [
    # Agendamiento
    {"etiqueta": "Registrar Agenda", "endpoint": "agenda_bp.index", "icono": "fa-calendar-alt", "modulo": "Agendamiento", "permiso_requerido": None},
    {"etiqueta": "Registrar Citas", "endpoint": "cita.citaIndex", "icono": "fa-book", "modulo": "Agendamiento", "permiso_requerido": None},
    {"etiqueta": "Registrar Avisos", "endpoint": "avisos_bp.avisos_recordatorios", "icono": "fa-bell", "modulo": "Agendamiento", "permiso_requerido": None},
    {"etiqueta": "Registrar Pacientes", "endpoint": "paciente.pacienteIndex", "icono": "fa-user-injured", "modulo": "Agendamiento", "permiso_requerido": None},
    {"etiqueta": "Registrar Funcionario", "endpoint": "funcionario.funcionarioIndex", "icono": "fa-users", "modulo": "Agendamiento", "permiso_requerido": None},
    {"etiqueta": "Registrar Médicos", "endpoint": "medico.medicoIndex", "icono": "fa-stethoscope", "modulo": "Agendamiento", "permiso_requerido": None},

    # Referenciales Agendamiento
    {"etiqueta": "Ciudad", "endpoint": "ciudad.ciudadIndex", "icono": "fa-map-marker-alt", "modulo": "Referenciales Agendamiento", "permiso_requerido": None},
    {"etiqueta": "Cargo", "endpoint": "cargo.cargoIndex", "icono": "fa-briefcase", "modulo": "Referenciales Agendamiento", "permiso_requerido": None},
    {"etiqueta": "Consultorio", "endpoint": "consultorio.consultorioIndex", "icono": "fa-clinic-medical", "modulo": "Referenciales Agendamiento", "permiso_requerido": None},
    {"etiqueta": "Disponibilidad Horaria", "endpoint": "disponibilidad.disponibilidadIndex", "icono": "fa-clock", "modulo": "Referenciales Agendamiento", "permiso_requerido": None},
    {"etiqueta": "Especialidad", "endpoint": "especialidad.especialidadIndex", "icono": "fa-certificate", "modulo": "Referenciales Agendamiento", "permiso_requerido": None},
    {"etiqueta": "Día", "endpoint": "dia.diaIndex", "icono": "fa-sun", "modulo": "Referenciales Agendamiento", "permiso_requerido": None},
    {"etiqueta": "Turno", "endpoint": "turno.turnoIndex", "icono": "fa-hourglass", "modulo": "Referenciales Agendamiento", "permiso_requerido": None},

    # Referenciales Consultorio
    {"etiqueta": "Tipo diagnóstico", "endpoint": "tipodiagnostico.tipoDiagnosticoIndex", "icono": "fa-microscope", "modulo": "Referenciales Consultorio", "permiso_requerido": None},
    {"etiqueta": "Síntomas", "endpoint": "sintoma.sintomaIndex", "icono": "fa-heartbeat", "modulo": "Referenciales Consultorio", "permiso_requerido": None},
    {"etiqueta": "Tipo Tratamiento", "endpoint": "tipotratamiento.tipoTratamientoIndex", "icono": "fa-notes-medical", "modulo": "Referenciales Consultorio", "permiso_requerido": None},
    {"etiqueta": "Tipo Insumo Utilizado", "endpoint": "tipoinsumo.tipoInsumoIndex", "icono": "fa-box-open", "modulo": "Referenciales Consultorio", "permiso_requerido": None},
    {"etiqueta": "Tipo Procedimiento Médico", "endpoint": "tipoprocedimientomedico.tipoProcedimientoMedicoIndex", "icono": "fa-syringe", "modulo": "Referenciales Consultorio", "permiso_requerido": None},
    {"etiqueta": "Medicamentos", "endpoint": "medicamento.medicamentoIndex", "icono": "fa-pills", "modulo": "Referenciales Consultorio", "permiso_requerido": None},
    {"etiqueta": "Tipo Estudio", "endpoint": "tipoestudio.tipoEstudioIndex", "icono": "fa-x-ray", "modulo": "Referenciales Consultorio", "permiso_requerido": None},
    {"etiqueta": "Tipo Análisis", "endpoint": "tipoanalisis.tipoAnalisisIndex", "icono": "fa-vial", "modulo": "Referenciales Consultorio", "permiso_requerido": None},

    # Módulo Consultorio
    {"etiqueta": "Registrar Consulta", "endpoint": "consulta.consultaIndex", "icono": "fa-stethoscope", "modulo": "Módulo Consultorio", "permiso_requerido": None},
    {"etiqueta": "Gestión Fichas Médicas", "endpoint": "fichamedica.fichaMedicaIndex", "icono": "fa-file-medical-alt", "modulo": "Módulo Consultorio", "permiso_requerido": None},
    {"etiqueta": "Gestión Diagnósticos", "endpoint": "diagnostico_medico.diagnosticoIndex", "icono": "fa-diagnoses", "modulo": "Módulo Consultorio", "permiso_requerido": None},
    {"etiqueta": "Historial Médico", "endpoint": "historial.historialIndex", "icono": "fa-history", "modulo": "Módulo Consultorio", "permiso_requerido": None},
    {"etiqueta": "Registrar Odontograma", "endpoint": "odontograma.odontogramaIndex", "icono": "fa-teeth", "modulo": "Módulo Consultorio", "permiso_requerido": None},

    # Módulo Seguridad (restringidas por permiso, salvo Administrador)
    {"etiqueta": "Gestión de Usuarios", "endpoint": "usuario.usuarioIndex", "icono": "fa-users-cog", "modulo": "Módulo Seguridad", "permiso_requerido": "gestionar_usuarios"},
    {"etiqueta": "Roles y Permisos", "endpoint": "permiso.permisoIndex", "icono": "fa-key", "modulo": "Módulo Seguridad", "permiso_requerido": "gestionar_permisos"},
    {"etiqueta": "Tablero de Administrador", "endpoint": "auditoria.auditoriaIndex", "icono": "fa-shield-alt", "modulo": "Módulo Seguridad", "permiso_requerido": "ver_auditoria"},
]
