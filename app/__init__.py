import os
from dotenv import load_dotenv
from flask import Flask
from flask import render_template

load_dotenv()

app = Flask(__name__)

# SECRET_KEY firma la cookie de sesión: sin ella cualquiera podría falsificarla. No hay valor por defecto en el
# código; solo en modo debug (FLASK_DEBUG, que run.py activa) se tolera su ausencia, con una clave efímera.
_clave = os.environ.get('SECRET_KEY')
if not _clave:
    if os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on'):
        import secrets
        _clave = secrets.token_hex(32)   # distinta en cada arranque: las sesiones no sobreviven a un reinicio
        print('AVISO: falta SECRET_KEY en .env; se usa una clave temporal (solo modo debug).')
    else:
        raise RuntimeError('Falta SECRET_KEY en el archivo .env. Generala con: '
                           'python -c "import secrets; print(secrets.token_hex(32))"')
app.secret_key = _clave

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '').lower() == 'true',  # true cuando se sirva por HTTPS
)

# importar referenciales
from app.rutas.login.vista_routes import vistamod
from app.rutas.modulo_seguridad.seguridad_routes import seguridadmod
from app.rutas.modulo_seguridad.usuario_routes import usuariomod
from app.rutas.modulo_seguridad.auditoria_routes import auditoriamod
from app.rutas.modulo_seguridad.permiso_routes import permisomod
from app.rutas.modulo_seguridad.backup_routes import backupmod
from app.rutas.modulo_seguridad.menu_routes import menumod
from app.rutas.modulo_seguridad.auditoria_cambios_routes import auditoriacambiosmod
from app.rutas.referenciales.ciudad.ciudad_routes import ciumod #ciudad
from app.rutas.referenciales.especialidad.especialidad_routes import especimod  #especialidad
from app.rutas.referenciales.dia.dia_routes import diamod  #dia
from app.rutas.referenciales.turno.turno_routes import turmod  #turno
from app.rutas.modulo_agendamiento.disponibilidad_horaria.disponibilidad_routes import disponibilidadmod
from app.rutas.referenciales.cargo.cargo_routes import cargomod #cargo


#Agendamiento nuevo
from app.rutas.modulo_agendamiento.medico.medico_routes import medicomod
from app.rutas.modulo_agendamiento.funcionario.funcionario_routes import funcionariomod
from app.rutas.modulo_agendamiento.agenda.agenda_routes import agenda_bp
from app.rutas.modulo_agendamiento.paciente.paciente_routes import pacientemod
from app.rutas.modulo_agendamiento.cita.cita_routes import citamod
from app.rutas.modulo_agendamiento.historial.historial_routes import historialmod
from app.rutas.modulo_agendamiento.avisosRecordatorios.avisos_routes import avisos_bp

#Consultorio TODOO
from app.rutas.modulo_agendamiento.consultorio.consultorio_routes import consulmod
from app.rutas.modulo_consultorio.tipo_diagnostico.tipo_diagnostico_routes import tipodiagnosticomod
from app.rutas.modulo_consultorio.sintoma.sintoma_routes import sintomod
from app.rutas.modulo_consultorio.odontograma.odontograma_routes import odontogramamod
from app.rutas.modulo_consultorio.tipo_tratamiento.tipo_tratamiento_routes import tipotratamientomod
from app.rutas.modulo_consultorio.tipo_insumo.tipo_insumo_routes import tipoinsumomod
from app.rutas.modulo_consultorio.tipo_procedimiento_medico.tipo_procedimiento_medico_routes import tipoprocedimientomedicomod
from app.rutas.modulo_consultorio.medicamento.medicamento_routes import medicamentomod
from app.rutas.modulo_consultorio.tipo_estudio.tipo_estudio_routes import tipoestudiomod
from app.rutas.modulo_consultorio.tipo_analisis.tipo_analisis_routes import tipoanalisismod
from app.rutas.modulo_consultorio.tratamiento.tratamiento_routes import tratamientomod
from app.rutas.modulo_consultorio.sesion_tratamiento.sesion_tratamiento_routes import sesiontratamientomod
from app.rutas.modulo_consultorio.receta.receta_routes import recetamod
from app.rutas.modulo_consultorio.orden_estudio.orden_estudio_routes import ordenestudiomod
from app.rutas.modulo_consultorio.orden_analisis.orden_analisis_routes import ordenanalisismod
from app.rutas.modulo_consultorio.justificativo_medico.justificativo_medico_routes import justificativomedicomod



# registrar referenciales
modulo0 = '/referenciales'
app.register_blueprint(vistamod, url_prefix=f'{modulo0}/vista')

