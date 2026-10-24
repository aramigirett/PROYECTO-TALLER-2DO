import os
import pathlib

import psycopg2
from dotenv import load_dotenv

# Las credenciales viven en .env (raíz del proyecto), nunca en el código.
load_dotenv(pathlib.Path(__file__).resolve().parents[2] / '.env')


def _variable_requerida(nombre):
    valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(
            f"Falta la variable {nombre} en el archivo .env (ver .env.example)."
        )
    return valor


class Conexion:

    """Metodo constructor
    """
    def __init__(self):
        # https://www.psycopg.org/docs/extensions.html#psycopg2.extensions.parse_dsn
        self.con = psycopg2.connect(
            dbname=_variable_requerida('DB_NAME'),
            user=_variable_requerida('DB_USER'),
            password=_variable_requerida('DB_PASSWORD'),
            host=_variable_requerida('DB_HOST'),
            port=int(_variable_requerida('DB_PORT')),
        )

    """getConexion

        retorna la instancia de la base de datos
    """
    def getConexion(self):
        return self.con
