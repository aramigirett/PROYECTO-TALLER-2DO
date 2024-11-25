from flask import Blueprint, render_template
from app.dao.referenciales.sucursal.sucursal_dao import SucursalDao
from app.dao.referenciales.empleado.empleado_dao import EmpleadoDao
from app.dao.referenciales.producto.producto_dao import ProductoDao

pdcmod = Blueprint('pdcmod', __name__, template_folder='templates')

@pdcmod.route('/pedidos-index')
def pedidos_index():
    return render_template('pedidos-index.html')

@pdcmod.route('/pedidos-agregar')
def pedidos_agregar():
    sdao = SucursalDao()
    empdao = EmpleadoDao()
    pdao = ProductoDao()

    return render_template('pedidos-agregar.html'\
        , sucursales = sdao.get_sucursales()\
        , empleados = empdao.get_empleados()\
        , productos = pdao.get_productos())