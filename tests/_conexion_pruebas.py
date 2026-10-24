"""Conexión de los tests para preparar y limpiar datos con privilegios (postgres, TEST_DB_USER/TEST_DB_PASSWORD).

Cada test hace `from tests._conexion_pruebas import Conexion` en lugar de importar la de la aplicación: lo que el test haga
DIRECTO en la base (datos ZZ, limpiar la auditoría, bases temporales) usa esta conexión, mientras que la app y los DAO que
el test ejercita siguen usando odontoclinic_app. Así la regresión prueba los permisos reales de la aplicación.
"""
from app.conexion.ConexionAdmin import ConexionAdmin as Conexion

__all__ = ['Conexion']
