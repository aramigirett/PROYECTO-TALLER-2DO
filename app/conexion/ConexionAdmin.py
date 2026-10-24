import os
import pathlib

import psycopg2
from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).resolve().parents[2] / '.env')


class ConexionAdmin:
    """Conexión PRIVILEGIADA (postgres) para migraciones, creación de roles y tests. La aplicación NO la usa: ella se
    conecta con odontoclinic_app (Conexion). Credenciales: TEST_DB_USER / TEST_DB_PASSWORD del .env; host, puerto y base
    toman TEST_DB_HOST / TEST_DB_PORT / TEST_DB_NAME y, si faltan, los DB_* de la aplicación."""

    def __init__(self, dbname=None):
        def requerida(nombre):
            valor = os.environ.get(nombre)
            if not valor:
                raise RuntimeError(f"Falta la variable {nombre} en el archivo .env (ver .env.example).")
            return valor

        self.con = psycopg2.connect(
            dbname=dbname or os.environ.get('TEST_DB_NAME') or requerida('DB_NAME'),
            user=requerida('TEST_DB_USER'),
            password=requerida('TEST_DB_PASSWORD'),
            host=os.environ.get('TEST_DB_HOST') or requerida('DB_HOST'),
            port=int(os.environ.get('TEST_DB_PORT') or requerida('DB_PORT')),
        )

    def getConexion(self):
        return self.con
