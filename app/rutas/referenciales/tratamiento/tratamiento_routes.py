from flask import Blueprint, render_template, jsonify
from app.dao.referenciales.tratamiento.TratamientoDao import TratamientoDao

tratmod = Blueprint('tratamiento', __name__, template_folder='templates')

@tratmod.route('/tratamiento-index')
def tratamientoIndex():
    tradao = TratamientoDao()
    return render_template('tratamiento-index.html', lista_tratamientos=tradao.getTratamientos())