# Módulo Seguridad (Login + 2FA) - sin prefijo: /login, /verificar-2fa, /logout
app.register_blueprint(seguridadmod)
app.register_blueprint(usuariomod, url_prefix=f'{modulo0}/usuario')
app.register_blueprint(auditoriamod, url_prefix=f'{modulo0}/auditoria')
app.register_blueprint(permisomod, url_prefix=f'{modulo0}/permiso')
app.register_blueprint(backupmod, url_prefix=f'{modulo0}/backup')
app.register_blueprint(menumod, url_prefix=f'{modulo0}/menu')
app.register_blueprint(auditoriacambiosmod, url_prefix=f'{modulo0}/auditoria-cambios')
app.register_blueprint(ciumod, url_prefix=f'{modulo0}/ciudad') #ciudad
app.register_blueprint(especimod, url_prefix=f'{modulo0}/especialidad') #especialidad
app.register_blueprint(diamod, url_prefix=f'{modulo0}/dia') #dia
app.register_blueprint(turmod, url_prefix=f'{modulo0}/turno') #turno
app.register_blueprint(disponibilidadmod, url_prefix=f'{modulo0}/disponibilidad')
app.register_blueprint(cargomod, url_prefix=f'{modulo0}/cargo') #cargo


#Agendamiento nuevo
app.register_blueprint(medicomod, url_prefix=f'{modulo0}/medico')
app.register_blueprint(funcionariomod, url_prefix=f'{modulo0}/funcionario') #funcionario
app.register_blueprint(agenda_bp, url_prefix=f'{modulo0}/agenda')
app.register_blueprint(pacientemod, url_prefix=f'{modulo0}/paciente')
app.register_blueprint(citamod, url_prefix=f'{modulo0}/cita')
app.register_blueprint(historialmod, url_prefix=f'{modulo0}/historial')
app.register_blueprint(avisos_bp, url_prefix=f'{modulo0}/avisos-recordatorios')
app.register_blueprint(consulmod, url_prefix=f'{modulo0}/consultorio')


#Cosnultorio TODOO
app.register_blueprint(tipodiagnosticomod, url_prefix=f'{modulo0}/tipo-diagnostico')
app.register_blueprint(sintomod, url_prefix=f'{modulo0}/sintoma')
app.register_blueprint(odontogramamod, url_prefix=f'{modulo0}/odontograma')
app.register_blueprint(tipotratamientomod, url_prefix=f'{modulo0}/tipo-tratamiento')
app.register_blueprint(tipoinsumomod, url_prefix=f'{modulo0}/tipo-insumo')
app.register_blueprint(tipoprocedimientomedicomod, url_prefix=f'{modulo0}/tipo-procedimiento-medico')
app.register_blueprint(medicamentomod, url_prefix=f'{modulo0}/medicamento')
app.register_blueprint(tipoestudiomod, url_prefix=f'{modulo0}/tipo-estudio')
app.register_blueprint(tipoanalisismod, url_prefix=f'{modulo0}/tipo-analisis')
app.register_blueprint(tratamientomod, url_prefix=f'{modulo0}/tratamiento')
app.register_blueprint(sesiontratamientomod, url_prefix=f'{modulo0}/sesion-tratamiento')
app.register_blueprint(recetamod, url_prefix=f'{modulo0}/receta')
app.register_blueprint(ordenestudiomod, url_prefix=f'{modulo0}/orden-estudio')
app.register_blueprint(ordenanalisismod, url_prefix=f'{modulo0}/orden-analisis')
app.register_blueprint(justificativomedicomod, url_prefix=f'{modulo0}/justificativo-medico')


#ciudad
from app.rutas.referenciales.ciudad.ciudad_api import ciuapi
#especialidad
from app.rutas.referenciales.especialidad.especialidad_api import especiapi
#dia
from app.rutas.referenciales.dia.dia_api import diaapi
#turno
from app.rutas.referenciales.turno.turno_api import turnoapi

from app.rutas.modulo_agendamiento.disponibilidad_horaria.disponibilidad_api import disponibilidadapi

#cargo
from app.rutas.referenciales.cargo.cargo_api import cargoapi

#usuario (Módulo Seguridad)
from app.rutas.modulo_seguridad.usuario_api import usuarioapi

#auditoria (Módulo Seguridad)
from app.rutas.modulo_seguridad.auditoria_api import auditoriaapi

#permiso (Módulo Seguridad)
from app.rutas.modulo_seguridad.permiso_api import permisoapi

#backup (Módulo Seguridad - copias de seguridad)
from app.rutas.modulo_seguridad.backup_api import backupapi
from app.rutas.modulo_seguridad.auditoria_cambios_api import auditoriacambiosapi

