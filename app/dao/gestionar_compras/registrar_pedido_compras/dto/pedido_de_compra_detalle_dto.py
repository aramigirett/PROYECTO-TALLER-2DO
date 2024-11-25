class PedidoDeCompraDetalleDto:
    
    def __init__(self, id_pedido_compra: int, id_producto: int, cantidad: int):
        self.__id_pedido_compra = id_pedido_compra
        self.__id_producto = id_producto
        self.__cantidad = cantidad

    #getters y setters de id_pedido_compra
    @property
    def id_pedido_compra(self) -> int:
        return self.__id_pedido_compra

    @id_pedido_compra.setter
    def id_pedido_compra(self, valor: int):
        if not isinstance(valor, int) or valor <= 0:
            raise ValueError("El atributo id_pedido_compra debe ser un entero positivo")
        self.__id_pedido_compra = valor

    #getters y setters de id_producto
    @property
    def id_producto(self) -> int:
        return self.__id_producto

    @id_producto.setter
    def id_producto(self, valor: int):
        if not isinstance(valor, int) or valor <= 0:
            raise ValueError("El atributo id_producto debe ser un entero positivo")
        self.__id_producto = valor

    #getters y setters de cantidad
    @property
    def cantidad(self) -> int:
        return self.__cantidad

    @cantidad.setter
    def cantidad(self, valor: int):
        if not isinstance(valor, int) or valor <= 0:
            raise ValueError("El atributo cantidad debe ser un entero positivo")
        self.__cantidad = valor