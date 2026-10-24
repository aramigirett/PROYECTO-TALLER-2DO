"""
Crea (o actualiza) los usuarios de base de datos de la aplicación y del backup, y les fija la contraseña.

    python -m app.dao.modulo_seguridad.crear_usuario_app

Se conecta como postgres con TEST_DB_USER / TEST_DB_PASSWORD del .env (es una migración: la app NO puede hacerlo),
aplica schema_usuario_app.sql (idempotente) y fija las contraseñas por la conexión, nunca por línea de comandos:
  - la de odontoclinic_app se toma de la variable de entorno APP_DB_PASSWORD o, si no está, se pide por teclado;
  - la de odontoclinic_backup, de BACKUP_DB_PASSWORD o se pide por teclado.
Con --solo-permisos no toca contraseñas (sirve para re-aplicar los permisos después de crear tablas nuevas).
Después hay que poner DB_USER/DB_PASSWORD y BACKUP_DB_USER/BACKUP_DB_PASSWORD en el .env.
"""
import argparse
import getpass
import os
import pathlib
import sys

from psycopg2 import sql

from app.conexion.ConexionAdmin import ConexionAdmin

SCRIPT = pathlib.Path(__file__).with_name('schema_usuario_app.sql')


def obtener(variable, descripcion):
    valor = os.environ.get(variable)
    if not valor:
        valor = getpass.getpass(f'Contraseña para {descripcion}: ')
        if valor != getpass.getpass('Repetila: '):
            sys.exit('Las contraseñas no coinciden.')
    if len(valor) < 12:
        sys.exit(f'La contraseña de {descripcion} debe tener al menos 12 caracteres.')
    return valor


def main():
    parser = argparse.ArgumentParser(description='Crea los roles odontoclinic_app y odontoclinic_backup')
    parser.add_argument('--solo-permisos', action='store_true', help='re-aplica los permisos sin cambiar contraseñas')
    args = parser.parse_args()

    claves = {}
    if not args.solo_permisos:
        claves = {'odontoclinic_app': obtener('APP_DB_PASSWORD', 'odontoclinic_app (la aplicación)'),
                  'odontoclinic_backup': obtener('BACKUP_DB_PASSWORD', 'odontoclinic_backup (copias de seguridad)')}

    con = ConexionAdmin().getConexion()
    cur = con.cursor()
    try:
        cur.execute(SCRIPT.read_text(encoding='utf-8'))
        for rol, clave in claves.items():
            # La contraseña viaja como literal por la conexión; no aparece en ningún comando ni log
            cur.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(rol), sql.Literal(clave)))
        con.commit()
        print('Roles y permisos aplicados.' + ('' if args.solo_permisos else ' Contraseñas fijadas.'))
    except Exception:
        con.rollback()
        raise
    finally:
        cur.close()
        con.close()


if __name__ == '__main__':
    main()
