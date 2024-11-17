from flask import Blueprint, render_template

hiscmod = Blueprint('historiaclinica', __name__, template_folder='templates')

@hiscmod.route('/historiaclinica-index')
def historiaclinicaIndex():
    return render_template('historiaclinica-index.html')