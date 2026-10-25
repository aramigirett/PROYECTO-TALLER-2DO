# REGISTRO DE VENTANAS DEL CÓDIGO (semilla y acciones soportadas). Desde "Mantener Menú" la tabla `menu` es la fuente del sidebar, del buscador general
# y de la matriz de Roles y Permisos (módulo, descripción, ruta, ícono, orden, visibilidad, solo Administrador y baja lógica). Este archivo conserva solo lo
# que depende del código:
#   - `acciones`: qué acciones consultan los endpoints de cada ventana con @require_permiso (una ventana creada desde la pantalla, sin entrada acá, solo tiene 'ver');
#   - la semilla con la que `schema_menu_mantener.sql` pobló la tabla (el test de menú comprueba que tabla y registro no se contradigan).
#
# Cada entrada:
#   etiqueta   -> texto visible (la tabla `menu` puede cambiarlo)
#   endpoint   -> endpoint de Flask (se guarda en `menu.ruta`)
#   icono      -> clase FontAwesome
#   modulo     -> agrupador (debe existir en MODULOS)
#   ventana    -> clave estable de la ventana (`menu.clave`; los @require_permiso la usan y no se puede cambiar)
#   en_menu    -> (opcional, default True) False = pantalla contextual: sin sidebar ni buscador, pero con fila en la matriz (`menu.visible_en_menu`)
#   solo_admin -> (opcional) True = ventana exclusiva del Administrador: no sale en la matriz de Roles y Permisos y puede() devuelve False para cualquier otro rol
#   acciones   -> subconjunto de ('ver','nuevo','editar','anular','estado','desbloquear'). 'ver' siempre debe estar.
#
# NOTA: acción 'desbloquear' = levantar el bloqueo de una cuenta (solo la ventana 'usuario'). Acción 'estado' = cambios de estado del flujo (cita, avisos,
# órdenes, consulta...); 'anular' incluye anular y reactivar. Agenda, Cita, Avisos e Historial no exponen 'editar': su edición de datos queda solo para
# el Administrador.
#
# VENTANAS PROTEGIDAS (columna `menu.protegida`, con trigger en la base): Mantener Menú, Gestión de Usuarios, Roles y Permisos y su módulo no se pueden
# anular, mover ni dejar de ser exclusivas del Administrador, para que nadie quede sin acceso a la administración.

