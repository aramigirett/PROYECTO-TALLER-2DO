import psycopg2
class Conexion:

    """Metodo constructor
    """
    def __init__(self):
        # https://www.psycopg.org/docs/extensions.html#psycopg2.extensions.parse_dsn
        dbname = "dbtaller"
        user = "postgres"
        password = "15dediciembre"
        host = "127.0.0.1"
        port = 5432
        #self.con = psycopg2.connect("dbname=dbtaller user=Postgres host=localhost password=15dediciembre")
        self.con = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)

    """getConexion

        retorna la instancia de la base de datos
    """
    def getConexion(self):
        return self.con