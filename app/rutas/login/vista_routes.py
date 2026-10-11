from flask import Blueprint, render_template
from app.dao.dashboard.DashboardDao import DashboardDao

vistamod = Blueprint('vista', __name__, template_folder='templates')


@vistamod.route('/vista-index')
def vistaIndex():
    dao = DashboardDao()
    datos = dao.obtener_datos_dashboard()
    return render_template('vista-index.html', **datos)