#menu (Módulo Seguridad - buscador general)
from app.rutas.modulo_seguridad.menu_api import menuapi
from app.rutas.modulo_seguridad.menu_abm_api import menuabmapi

#Agendamiento nuevo
from app.rutas.modulo_agendamiento.medico.medico_api import medicoapi
from app.rutas.modulo_agendamiento.funcionario.funcionario_api import funcionarioapi
from app.rutas.modulo_agendamiento.agenda.agenda_api import agendaapi
from app.rutas.modulo_agendamiento.paciente.paciente_api import pacienteapi
from app.rutas.modulo_agendamiento.cita.cita_api import citaapi
from app.rutas.modulo_agendamiento.historial.historial_api import historialapi
from app.rutas.modulo_agendamiento.avisosRecordatorios.avisos_api import avisoapi
from app.rutas.modulo_agendamiento.consultorio.consultorio_api import consultorioapi

#Consulrorio TODOOO
from app.rutas.modulo_consultorio.tipo_diagnostico.tipo_diagnostico_api import tipodiagnosticoapi
from app.rutas.modulo_consultorio.sintoma.sintoma_api import sintomaapi
from app.rutas.modulo_consultorio.odontograma.odontograma_api import odontogramaapi
from app.rutas.modulo_consultorio.tipo_tratamiento.tipo_tratamiento_api import tipotratamientoapi
from app.rutas.modulo_consultorio.tipo_insumo.tipo_insumo_api import tipoinsumoapi
from app.rutas.modulo_consultorio.tipo_procedimiento_medico.tipo_procedimiento_medico_api import tipoprocedimientomedicoapi
from app.rutas.modulo_consultorio.medicamento.medicamento_api import medicamentoapi
from app.rutas.modulo_consultorio.tipo_estudio.tipo_estudio_api import tipoestudioapi
from app.rutas.modulo_consultorio.tipo_analisis.tipo_analisis_api import tipoanalisisapi
from app.rutas.modulo_consultorio.tratamiento.tratamiento_api import tratamientoapi
from app.rutas.modulo_consultorio.sesion_tratamiento.sesion_tratamiento_api import sesiontratamientoapi
from app.rutas.modulo_consultorio.receta.receta_api import recetaapi
from app.rutas.modulo_consultorio.orden_estudio.orden_estudio_api import ordenestudioapi
from app.rutas.modulo_consultorio.orden_analisis.orden_analisis_api import ordenanalisisapi
from app.rutas.modulo_consultorio.justificativo_medico.justificativo_medico_api import justificativomedicoapi


# APIS v1
#Ciudad
version1 = '/api/v1'
app.register_blueprint(ciuapi, url_prefix=version1)
version1 = '/api/v1'
#especialidad
version1 = '/api/v1'
app.register_blueprint(especiapi, url_prefix=version1)
#dia
version1 = '/api/v1'
app.register_blueprint(diaapi, url_prefix=version1)
#turno
version1 = '/api/v1'
app.register_blueprint(turnoapi, url_prefix=version1)



