class ProductoDto:
    
    def __init__(self, id_producto, nombre, \
        cantidad, precio_unitario):
        self.__id_producto = id_producto
        self.__nombre = nombre
        self.__cantidad = cantidad
        self.__precio_unitario = precio_unitario

    #getters y setters de id_producto
    @property
    def id_producto(self):
        return self.__id_producto

    @id_producto.setter
    def id_producto(self, valor):
        if not valor:
            raise ValueError("El atributo id_producto no puede estar vacio")
        self.__id_producto = valor

    #getters y setters de nombre
    @property
    def nombre(self):
        return self.__nombre

    @nombre.setter
    def nombre(self, valor):
        if not valor:
            raise ValueError("El atributo nombre no puede estar vacio")
        self.__nombre = valor.upper()

    #getters y setters de cantidad
    @property
    def cantidad(self):
        return self.__cantidad

    @cantidad.setter
    def cantidad(self, valor):
        if not valor:
            raise ValueError("El atributo cantidad no puede estar vacio")
        self.__cantidad = valor

    #getters y setters de precio_unitario
    @property
    def precio_unitario(self):
        return self.__precio_unitario

    @precio_unitario.setter
    def precio_unitario(self, valor):
        if not valor:
            raise ValueError("El atributo precio_unitario no puede estar vacio")
        self.__precio_unitario = valor
