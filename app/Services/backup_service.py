"""Copias de seguridad de la base de datos con pg_dump (formato custom).

Lo usan el script programado (scripts/backup_db.py, todas las noches desde el Programador de tareas de Windows) y la pantalla
"Copias de Seguridad" (botón "Generar backup ahora"). La restauración NO está acá a propósito: se hace a mano con pg_restore
siguiendo docs/backups.md.

Configuración (.env): BACKUP_DB_USER / BACKUP_DB_PASSWORD (rol de solo lectura odontoclinic_backup), BACKUP_DIR (carpeta
de destino; conviene FUERA de OneDrive, ver docs/backups.md), PG_BIN_DIR (carpeta bin de PostgreSQL, la de la versión del
servidor) y los DB_HOST / DB_PORT / DB_NAME de la aplicación.

La contraseña viaja SOLO en la variable de entorno PGPASSWORD del proceso hijo: no aparece en la línea de comandos, ni en el
log, ni en los mensajes de error (se la borra de lo que escribe pg_dump antes de guardarlo).
"""
import datetime
import locale
import os
import pathlib
import re
import shutil
import subprocess
import threading

from dotenv import load_dotenv

RAIZ = pathlib.Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / '.env')

RETENCION = 7                      # cantidad de copias que se conservan
TIMEOUT_SEGUNDOS = 1800
NOMBRE_LOG = 'backup.log'
_PATRON = re.compile(r'^(?P<base>[A-Za-z0-9_]+)_(?P<fecha>\d{8}_\d{6})\.dump$')
_candado = threading.Lock()        # una sola copia a la vez dentro del mismo proceso


class BackupError(Exception):
    """Error esperable al generar la copia (configuración, pg_dump). El mensaje es apto para mostrar."""


def directorio_backups():
    ruta = pathlib.Path(os.environ.get('BACKUP_DIR') or (RAIZ / 'backups'))
    return ruta if ruta.is_absolute() else RAIZ / ruta


def _requerida(nombre):
    valor = os.environ.get(nombre)
    if not valor:
        raise BackupError(f'Falta la variable {nombre} en el archivo .env.')
    return valor


def _ejecutable(nombre):
    carpeta = os.environ.get('PG_BIN_DIR')
    if carpeta:
        for candidato in (pathlib.Path(carpeta) / f'{nombre}.exe', pathlib.Path(carpeta) / nombre):
            if candidato.exists():
                return str(candidato)
        raise BackupError(f'No se encontró {nombre} en PG_BIN_DIR ({carpeta}).')
    encontrado = shutil.which(nombre)
    if not encontrado:
        raise BackupError(f'No se encontró {nombre}: configurá PG_BIN_DIR en el .env.')
    return encontrado


def _sin_secretos(texto, *secretos):
    for secreto in secretos:
        if secreto:
            texto = texto.replace(secreto, '***')
    return texto


def _registrar_log(carpeta, linea):
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        marca = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(carpeta / NOMBRE_LOG, 'a', encoding='utf-8') as f:
            f.write(f'{marca} {linea}\n')
    except OSError:
        pass   # no poder escribir el log no debe tapar el resultado de la copia


def listar_backups():
    """Copias existentes, la más reciente primero: [{nombre, tamano (bytes), fecha (datetime de modificación)}]."""
    carpeta = directorio_backups()
    if not carpeta.is_dir():
        return []
    copias = []
    for archivo in carpeta.iterdir():
        if archivo.is_file() and _PATRON.match(archivo.name):
            estado = archivo.stat()
            copias.append({'nombre': archivo.name, 'tamano': estado.st_size,
                           'fecha': datetime.datetime.fromtimestamp(estado.st_mtime)})
    copias.sort(key=lambda c: c['nombre'], reverse=True)   # el nombre lleva la fecha y hora
    return copias


def aplicar_retencion(carpeta=None, conservar=RETENCION):
    """Borra las copias más viejas y deja las últimas `conservar`. Devuelve los nombres borrados."""
    carpeta = carpeta or directorio_backups()
    borradas = []
    for copia in listar_backups()[conservar:]:
        try:
            (carpeta / copia['nombre']).unlink()
            borradas.append(copia['nombre'])
        except OSError:
            pass
    return borradas


def generar_backup():
    """
    Genera una copia con pg_dump -Fc. Devuelve {'archivo', 'tamano', 'borradas'}; si falla lanza BackupError.
    Cada ejecución (OK o ERROR) queda en backup.log dentro de la carpeta de copias.
    """
    carpeta = directorio_backups()
    clave = os.environ.get('BACKUP_DB_PASSWORD', '')
    with _candado:
        try:
            usuario = _requerida('BACKUP_DB_USER')
            clave = _requerida('BACKUP_DB_PASSWORD')
            base, host, puerto = _requerida('DB_NAME'), _requerida('DB_HOST'), _requerida('DB_PORT')
            pg_dump = _ejecutable('pg_dump')
            carpeta.mkdir(parents=True, exist_ok=True)

            nombre = f"{base}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.dump"
            destino, parcial = carpeta / nombre, carpeta / (nombre + '.parcial')
            comando = [pg_dump, '-Fc', '--no-password', '-h', host, '-p', puerto, '-U', usuario, '-d', base, '-f', str(parcial)]
            entorno = dict(os.environ, PGPASSWORD=clave)

            try:
                proceso = subprocess.run(comando, env=entorno, capture_output=True, text=True,
                                         encoding=locale.getpreferredencoding(False),   # pg_dump habla en la codificación de Windows
                                         errors='replace', timeout=TIMEOUT_SEGUNDOS)
            except subprocess.TimeoutExpired:
                parcial.unlink(missing_ok=True)
                raise BackupError('pg_dump superó el tiempo máximo y se canceló.')
            if proceso.returncode != 0:
                parcial.unlink(missing_ok=True)
                detalle = _sin_secretos((proceso.stderr or '').strip().splitlines()[-1] if proceso.stderr else '', clave)
                raise BackupError(f'pg_dump falló (código {proceso.returncode}): {detalle or "sin detalle"}')

            parcial.replace(destino)   # recién ahora aparece en el listado
            tamano = destino.stat().st_size
            borradas = aplicar_retencion(carpeta)
            _registrar_log(carpeta, f'OK archivo={nombre} tamano={tamano} bytes'
                                    + (f' retencion_borradas={len(borradas)}' if borradas else ''))
            return {'archivo': nombre, 'tamano': tamano, 'borradas': borradas}
        except BackupError as e:
            _registrar_log(carpeta, f'ERROR {_sin_secretos(str(e), clave)}')
            raise
        except Exception as e:   # error inesperado: se registra sin secretos y se informa como BackupError
            mensaje = _sin_secretos(f'{type(e).__name__}: {e}', clave)
            _registrar_log(carpeta, f'ERROR {mensaje}')
            raise BackupError(mensaje)


def formatear_tamano(bytes_):
    unidad, valor = 'B', float(bytes_)
    for unidad in ('B', 'KB', 'MB', 'GB'):
        if valor < 1024 or unidad == 'GB':
            break
        valor /= 1024
    return f'{valor:.0f} {unidad}' if unidad == 'B' else f'{valor:.1f} {unidad}'