version1 = '/api/v1'
app.register_blueprint(disponibilidadapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(cargoapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(usuarioapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(auditoriaapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(permisoapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(backupapi, url_prefix=version1)
app.register_blueprint(auditoriacambiosapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(menuapi, url_prefix=version1)
app.register_blueprint(menuabmapi, url_prefix=version1)

#Agendamiento nuevo
version1 = '/api/v1'
app.register_blueprint(medicoapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(funcionarioapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(agendaapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(pacienteapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(citaapi, url_prefix=version1)

app.register_blueprint(historialapi, url_prefix=version1)

app.register_blueprint(avisoapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(consultorioapi, url_prefix=version1)

#Consultorio TODOOO
version1 = '/api/v1'
app.register_blueprint(tipodiagnosticoapi, url_prefix=version1)
app.register_blueprint(sintomaapi, url_prefix=version1)
app.register_blueprint(odontogramaapi, url_prefix=version1)
app.register_blueprint(tipotratamientoapi, url_prefix=version1)
app.register_blueprint(tipoinsumoapi, url_prefix=version1)
app.register_blueprint(tipoprocedimientomedicoapi, url_prefix=version1)
app.register_blueprint(medicamentoapi, url_prefix=version1)
app.register_blueprint(tipoestudioapi, url_prefix=version1)
app.register_blueprint(tipoanalisisapi, url_prefix=version1)
app.register_blueprint(tratamientoapi, url_prefix=version1)
app.register_blueprint(sesiontratamientoapi, url_prefix=version1)
app.register_blueprint(recetaapi, url_prefix=version1)
app.register_blueprint(ordenestudioapi, url_prefix=version1)
app.register_blueprint(ordenanalisisapi, url_prefix=version1)
app.register_blueprint(justificativomedicoapi, url_prefix=version1)

# ============================================
# MÓDULO FACTURACIÓN - Referenciales
# ============================================
from app.rutas.modulo_facturacion.forma_cobro.forma_cobro_routes import formacobromod
from app.rutas.modulo_facturacion.forma_cobro.forma_cobro_api import formacobroapi
from app.rutas.modulo_facturacion.marca_tarjeta.marca_tarjeta_routes import marcatarjetamod
from app.rutas.modulo_facturacion.marca_tarjeta.marca_tarjeta_api import marcatarjetaapi
from app.rutas.modulo_facturacion.entidad_emisora.entidad_emisora_routes import entidademisoramod
from app.rutas.modulo_facturacion.entidad_emisora.entidad_emisora_api import entidademisoraapi
from app.rutas.modulo_facturacion.entidad_adherida.entidad_adherida_routes import entidadadheridamod
from app.rutas.modulo_facturacion.entidad_adherida.entidad_adherida_api import entidadadheridaapi
from app.rutas.modulo_facturacion.tipo_items.tipo_items_routes import tipoitemmod
from app.rutas.modulo_facturacion.tipo_items.tipo_items_api import tipoitemapi
from app.rutas.modulo_facturacion.items.items_routes import itemmod
from app.rutas.modulo_facturacion.items.items_api import itemapi
from app.rutas.modulo_facturacion.caja.caja_routes import cajamod
from app.rutas.modulo_facturacion.caja.caja_api import cajaapi
from app.rutas.modulo_facturacion.deposito.deposito_routes import depositomod
from app.rutas.modulo_facturacion.deposito.deposito_api import depositoapi
from app.rutas.modulo_facturacion.cliente.cliente_routes import clientemod
from app.rutas.modulo_facturacion.cliente.cliente_api import clienteapi
from app.rutas.modulo_facturacion.apertura_caja.apertura_caja_routes import aperturacajamod
from app.rutas.modulo_facturacion.apertura_caja.apertura_caja_api import aperturacajaapi
from app.rutas.modulo_facturacion.pedido_cliente.pedido_cliente_routes import pedidoclientemod
from app.rutas.modulo_facturacion.pedido_cliente.pedido_cliente_api import pedidoclienteapi
from app.rutas.modulo_facturacion.venta.venta_routes import ventamod
from app.rutas.modulo_facturacion.venta.venta_api import ventaapi
from app.rutas.modulo_facturacion.cobro.cobro_routes import cobromod
from app.rutas.modulo_facturacion.cobro.cobro_api import cobroapi
from app.rutas.modulo_facturacion.remision.remision_routes import remisionmod
from app.rutas.modulo_facturacion.remision.remision_api import remisionapi
from app.rutas.modulo_facturacion.nota_credito_debito.nota_routes import notacdmod
from app.rutas.modulo_facturacion.nota_credito_debito.nota_api import notacdapi
from app.rutas.modulo_facturacion.cuenta_bancaria.cuenta_bancaria_routes import cuentabancariamod
from app.rutas.modulo_facturacion.cuenta_bancaria.cuenta_bancaria_api import cuentabancariaapi
from app.rutas.modulo_facturacion.arqueo.arqueo_routes import arqueomod
from app.rutas.modulo_facturacion.arqueo.arqueo_api import arqueoapi

app.register_blueprint(formacobromod, url_prefix='/referenciales/forma-cobro')
app.register_blueprint(formacobroapi, url_prefix='/api/v1')
app.register_blueprint(marcatarjetamod, url_prefix='/referenciales/marca-tarjeta')
app.register_blueprint(marcatarjetaapi, url_prefix='/api/v1')
app.register_blueprint(entidademisoramod, url_prefix='/referenciales/entidad-emisora')
app.register_blueprint(entidademisoraapi, url_prefix='/api/v1')
app.register_blueprint(entidadadheridamod, url_prefix='/referenciales/entidad-adherida')
app.register_blueprint(entidadadheridaapi, url_prefix='/api/v1')
app.register_blueprint(tipoitemmod, url_prefix='/referenciales/tipo-item')
app.register_blueprint(tipoitemapi, url_prefix='/api/v1')
app.register_blueprint(itemmod, url_prefix='/referenciales/item')
app.register_blueprint(itemapi, url_prefix='/api/v1')
app.register_blueprint(cajamod, url_prefix='/referenciales/caja')
app.register_blueprint(cajaapi, url_prefix='/api/v1')
app.register_blueprint(depositomod, url_prefix='/referenciales/deposito')
app.register_blueprint(depositoapi, url_prefix='/api/v1')
app.register_blueprint(clientemod, url_prefix='/referenciales/cliente')
app.register_blueprint(clienteapi, url_prefix='/api/v1')
app.register_blueprint(aperturacajamod, url_prefix='/referenciales/apertura-caja')
app.register_blueprint(aperturacajaapi, url_prefix='/api/v1')
app.register_blueprint(pedidoclientemod, url_prefix='/referenciales/pedido-cliente')
app.register_blueprint(pedidoclienteapi, url_prefix='/api/v1')
app.register_blueprint(ventamod, url_prefix='/referenciales/venta')
app.register_blueprint(ventaapi, url_prefix='/api/v1')
app.register_blueprint(cobromod, url_prefix='/referenciales/cobro')
app.register_blueprint(cobroapi, url_prefix='/api/v1')
app.register_blueprint(remisionmod, url_prefix='/referenciales/remision')
app.register_blueprint(remisionapi, url_prefix='/api/v1')
app.register_blueprint(notacdmod, url_prefix='/referenciales/nota-credito-debito')
app.register_blueprint(notacdapi, url_prefix='/api/v1')
app.register_blueprint(cuentabancariamod, url_prefix='/referenciales/cuenta-bancaria')
app.register_blueprint(cuentabancariaapi, url_prefix='/api/v1')
app.register_blueprint(arqueomod, url_prefix='/referenciales/arqueo')
app.register_blueprint(arqueoapi, url_prefix='/api/v1')


##REGISTRAR CONSULTA Y FICHA MEDICA
# ============================================
# IMPORTS: MÓDULO CONSULTORIO
# ============================================

# Routes (Vistas HTML)
from app.rutas.modulo_consultorio.consulta.consulta_routes import consultamod

# APIs (Endpoints REST)
from app.rutas.modulo_consultorio.consulta.consulta_api import consultaapi
from app.rutas.modulo_consultorio.consulta.ficha_medica_api import fichamedicaapi
# ============================================
# MÓDULO CONSULTORIO - ROUTES
# ============================================
modulo0 = '/referenciales'
app.register_blueprint(consultamod, url_prefix=f'{modulo0}/consulta')
# ============================================
# MÓDULO CONSULTORIO - APIs
# ============================================
version1 = '/api/v1'
app.register_blueprint(consultaapi, url_prefix=version1)
app.register_blueprint(fichamedicaapi, url_prefix=version1)

# ============================================
# IMPORTAR ROUTES DE FICHA MÉDICA
# ============================================
from app.rutas.modulo_consultorio.consulta.ficha_medica_routes import fichamedicamod

# ============================================
# REGISTRAR BLUEPRINT
# ============================================
modulo0 = '/referenciales'
app.register_blueprint(fichamedicamod, url_prefix=f'{modulo0}/ficha-medica')

# ============================================
# IMPORTAR API DIAGNÓSTICO
# ============================================
from app.rutas.modulo_consultorio.diagnostico.diagnostico_api import diagnostico_medico_api
# ============================================
# REGISTRAR BLUEPRINT
# ============================================
version1 = '/api/v1'
app.register_blueprint(diagnostico_medico_api, url_prefix=version1)
# ============================================
# IMPORTAR ROUTES DE DIAGNÓSTICO
# ============================================
from app.rutas.modulo_consultorio.diagnostico.diagnostico_routes import diagnosticos_medicos_mod

app.register_blueprint(diagnosticos_medicos_mod, url_prefix=f'{modulo0}/diagnosticos-medicos')


# ============================================
# Accesibilidad (Roles y Permisos): puede() y el sidebar dinámico quedan
# disponibles en todos los templates sin pasarlos a mano en cada render_template.
# ============================================
from app.rutas.modulo_seguridad.permisos_contexto import puede
from app.rutas.modulo_seguridad.menu_servicio import menu_visible


@app.context_processor
def inject_permisos():
    return dict(puede=puede, menu_agrupado=menu_visible())


# ============================================
# Controles de sesión: validación de IP por país (login) y cierre por inactividad
# ============================================
from app.rutas.modulo_seguridad.sesion_seguridad import registrar_controles_de_sesion
registrar_controles_de_sesion(app)


# ============================================
# Páginas de error propias (403 / 404 / 500); JSON si la ruta es /api/
# ============================================
from app.rutas.errores import registrar_manejadores_de_error
registrar_manejadores_de_error(app)




