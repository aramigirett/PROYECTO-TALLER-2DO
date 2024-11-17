from flask import Blueprint, render_template, jsonify
from app.dao.referenciales.instrumento.InstrumentoDao import InstrumentoDao

instmod = Blueprint('instrumento', __name__, template_folder='templates')

@instmod.route('/instrumento-index')
def instrumentoIndex():
    instdao = InstrumentoDao()
    return render_template('instrumento-index.html')