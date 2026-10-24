# Catálogo único de pantallas del sistema. De acá salen, dinámicamente:
# el sidebar de base.html, el buscador general (CUS "Mantener Menú") y las
# filas de la matriz de "Roles y Permisos" (CUS "Mantener Acceso" -
# Accesibilidad). Agregar una pantalla nueva = una entrada acá.
#
# Cada entrada:
#   etiqueta   -> texto visible
#   endpoint   -> endpoint de Flask (para url_for)
#   icono      -> clase FontAwesome
#   modulo     -> agrupador visual (debe existir en MODULOS, más abajo)
#   ventana    -> clave estable usada en la tabla `permisos` (rol+ventana+accion)
#   en_menu    -> (opcional, default True) False = no se muestra en sidebar ni buscador,
#                 solo en la matriz de permisos (pantallas contextuales)
#   solo_admin -> (opcional) True = ventana exclusiva del Administrador: no sale en la matriz de Roles y Permisos y
#                 puede() devuelve False para cualquier otro rol (hoy: Copias de Seguridad).
#   acciones   -> subconjunto de ('ver','nuevo','editar','anular','estado','desbloquear') que expone
#                 esa ventana. 'ver' siempre debe estar. 'editar' solo en las
#                 ventanas donde el CUS lo contempla explícitamente (hoy:
#                 Ficha Médica y las referenciales). Los movimientos
#                 clínicos/de agendamiento son ver+nuevo+anular por defecto.
#
# NOTA: "Roles y Permisos" (matriz) NO está en este catálogo a propósito:
# queda siempre exclusiva de Administrador vía @require_admin, fuera del
# mecanismo de permisos delegables, para que nadie pueda autoconcederse
# acceso. Sigue teniendo su link fijo en el sidebar (ver base.html).
#
# NOTA 1b: acción 'desbloquear' = levantar el bloqueo de una cuenta por intentos
# fallidos. Solo la expone la ventana 'usuario'.
#
# NOTA 2: acción 'estado' = cambios de estado del flujo (no baja ni edición de
# datos). Hoy: Cita (estado de cada horario) y Avisos (confirmación y envío por
# WhatsApp) y, en Consultorio, Duración/Estado de la Consulta, Actualizar Estado
# de Órdenes de Estudios/Análisis y Finalizar Tratamiento. 'anular' incluye
# anular/reactivar. En Consultorio solo Ficha Médica expone 'editar'; las
# demás ediciones de datos (detalle clínico de Consulta, Odontograma) exigen
# 'editar' sin que exista en su ventana: quedan solo para Administrador.
# Paciente/Funcionario/Médico tienen 'editar' (datos maestros). Agenda, Cita,
# Avisos e Historial NO la exponen: su edición de datos (PUT) exige 'editar',
# que ningún rol no-admin puede tener, o sea queda solo para Administrador.

MODULOS = [
    {"modulo": "Agendamiento", "icono": "fa-calendar-check"},
    {"modulo": "Referenciales Agendamiento", "icono": "fa-file-alt"},
    {"modulo": "Referenciales Consultorio", "icono": "fa-file-alt"},
    {"modulo": "Módulo Consultorio", "icono": "fa-file-medical"},
    {"modulo": "Referenciales Facturación", "icono": "fa-file-invoice-dollar"},
    {"modulo": "Módulo Facturación", "icono": "fa-cash-register"},
    {"modulo": "Módulo Seguridad", "icono": "fa-user-shield"},
]