MODULOS = [
    {"modulo": "Agendamiento", "icono": "fa-calendar-check"},
    {"modulo": "Referenciales Agendamiento", "icono": "fa-file-alt"},
    {"modulo": "Referenciales Consultorio", "icono": "fa-file-alt"},
    {"modulo": "Módulo Consultorio", "icono": "fa-file-medical"},
    {"modulo": "Referenciales Facturación", "icono": "fa-file-invoice-dollar"},
    {"modulo": "Módulo Facturación", "icono": "fa-cash-register"},
    {"modulo": "Módulo Seguridad", "icono": "fa-user-shield"},
    {"modulo": "Informes", "icono": "fa-chart-line"},
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
    {"etiqueta": "Gestión Fichas Médicas", "endpoint": "fichamedica.fichaMedicaIndex", "icono": "fa-file-medical-alt", "modulo": "Módulo Consultorio", "ventana": "fichamedica", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Gestión Diagnósticos", "endpoint": "diagnostico_medico.diagnosticoIndex", "icono": "fa-diagnoses", "modulo": "Módulo Consultorio", "ventana": "diagnostico", "acciones": ["ver", "nuevo", "anular"]},
    {"etiqueta": "Historial Médico", "endpoint": "historial.historialIndex", "icono": "fa-history", "modulo": "Módulo Consultorio", "ventana": "historial", "acciones": ["ver", "nuevo", "anular"]},
    {"etiqueta": "Registrar Odontograma", "endpoint": "odontograma.odontogramaIndex", "icono": "fa-teeth", "modulo": "Módulo Consultorio", "ventana": "odontograma", "acciones": ["ver", "nuevo", "editar", "anular"]},
    {"etiqueta": "Gestionar Tratamientos", "endpoint": "tratamiento.tratamientoIndex", "icono": "fa-prescription-bottle-alt", "modulo": "Módulo Consultorio", "ventana": "tratamiento", "acciones": ["ver", "nuevo", "anular", "estado"]},
    {"etiqueta": "Generar Recetas e Indicaciones", "endpoint": "receta.recetaIndex", "icono": "fa-prescription", "modulo": "Módulo Consultorio", "ventana": "receta", "acciones": ["ver", "nuevo", "anular"]},
    # Sin entrada en el sidebar ni en el buscador (en_menu False): se llega siempre desde
    # Gestionar Tratamientos. Está en el catálogo para tener su fila en la matriz de permisos.
    {"etiqueta": "Procedimientos e Insumos (Sesiones)", "endpoint": "sesiontratamiento.sesionTratamientoIndex", "icono": "fa-notes-medical", "modulo": "Módulo Consultorio", "ventana": "sesiontratamiento", "acciones": ["ver", "nuevo", "anular"], "en_menu": False},
    {"etiqueta": "Generar Orden de Estudios", "endpoint": "ordenestudio.ordenEstudioIndex", "icono": "fa-vial", "modulo": "Módulo Consultorio", "ventana": "ordenestudio", "acciones": ["ver", "nuevo", "anular", "estado"]},
    {"etiqueta": "Generar Orden de Análisis", "endpoint": "ordenanalisis.ordenAnalisisIndex", "icono": "fa-flask", "modulo": "Módulo Consultorio", "ventana": "ordenanalisis", "acciones": ["ver", "nuevo", "anular", "estado"]},
    {"etiqueta": "Generar Justificativo Médico", "endpoint": "justificativomedico.justificativoMedicoIndex", "icono": "fa-file-signature", "modulo": "Módulo Consultorio", "ventana": "justificativomedico", "acciones": ["ver", "nuevo", "anular", "estado"]},

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
    {"etiqueta": "Gestión de Usuarios", "endpoint": "usuario.usuarioIndex", "icono": "fa-users-cog", "modulo": "Módulo Seguridad", "ventana": "usuario", "acciones": ["ver", "nuevo", "editar", "anular", "desbloquear"], "solo_admin": True},
    {"etiqueta": "Roles y Permisos", "endpoint": "permiso.permisoIndex", "icono": "fa-key", "modulo": "Módulo Seguridad", "ventana": "permiso", "acciones": ["ver"], "solo_admin": True},
    {"etiqueta": "Mantener Menú", "endpoint": "menu.menuIndex", "icono": "fa-bars", "modulo": "Módulo Seguridad", "ventana": "menu", "acciones": ["ver", "nuevo", "editar", "anular"], "solo_admin": True},
    {"etiqueta": "Tablero de Administrador", "endpoint": "auditoria.auditoriaIndex", "icono": "fa-shield-alt", "modulo": "Módulo Seguridad", "ventana": "auditoria", "acciones": ["ver"], "solo_admin": True},
    {"etiqueta": "Auditoría de Cambios", "endpoint": "auditoriacambios.auditoriaCambiosIndex", "icono": "fa-history", "modulo": "Módulo Seguridad", "ventana": "auditoriacambios", "acciones": ["ver"], "solo_admin": True},
    {"etiqueta": "Copias de Seguridad", "endpoint": "backup.backupIndex", "icono": "fa-database", "modulo": "Módulo Seguridad", "ventana": "backup", "acciones": ["ver", "nuevo"], "solo_admin": True},

    # Informes (una sola pantalla de consulta; la exportación a PDF / Excel también exige solo ser Administrador)
    {"etiqueta": "Informes", "endpoint": "informes.informesIndex", "icono": "fa-chart-line", "modulo": "Informes", "ventana": "informes", "acciones": ["ver"], "solo_admin": True},
]

# Ventanas de la semilla que solo puede usar el Administrador (la fuente en ejecución es `menu.solo_admin`, ver menu_servicio.ventanas_solo_admin())
VENTANAS_SOLO_ADMIN = frozenset(item["ventana"] for item in CATALOGO_MENU if item.get("solo_admin"))
