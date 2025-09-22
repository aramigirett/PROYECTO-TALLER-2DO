from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.paises.PaisDao import PaisDao

paisapi = Blueprint('paisapi', __name__)

# Trae todos los paises
@paisapi.route('/paises', methods=['GET'])
def getPaises():
    paisdao = PaisDao()

    try:
        paises = paisdao.getPaises()

        return jsonify({
            'success': True,
            'data': paises,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todas los paises: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@paisapi.route('/paises/<int:pais_id>', methods=['GET'])
def getPais(pais_id):
    paisdao = PaisDao()

    try:
        pais = paisdao.getPaisById(pais_id)

        if pais:
            return jsonify({
                'success': True,
                'data': pais,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el pais con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener pais: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega un nuevo pais
@paisapi.route('/paises', methods=['POST'])
def addPais():
    data = request.get_json()
    paisdao = PaisDao()

    campos_requeridos = ['descripcion']
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        descripcion = data['descripcion'].strip().upper()

        # Validar solo letras sin símbolos ni espacios
        if not descripcion.isalpha():
            return jsonify({
                'success': False,
                'error': 'Solo se permiten letras, sin símbolos ni espacios.'
            }), 400

        # Obtener todos los países existentes
        paises_existentes = paisdao.getPaises()
        for pais in paises_existentes:
            existente = pais['descripcion'].strip().upper()
            # Verifica si uno contiene al otro
            if descripcion in existente or existente in descripcion:
                return jsonify({
                    'success': False,
                    'error': f'El país "{descripcion}" es similar o derivado de "{existente}", ya registrado.'
                }), 409

        pais_id = paisdao.guardarPais(descripcion)
        if pais_id is not None:
            return jsonify({
                'success': True,
                'data': {'id': pais_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el país. Consulte con el administrador.'
            }), 500

    except Exception as e:
        app.logger.error(f"Error al agregar país: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


@paisapi.route('/paises/<int:pais_id>', methods=['PUT'])
def updatePais(pais_id):
    data = request.get_json()
    paisdao = PaisDao()

    campos_requeridos = ['descripcion']
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    descripcion = data['descripcion'].strip().upper()

    if not descripcion.isalpha():
        return jsonify({
            'success': False,
            'error': 'Solo se permiten letras, sin símbolos ni espacios.'
        }), 400

    try:
        paises_existentes = paisdao.getPaises()
        for pais in paises_existentes:
            existente = pais['descripcion'].strip().upper()
            if pais['id_pais'] != pais_id and (descripcion in existente or existente in descripcion):
                return jsonify({
                    'success': False,
                    'error': f'El país "{descripcion}" es similar o derivado de "{existente}", ya registrado.'
                }), 409

        if paisdao.updatePais(pais_id, descripcion):
            return jsonify({
                'success': True,
                'data': {'id': pais_id, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el pais con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar pais: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


@paisapi.route('/paises/<int:pais_id>', methods=['DELETE'])
def deletePais(pais_id):
    paisdao = PaisDao()

    try:
        if paisdao.deletePais(pais_id):
            return jsonify({
                'success': True,
                'mensaje': f'Pais con ID {pais_id} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el pais con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar pais: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500