CATALOGO_MENU = [
    # Agendamiento
    {"etiqueta": "Registrar Agenda", "endpoint": "agenda_bp.index", "icono": "fa-calendar-alt", "modulo": "Agendamiento", "ventana": "agenda", "acciones": ["ver", "nuevo", "anular"]},
    {"etiqueta": "Registrar Citas", "endpoint": "cita.citaIndex", "icono": "fa-book", "modulo": "Agendamiento", "ventana": "cita", "acciones": ["ver", "nuevo", "anular", "estado"]},
    {"etiqueta": "Registrar Avisos", "endpoint": "avisos_bp.avisos_recordatorios", "icono": "fa-bell", "modulo": "Agendamiento", "ventana": "avisos", "acciones": ["ver", "nuevo", "anular", "estado"]},
    {"etiqueta": "Registrar Pacientes", "endpoint": "paciente.pacienteIndex", "icono": "fa-user-injured", "modulo": "Agendamiento", "ventana": "paciente", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Registrar Funcionario", "endpoint": "funcionario.funcionarioIndex", "icono": "fa-users", "modulo": "Agendamiento", "ventana": "funcionario", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Registrar Médicos", "endpoint": "medico.medicoIndex", "icono": "fa-stethoscope", "modulo": "Agendamiento", "ventana": "medico", "acciones": ["ver", "nuevo", "editar", "anular"]},

    # Referenciales Agendamiento
    {"etiqueta": "Ciudad", "endpoint": "ciudad.ciudadIndex", "icono": "fa-map-marker-alt", "modulo": "Referenciales Agendamiento", "ventana": "ciudad", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Cargo", "endpoint": "cargo.cargoIndex", "icono": "fa-briefcase", "modulo": "Referenciales Agendamiento", "ventana": "cargo", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Consultorio", "endpoint": "consultorio.consultorioIndex", "icono": "fa-clinic-medical", "modulo": "Referenciales Agendamiento", "ventana": "consultorio", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Disponibilidad Horaria", "endpoint": "disponibilidad.disponibilidadIndex", "icono": "fa-clock", "modulo": "Referenciales Agendamiento", "ventana": "disponibilidad", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Especialidad", "endpoint": "especialidad.especialidadIndex", "icono": "fa-certificate", "modulo": "Referenciales Agendamiento", "ventana": "especialidad", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Día", "endpoint": "dia.diaIndex", "icono": "fa-sun", "modulo": "Referenciales Agendamiento", "ventana": "dia", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Turno", "endpoint": "turno.turnoIndex", "icono": "fa-hourglass", "modulo": "Referenciales Agendamiento", "ventana": "turno", "acciones": ["ver", "nuevo", "editar", "anular"]},

    # Referenciales Consultorio
    {"etiqueta": "Tipo diagnóstico", "endpoint": "tipodiagnostico.tipoDiagnosticoIndex", "icono": "fa-microscope", "modulo": "Referenciales Consultorio", "ventana": "tipodiagnostico", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Síntomas", "endpoint": "sintoma.sintomaIndex", "icono": "fa-heartbeat", "modulo": "Referenciales Consultorio", "ventana": "sintoma", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Tipo Tratamiento", "endpoint": "tipotratamiento.tipoTratamientoIndex", "icono": "fa-notes-medical", "modulo": "Referenciales Consultorio", "ventana": "tipotratamiento", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Tipo Insumo Utilizado", "endpoint": "tipoinsumo.tipoInsumoIndex", "icono": "fa-box-open", "modulo": "Referenciales Consultorio", "ventana": "tipoinsumo", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Tipo Procedimiento Médico", "endpoint": "tipoprocedimientomedico.tipoProcedimientoMedicoIndex", "icono": "fa-syringe", "modulo": "Referenciales Consultorio", "ventana": "tipoprocedimientomedico", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Medicamentos", "endpoint": "medicamento.medicamentoIndex", "icono": "fa-pills", "modulo": "Referenciales Consultorio", "ventana": "medicamento", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Tipo Estudio", "endpoint": "tipoestudio.tipoEstudioIndex", "icono": "fa-x-ray", "modulo": "Referenciales Consultorio", "ventana": "tipoestudio", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Tipo Análisis", "endpoint": "tipoanalisis.tipoAnalisisIndex", "icono": "fa-vial", "modulo": "Referenciales Consultorio", "ventana": "tipoanalisis", "acciones": ["ver", "nuevo", "editar", "anular"]},

    # Módulo Consultorio
    {"etiqueta": "Registrar Consulta", "endpoint": "consulta.consultaIndex", "icono": "fa-stethoscope", "modulo": "Módulo Consultorio", "ventana": "consulta", "acciones": ["ver", "nuevo", "anular", "estado"]},
    {"etiqueta": "Gestión Fichas Médicas", "endpoint": "fichamedica.fichaMedicaIndex", "icono": "fa-file-medical-alt", "modulo": "Módulo Consultorio", "ventana": "fichamedica", "acciones": ["ver", "editar", "anular"]},
    {"etiqueta": "Gestión Diagnósticos", "endpoint": "diagnostico_medico.diagnosticoIndex", "icono": "fa-diagnoses", "modulo": "Módulo Consultorio", "ventana": "diagnostico", "acciones": ["ver", "nuevo", "anular"]},
    {"etiqueta": "Historial Médico", "endpoint": "historial.historialIndex", "icono": "fa-history", "modulo": "Módulo Consultorio", "ventana": "historial", "acciones": ["ver", "nuevo", "anular"]},
    {"etiqueta": "Registrar Odontograma", "endpoint": "odontograma.odontogramaIndex", "icono": "fa-teeth", "modulo": "Módulo Consultorio", "ventana": "odontograma", "acciones": ["ver", "nuevo", "anular"]},
    {"etiqueta": "Gestionar Tratamientos", "endpoint": "tratamiento.tratamientoIndex", "icono": "fa-prescription-bottle-alt", "modulo": "Módulo Consultorio", "ventana": "tratamiento", "acciones": ["ver", "nuevo", "anular", "estado"]},
    {"etiqueta": "Generar Recetas e Indicaciones", "endpoint": "receta.recetaIndex", "icono": "fa-prescription", "modulo": "Módulo Consultorio", "ventana": "receta", "acciones": ["ver", "nuevo", "anular"]},
    # Sin entrada en el sidebar ni en el buscador (en_menu False): se llega siempre desde
    # Gestionar Tratamientos. Está en el catálogo para tener su fila en la matriz de permisos.
    {"etiqueta": "Procedimientos e Insumos (Sesiones)", "endpoint": "sesiontratamiento.sesionTratamientoIndex", "icono": "fa-notes-medical", "modulo": "Módulo Consultorio", "ventana": "sesiontratamiento", "acciones": ["ver", "nuevo", "anular"], "en_menu": False},
    {"etiqueta": "Generar Orden de Estudios", "endpoint": "ordenestudio.ordenEstudioIndex", "icono": "fa-vial", "modulo": "Módulo Consultorio", "ventana": "ordenestudio", "acciones": ["ver", "nuevo", "anular", "estado"]},
    {"etiqueta": "Generar Orden de Análisis", "endpoint": "ordenanalisis.ordenAnalisisIndex", "icono": "fa-flask", "modulo": "Módulo Consultorio", "ventana": "ordenanalisis", "acciones": ["ver", "nuevo", "anular", "estado"]},
    {"etiqueta": "Generar Justificativo Médico", "endpoint": "justificativomedico.justificativoMedicoIndex", "icono": "fa-file-signature", "modulo": "Módulo Consultorio", "ventana": "justificativomedico", "acciones": ["ver", "nuevo", "anular"]},

    # Referenciales Facturación
    {"etiqueta": "Forma de Cobro", "endpoint": "formacobro.formaCobroIndex", "icono": "fa-money-bill-wave", "modulo": "Referenciales Facturación", "ventana": "formacobro", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Marca de Tarjeta", "endpoint": "marcatarjeta.marcaTarjetaIndex", "icono": "fa-credit-card", "modulo": "Referenciales Facturación", "ventana": "marcatarjeta", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Entidad Emisora", "endpoint": "entidademisora.entidadEmisoraIndex", "icono": "fa-university", "modulo": "Referenciales Facturación", "ventana": "entidademisora", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Entidad Adherida", "endpoint": "entidadadherida.entidadAdheridaIndex", "icono": "fa-handshake", "modulo": "Referenciales Facturación", "ventana": "entidadadherida", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Cuenta Bancaria", "endpoint": "cuentabancaria.cuentaBancariaIndex", "icono": "fa-piggy-bank", "modulo": "Referenciales Facturación", "ventana": "cuentabancaria", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Tipo Ítems", "endpoint": "tipoitem.tipoItemIndex", "icono": "fa-tags", "modulo": "Referenciales Facturación", "ventana": "tipoitem", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Ítems", "endpoint": "item.itemIndex", "icono": "fa-boxes", "modulo": "Referenciales Facturación", "ventana": "item", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Caja", "endpoint": "caja.cajaIndex", "icono": "fa-cash-register", "modulo": "Referenciales Facturación", "ventana": "caja", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Depósito", "endpoint": "deposito.depositoIndex", "icono": "fa-warehouse", "modulo": "Referenciales Facturación", "ventana": "deposito", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Cliente", "endpoint": "cliente.clienteIndex", "icono": "fa-address-book", "modulo": "Referenciales Facturación", "ventana": "cliente", "acciones": ["ver", "nuevo", "editar", "anular"]},

    # Módulo Facturación (movimientos)
    {"etiqueta": "Apertura y Cierre de Caja", "endpoint": "aperturacaja.aperturaCajaIndex", "icono": "fa-cash-register", "modulo": "Módulo Facturación", "ventana": "aperturacaja", "acciones": ["ver", "nuevo", "anular", "estado"]},
    {"etiqueta": "Registrar Pedido Cliente", "endpoint": "pedidocliente.pedidoClienteIndex", "icono": "fa-clipboard-list", "modulo": "Módulo Facturación", "ventana": "pedidocliente", "acciones": ["ver", "nuevo", "anular"]},
    {"etiqueta": "Registrar Ventas", "endpoint": "venta.ventaIndex", "icono": "fa-file-invoice-dollar", "modulo": "Módulo Facturación", "ventana": "venta", "acciones": ["ver", "nuevo", "anular"]},
    {"etiqueta": "Registrar Cobranzas", "endpoint": "cobro.cobroIndex", "icono": "fa-hand-holding-usd", "modulo": "Módulo Facturación", "ventana": "cobro", "acciones": ["ver", "nuevo", "anular"]},
    {"etiqueta": "Registrar Nota de Remisión", "endpoint": "remision.remisionIndex", "icono": "fa-truck", "modulo": "Módulo Facturación", "ventana": "remision", "acciones": ["ver", "nuevo", "anular"]},
    {"etiqueta": "Notas de Crédito y Débito", "endpoint": "notacd.notaIndex", "icono": "fa-file-invoice", "modulo": "Módulo Facturación", "ventana": "notacd", "acciones": ["ver", "nuevo", "anular"]},
    {"etiqueta": "Arqueo de Caja", "endpoint": "arqueo.arqueoIndex", "icono": "fa-calculator", "modulo": "Módulo Facturación", "ventana": "arqueo", "acciones": ["ver", "nuevo", "anular", "estado"]},

    # Módulo Seguridad
    {"etiqueta": "Gestión de Usuarios", "endpoint": "usuario.usuarioIndex", "icono": "fa-users-cog", "modulo": "Módulo Seguridad", "ventana": "usuario", "acciones": ["ver", "nuevo", "editar", "anular", "desbloquear"]},
    {"etiqueta": "Tablero de Administrador", "endpoint": "auditoria.auditoriaIndex", "icono": "fa-shield-alt", "modulo": "Módulo Seguridad", "ventana": "auditoria", "acciones": ["ver"]},
    {"etiqueta": "Copias de Seguridad", "endpoint": "backup.backupIndex", "icono": "fa-database", "modulo": "Módulo Seguridad", "ventana": "backup", "acciones": ["ver", "nuevo"], "solo_admin": True},
]

# Ventanas que solo puede usar el Administrador, aunque alguien intentara otorgarles permisos
VENTANAS_SOLO_ADMIN = frozenset(item["ventana"] for item in CATALOGO_MENU if item.get("solo_admin"))


def agrupar_por_modulo_visible():
    """
    Agrupa CATALOGO_MENU por módulo (respetando el orden de MODULOS),
    filtrando a las ventanas donde el rol de la sesión actual tiene 'ver'.
    Usado por el context_processor para armar el sidebar dinámico.
    """
    from app.rutas.modulo_seguridad.permisos_contexto import puede

    visibles = [item for item in CATALOGO_MENU if item.get('en_menu', True) and puede(item['ventana'], 'ver')]
    por_modulo = {}
    for item in visibles:
        por_modulo.setdefault(item['modulo'], []).append(item)

    return [
        {**modulo, "entradas": por_modulo[modulo['modulo']]}
        for modulo in MODULOS
        if modulo['modulo'] in por_modulo
    ]
