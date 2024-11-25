from datetime import date
from flask import Blueprint, jsonify, request, current_app as app
from app.dao.gestionar_compras.registrar_pedido_compras.pedido_de_compras_dao \
    import PedidoDeComprasDao
from app.dao.gestionar_compras.registrar_pedido_compras.dto.pedido_de_compras_dto\
    import PedidoDeComprasDto, PedidoDeCompraDetalleDto, EstadoPedidoCompra
from app.dao.referenciales.sucursal.sucursal_dao import SucursalDao

pdcapi = Blueprint('pdcapi', __name__)

@pdcapi.route('/pedidos', methods=['GET'])
def get_pedidos():
    dao = PedidoDeComprasDao()

    try:
        pedidos = dao.obtener_pedidos()
        return jsonify({
            'success': True,
            'data': pedidos,
            'error': False
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener los pedidos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador'
        }), 500

@pdcapi.route('/pedidos', methods=['POST'])
def add():
    pdcdao = PedidoDeComprasDao()
    data = request.get_json()
    # Validar que el JSON no esté vacío y tenga las propiedades necesarias
    campos_requeridos = ['id_empleado', 'id_sucursal', 'id_deposito', 'fecha_pedido', 'detalle_pedido']
    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                        'success': False,
                        'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
                    }), 400
    try:
        id_empleado = data['id_empleado']
        id_sucursal = data['id_sucursal']
        id_deposito = data['id_deposito']
        fecha_pedido = data['fecha_pedido']
        detalle_pedido = data['detalle_pedido']

        detalle_dto = [PedidoDeCompraDetalleDto(
                        id_pedido_compra=None
                        , id_producto=item['id_producto']
                        , cantidad=item['cantidad']
                    )for item in detalle_pedido]

        cabecera_dto = PedidoDeComprasDto(
            id_pedido_compra=None
            , id_empleado=id_empleado
            , id_sucursal=id_sucursal
            , estado=EstadoPedidoCompra(id=2, descripcion=None) # Pendiente
            , fecha_pedido=date.fromisoformat(fecha_pedido)
            , id_deposito=id_deposito
            , detalle_pedido=detalle_dto
        )

        resultado = pdcdao.agregar(pedido_dto=cabecera_dto)
        if resultado:
            return jsonify({
                'success': True,
                'error': None
            }), 201
        else:
            return jsonify({ 'success': False, 'error': 'No se pudo crear el pedido. Consulte con el administrador.' }), 500
    except Exception as e:
        app.logger.error(f"Error al crear pedido: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Recuerdame, implementacion pobre versus implementacion millonario
@pdcapi.route('/sucursal-depositos/<int:id_sucursal>', methods=['GET'])
def get_sucursal_depositos(id_sucursal):
    dao = SucursalDao()

    try:
        pedidos = dao.get_sucursal_depositos(id_sucursal)
        return jsonify({
            'success': True,
            'data': pedidos,
            'error': False
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener los pedidos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador'
        }), 500