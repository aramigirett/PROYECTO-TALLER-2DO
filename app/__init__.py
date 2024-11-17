from flask import Flask
from flask import render_template

app = Flask(__name__)

# importar referenciales
from app.rutas.login.login_routes import loginmod
from app.rutas.login.vista_routes import vistamod
from app.rutas.referenciales.ciudad.ciudad_routes import ciumod #ciudad
from app.rutas.referenciales.paises.pais_routes import paimod   #pais
from app.rutas.referenciales.nacionalidad.nacionalidad_routes import naciomod  #nacionalidad
from app.rutas.referenciales.ocupacion.ocupacion_routes import ocupmod  #ocupacion
from app.rutas.referenciales.estado_civil.estado_civil_routes import estacivmod  #estado civil
from app.rutas.referenciales.sexo.sexo_routes import sexmod  #sexo
from app.rutas.referenciales.estado_cita.estado_cita_routes import estacitmod  #estado de la cita
from app.rutas.referenciales.persona.persona_routes import persmod  #persona
from app.rutas.referenciales.especialidad.especialidad_routes import especimod  #especialidad
from app.rutas.referenciales.dia.dia_routes import diamod  #dia
from app.rutas.referenciales.diagnostico.diagnostico_routes import diagmod  # diagnostico
from app.rutas.referenciales.duracion_consulta.duracion_consulta_routes import duraconsumod  #duracion de la consulta
from app.rutas.referenciales.instrumento.instrumento_routes import instmod  #instrumento utilizado
from app.rutas.referenciales.turno.turno_routes import turmod  #turno
from app.rutas.referenciales.historia_clinica.historiaclinica_routes import hiscmod

# registrar referenciales
modulo0 = '/referenciales'
app.register_blueprint(loginmod, url_prefix=f'{modulo0}/login') 
app.register_blueprint(vistamod, url_prefix=f'{modulo0}/vista') 
app.register_blueprint(ciumod, url_prefix=f'{modulo0}/ciudad') #ciudad
app.register_blueprint(paimod, url_prefix=f'{modulo0}/paises') #pais
app.register_blueprint(naciomod, url_prefix=f'{modulo0}/nacionalidad')  #nacionalidad
app.register_blueprint(ocupmod, url_prefix=f'{modulo0}/ocupacion')  #ocupacion
app.register_blueprint(estacivmod, url_prefix=f'{modulo0}/estadocivil')  #estado civil
app.register_blueprint(sexmod, url_prefix=f'{modulo0}/sexo')  #sexo
app.register_blueprint(estacitmod, url_prefix=f'{modulo0}/estadocita')  #estado de la cita
app.register_blueprint(persmod, url_prefix=f'{modulo0}/persona') #persona
app.register_blueprint(especimod, url_prefix=f'{modulo0}/especialidad') #especialidad
app.register_blueprint(diamod, url_prefix=f'{modulo0}/dia') #dia
app.register_blueprint(diagmod, url_prefix=f'{modulo0}/diagnostico')  # diagnostico
app.register_blueprint(duraconsumod, url_prefix=f'{modulo0}/duracionconsulta') #duracion de la consulta
app.register_blueprint(instmod, url_prefix=f'{modulo0}/instrumento') #instrumento utilizado
app.register_blueprint(turmod, url_prefix=f'{modulo0}/turno') #turno
app.register_blueprint(hiscmod, url_prefix=f'{modulo0}/historiaclinica') #historia clinica

#ciudad
from app.rutas.referenciales.ciudad.ciudad_api import ciuapi

#pais
from app.rutas.referenciales.paises.pais_api import paisapi

#nacionalidad
from app.rutas.referenciales.nacionalidad.nacionalidad_api import nacioapi

#nacionalidad
from app.rutas.referenciales.ocupacion.ocupacion_api import ocupapi

#estado civil
from app.rutas.referenciales.estado_civil.estado_civil_api import estacivapi

#sexo
from app.rutas.referenciales.sexo.sexo_api import sexapi

#estado de la cita
from app.rutas.referenciales.estado_cita.estado_cita_api import estacitapi

#persona
from app.rutas.referenciales.persona.persona_api import persapi

#especialidad
from app.rutas.referenciales.especialidad.especialidad_api import especiapi

#dia
from app.rutas.referenciales.dia.dia_api import diaapi

#diagnostico
from app.rutas.referenciales.diagnostico.diagnostico_api import diagapi

#duracion consulta
from app.rutas.referenciales.duracion_consulta.duracion_consulta_api import duraconsuapi

#instrumento utilizado
from app.rutas.referenciales.instrumento.instrumento_api import instapi

#turno
from app.rutas.referenciales.turno.turno_api import turnoapi

#historia clinica
from app.rutas.referenciales.historia_clinica.historiaclinica_api import histocliapi

# APIS v1
#Ciudad
version1 = '/api/v1'
app.register_blueprint(ciuapi, url_prefix=version1)

#Pais
version1 = '/api/v1'
app.register_blueprint(paisapi, url_prefix=version1)

#nacionalidad
version1 = '/api/v1'
app.register_blueprint(nacioapi, url_prefix=version1)

#ocupacion
version1 = '/api/v1'
app.register_blueprint(ocupapi, url_prefix=version1)

#Estado civil
version1 = '/api/v1'
app.register_blueprint(estacivapi, url_prefix=version1)

#sexo
version1 = '/api/v1'
app.register_blueprint(sexapi, url_prefix=version1)

#Estado de la cita
version1 = '/api/v1'
app.register_blueprint(estacitapi, url_prefix=version1)

#persona
version1 = '/api/v1'
app.register_blueprint(persapi, url_prefix=version1)

#especialidad
version1 = '/api/v1'
app.register_blueprint(especiapi, url_prefix=version1)

#dia
version1 = '/api/v1'
app.register_blueprint(diaapi, url_prefix=version1)

#diagnostico
version1 = '/api/v1'
app.register_blueprint(diagapi, url_prefix=version1)  

#duracion consulta
version1 = '/api/v1'
app.register_blueprint(duraconsuapi, url_prefix=version1)

#instrumento utilizado
version1 = '/api/v1'
app.register_blueprint(instapi, url_prefix=version1)

#turno
version1 = '/api/v1'
app.register_blueprint(turnoapi, url_prefix=version1)

#Historia Clinica
version1 = '/api/v1'
app.register_blueprint(histocliapi, url_prefix=version1)




@app.route('/login')
def login():
    return render_template('login-index.html')




@app.route('/vista')
def vista():
    return render_template('vista-index.html')
