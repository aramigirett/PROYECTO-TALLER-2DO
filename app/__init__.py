from flask import Flask
from flask import render_template

app = Flask(__name__)

# importar referenciales
from app.rutas.login.login_routes import loginmod
from app.rutas.login.vista_routes import vistamod
from app.rutas.referenciales.ciudad.ciudad_routes import ciumod #ciudad
from app.rutas.referenciales.paises.pais_routes import paimod   #pais
from app.rutas.referenciales.estado_cita.estado_cita_routes import estacitmod  #estado de la cita
from app.rutas.referenciales.especialidad.especialidad_routes import especimod  #especialidad
from app.rutas.referenciales.dia.dia_routes import diamod  #dia
from app.rutas.referenciales.turno.turno_routes import turmod  #turno
from app.rutas.referenciales.consultorio.consultorio_routes import consulmod
from app.rutas.referenciales.avisosRecordatorios.AvisosRecordatorios_routes import avisomod
from app.rutas.modulo_agendamiento.disponibilidad_horaria.disponibilidad_routes import disponibilidadmod
from app.rutas.referenciales.cargo.cargo_routes import cargomod #cargo


#Agendamiento nuevo
from app.rutas.modulo_agendamiento.medico.medico_routes import medicomod
from app.rutas.modulo_agendamiento.funcionario.funcionario_routes import funcionariomod
from app.rutas.modulo_agendamiento.agenda.agenda_routes import agenda_bp
from app.rutas.modulo_agendamiento.paciente.paciente_routes import pacientemod
from app.rutas.modulo_agendamiento.cita.cita_routes import citamod
from app.rutas.modulo_agendamiento.odontograma.odontograma_routes import odontogramamod


# registrar referenciales
modulo0 = '/referenciales'
app.register_blueprint(loginmod, url_prefix=f'{modulo0}/login') 
app.register_blueprint(vistamod, url_prefix=f'{modulo0}/vista') 
app.register_blueprint(ciumod, url_prefix=f'{modulo0}/ciudad') #ciudad
app.register_blueprint(paimod, url_prefix=f'{modulo0}/paises') #pais
app.register_blueprint(estacitmod, url_prefix=f'{modulo0}/estadocita')  #estado de la cita
app.register_blueprint(especimod, url_prefix=f'{modulo0}/especialidad') #especialidad
app.register_blueprint(diamod, url_prefix=f'{modulo0}/dia') #dia
app.register_blueprint(turmod, url_prefix=f'{modulo0}/turno') #turno
app.register_blueprint(consulmod, url_prefix=f'{modulo0}/consultorio')
app.register_blueprint(avisomod, url_prefix=f'{modulo0}/avisos')
app.register_blueprint(disponibilidadmod, url_prefix=f'{modulo0}/disponibilidad')
app.register_blueprint(cargomod, url_prefix=f'{modulo0}/cargo') #cargo


#Agendamiento nuevo
app.register_blueprint(medicomod, url_prefix=f'{modulo0}/medico')
app.register_blueprint(funcionariomod, url_prefix=f'{modulo0}/funcionario') #funcionario
app.register_blueprint(agenda_bp, url_prefix=f'{modulo0}/agenda')
app.register_blueprint(pacientemod, url_prefix=f'{modulo0}/paciente')
app.register_blueprint(citamod, url_prefix=f'{modulo0}/cita')
app.register_blueprint(odontogramamod, url_prefix=f'{modulo0}/odontograma')



#ciudad
from app.rutas.referenciales.ciudad.ciudad_api import ciuapi
#pais
from app.rutas.referenciales.paises.pais_api import paisapi
#estado de la cita
from app.rutas.referenciales.estado_cita.estado_cita_api import estacitapi
#especialidad
from app.rutas.referenciales.especialidad.especialidad_api import especiapi
#dia
from app.rutas.referenciales.dia.dia_api import diaapi
#turno
from app.rutas.referenciales.turno.turno_api import turnoapi

from app.rutas.referenciales.consultorio.consultorio_api import consultorioapi

from app.rutas.referenciales.avisosRecordatorios.AvisosRecordatorios_api import avisoapi

from app.rutas.modulo_agendamiento.disponibilidad_horaria.disponibilidad_api import disponibilidadapi

#cargo
from app.rutas.referenciales.cargo.cargo_api import cargoapi

#Agendamiento nuevo
from app.rutas.modulo_agendamiento.medico.medico_api import medicoapi
from app.rutas.modulo_agendamiento.funcionario.funcionario_api import funcionarioapi
from app.rutas.modulo_agendamiento.agenda.agenda_api import agendaapi
from app.rutas.modulo_agendamiento.paciente.paciente_api import pacienteapi
from app.rutas.modulo_agendamiento.cita.cita_api import citaapi
from app.rutas.modulo_agendamiento.odontograma.odontograma_api import odontogramaapi

# APIS v1
#Ciudad
version1 = '/api/v1'
app.register_blueprint(ciuapi, url_prefix=version1)
#Pais
version1 = '/api/v1'
app.register_blueprint(paisapi, url_prefix=version1)
#Estado de la cita
version1 = '/api/v1'
app.register_blueprint(estacitapi, url_prefix=version1)
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
app.register_blueprint(consultorioapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(avisoapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(disponibilidadapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(cargoapi, url_prefix=version1)

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

version1 = '/api/v1'
app.register_blueprint(odontogramaapi, url_prefix=version1)




@app.route('/login')
def login():
    return render_template('login-index.html')




@app.route('/vista')
def vista():
    return render_template('vista-index.html')
