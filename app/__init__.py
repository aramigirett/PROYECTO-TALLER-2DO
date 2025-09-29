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
from app.rutas.referenciales.medico.medico_routes import medicomod
from app.rutas.referenciales.paciente.paciente_routes import pacientemod
from app.rutas.referenciales.agenda_medica.agenda_medica_routes import agendamedmod
from app.rutas.referenciales.persona.persona_routes import persona_mod
from app.rutas.referenciales.consultorio.consultorio_routes import consulmod
from app.rutas.referenciales.avisosRecordatorios.AvisosRecordatorios_routes import avisomod

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
app.register_blueprint(pacientemod, url_prefix=f'{modulo0}/paciente')
app.register_blueprint(medicomod, url_prefix=f'{modulo0}/medico')
app.register_blueprint(agendamedmod, url_prefix=f'{modulo0}/agenda_medica')
app.register_blueprint(persona_mod, url_prefix=f'{modulo0}/persona')
app.register_blueprint(consulmod, url_prefix=f'{modulo0}/consultorio')
app.register_blueprint(avisomod, url_prefix=f'{modulo0}/avisos')



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
#paciente
from app.rutas.referenciales.paciente.paciente_api import pacienteapi
#medico
from app.rutas.referenciales.medico.medico_api import medicoapi

from app.rutas.referenciales.agenda_medica.agenda_medica_api import agenda_medica_api

from app.rutas.referenciales.persona.persona_api import personaapi

from app.rutas.referenciales.consultorio.consultorio_api import consultorioapi

from app.rutas.referenciales.avisosRecordatorios.AvisosRecordatorios_api import avisoapi

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
#paciente
version1 = '/api/v1'
app.register_blueprint(pacienteapi, url_prefix=version1)
#medico
version1 = '/api/v1'
app.register_blueprint(medicoapi, url_prefix=version1)
version1 = '/api/v1'
app.register_blueprint(agenda_medica_api, url_prefix=version1)

app.register_blueprint(personaapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(consultorioapi, url_prefix=version1)

version1 = '/api/v1'
app.register_blueprint(avisoapi, url_prefix=version1)




@app.route('/login')
def login():
    return render_template('login-index.html')




@app.route('/vista')
def vista():
    return render_template('vista-index.html')
