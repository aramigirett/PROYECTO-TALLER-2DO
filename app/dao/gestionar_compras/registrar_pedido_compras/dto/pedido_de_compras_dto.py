from typing import List
from datetime import date
from app.dao.gestionar_compras.registrar_pedido_compras.dto.pedido_de_compra_detalle_dto \
    import PedidoDeCompraDetalleDto
from app.dao.referenciales.estado_pedido_compra.estado_pedido_compra_dto import EstadoPedidoCompra

class PedidoDeComprasDto:
    
    def __init__(self, id_pedido_compra: int, id_empleado: int, id_sucursal: int, \
        estado: EstadoPedidoCompra, fecha_pedido: date, id_deposito: int, detalle_pedido: List[PedidoDeCompraDetalleDto]):

        self.__id_pedido_compra = id_pedido_compra
        self.__id_empleado = id_empleado
        self.__id_sucursal = id_sucursal
        self.__estado = estado
        self.__fecha_pedido = fecha_pedido
        self.__id_deposito = id_deposito
        self.__detalle_pedido = detalle_pedido

    @property
    def id_pedido_compra(self) -> int:
        return self.__id_pedido_compra

    @id_pedido_compra.setter
    def id_pedido_compra(self, valor: int):
        self.__id_pedido_compra = valor

    @property
    def id_empleado(self) -> int:
        return self.__id_empleado

    @id_empleado.setter
    def id_empleado(self, valor: int):
        if not valor:
            raise ValueError("El atributo id_empleado no puede estar vacio")
        self.__id_empleado = valor

    @property
    def id_sucursal(self) -> int:
        return self.__id_sucursal

    @id_sucursal.setter
    def id_sucursal(self, valor: int):
        if not valor:
            raise ValueError("El atributo id_sucursal no puede estar vacio")
        self.__id_sucursal = valor

    @property
    def estado(self) -> EstadoPedidoCompra:
        return self.__estado

    @estado.setter
    def estado(self, valor: EstadoPedidoCompra):
        if not isinstance(valor, EstadoPedidoCompra):
            raise ValueError("El atributo estado debe ser de tipo 'EstadoPedidoCompra'")
        self.__estado = valor

    @property
    def fecha_pedido(self) -> date:
        return self.__fecha_pedido

    @fecha_pedido.setter
    def fecha_pedido(self, valor: date):
        if not isinstance(valor, date):
            raise ValueError("El atributo fecha_pedido debe ser de tipo 'date'")
        self.__fecha_pedido = valor

    @property
    def id_deposito(self) -> int:
        return self.__id_deposito

    @id_deposito.setter
    def id_deposito(self, valor: int):
        if not valor:
            raise ValueError("El atributo id_deposito no puede estar vacio")
        self.__id_deposito = valor

    @property
    def detalle_pedido(self) -> List[PedidoDeCompraDetalleDto]:
        return self.__detalle_pedido

    @detalle_pedido.setter
    def detalle_pedido(self, detalle_pedido: List[PedidoDeCompraDetalleDto]):
        if not isinstance(detalle_pedido, list):
            raise ValueError("detallePedido debe ser una lista de objetos PedidoDeCompraDetalleDto")

        # Verificar que todos los elementos en la lista sean del tipo correcto
        for item in detalle_pedido:
            if not isinstance(item, PedidoDeCompraDetalleDto):
                raise ValueError("Todos los elementos de detallePedido deben ser instancias de PedidoDeCompraDetalleDto")

        self.__detalle_pedido = detalle_pedido