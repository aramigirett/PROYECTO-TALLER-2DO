import logging
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


def _mensaje_sin_secretos(texto, secretos):
    """El texto del error sin ninguna de las contraseñas (por si el servidor o el driver la repitieran)."""
    for secreto in secretos:
        if secreto:
            texto = texto.replace(secreto, '****')
    return texto


class Conexion:

    """Metodo constructor
    """
    def __init__(self):
        # https://www.psycopg.org/docs/extensions.html#psycopg2.extensions.parse_dsn
        password = _variable_requerida('DB_PASSWORD')
        try:
            self.con = psycopg2.connect(
                dbname=_variable_requerida('DB_NAME'),
                user=_variable_requerida('DB_USER'),
                password=password,
                host=_variable_requerida('DB_HOST'),
                port=int(_variable_requerida('DB_PORT')),
            )
        except UnicodeDecodeError as e:
            # PostgreSQL en Windows en español responde sus errores en cp1252 y psycopg2 los intenta leer como UTF-8:
            # en vez de ese UnicodeDecodeError, se registra y se levanta el error real, decodificado y sin contraseñas.
            crudo = e.object if isinstance(e.object, (bytes, bytearray)) else b''
            real = _mensaje_sin_secretos(bytes(crudo).decode('cp1252', errors='replace').strip(), (password,))
            logging.getLogger(__name__).error("No se pudo conectar a PostgreSQL: %s", real)
            raise psycopg2.OperationalError(real) from None

    """getConexion

        retorna la instancia de la base de datos
    """
    def getConexion(self):
        return self.con
