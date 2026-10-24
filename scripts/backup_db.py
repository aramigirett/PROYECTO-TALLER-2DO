"""Genera una copia de seguridad de la base (pg_dump -Fc) en BACKUP_DIR, conserva las últimas 7 y registra el resultado en
backup.log. Lo ejecuta backup_diario.bat desde el Programador de tareas de Windows (ver docs/backups.md).

    python scripts/backup_db.py   (con el Python del entorno virtual)

Código de salida: 0 = OK, 1 = ERROR (el Programador de tareas lo muestra como "último resultado").
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.Services.backup_service import BackupError, formatear_tamano, generar_backup


def main():
    # Un acento que la consola no pueda mostrar no debe convertir un OK/ERROR en un traceback
    sys.stdout.reconfigure(errors='replace')
    try:
        r = generar_backup()
    except BackupError as e:
        print(f'ERROR: {e}')
        return 1
    print(f"OK: {r['archivo']} ({formatear_tamano(r['tamano'])})"
          + (f"; se borraron {len(r['borradas'])} copia(s) vieja(s)" if r['borradas'] else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
