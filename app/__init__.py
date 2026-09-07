import os
from dotenv import load_dotenv
from flask import Flask
from flask import render_template

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-cambiar-en-produccion')

# importar referenciales
from app.rutas.login.vista_routes import vistamod
from app.rutas.modulo_seguridad.seguridad_routes import seguridadmod
from app.rutas.modulo_seguridad.usuario_routes import usuariomod
from app.rutas.modulo_seguridad.auditoria_routes import auditoriamod
from app.rutas.modulo_seguridad.permiso_routes import permisomod
from app.rutas.referenciales.ciudad.ciudad_routes import ciumod #ciudad
from app.rutas.referenciales.paises.pais_routes import paimod   #pais
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



# registrar referenciales
modulo0 = '/referenciales'
app.register_blueprint(vistamod, url_prefix=f'{modulo0}/vista')

# Módulo Seguridad (Login + 2FA) - sin prefijo: /login, /verificar-2fa, /logout
app.register_blueprint(seguridadmod)
app.register_blueprint(usuariomod, url_prefix=f'{modulo0}/usuario')
app.register_blueprint(auditoriamod, url_prefix=f'{modulo0}/auditoria')
app.register_blueprint(permisomod, url_prefix=f'{modulo0}/permiso')
app.register_blueprint(ciumod, url_prefix=f'{modulo0}/ciudad') #ciudad
app.register_blueprint(paimod, url_prefix=f'{modulo0}/paises') #pais
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


#ciudad
from app.rutas.referenciales.ciudad.ciudad_api import ciuapi
#pais
from app.rutas.referenciales.paises.pais_api import paisapi
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

#menu (Módulo Seguridad - buscador general)
from app.rutas.modulo_seguridad.menu_api import menuapi

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


# APIS v1
#Ciudad
version1 = '/api/v1'
app.register_blueprint(ciuapi, url_prefix=version1)
#Pais
version1 = '/api/v1'
app.register_blueprint(paisapi, url_prefix=version1)
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
app.register_blueprint(menuapi, url_prefix=version1)

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


##REGISTRAR CONSULTA Y FICHA MEDICA
# ============================================
# IMPORTS: MÓDULO CONSULTORIO
# ============================================

# Routes (Vistas HTML)
from app.rutas.modulo_consultorio.consulta.consulta_routes import consultamod

# APIs (Endpoints REST)
from app.rutas.modulo_consultorio.consulta.consulta_api import consultaapi
from app.rutas.modulo_consultorio.consulta.consulta_detalle_api import consultadetalleapi
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
app.register_blueprint(consultadetalleapi, url_prefix=version1)
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


@app.route('/vista')
def vista():
    return render_template('vista-index.html')



