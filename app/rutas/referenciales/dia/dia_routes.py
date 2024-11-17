from flask import Blueprint, render_template

diamod = Blueprint('dia', __name__, template_folder='templates')

@diamod.route('/dia-index')
def diaIndex():
    return render_template('dia-index.html')