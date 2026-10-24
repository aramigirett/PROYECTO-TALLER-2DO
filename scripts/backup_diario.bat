@echo off
REM Copia de seguridad diaria de OdontoClinic. Se programa a las 23:00 en el Programador de tareas (docs\backups.md).
REM Usa el Python del entorno virtual del proyecto; el resultado queda en backup.log dentro de BACKUP_DIR.
cd /d "%~dp0.."
".venv\Scripts\python.exe" -I "scripts\backup_db.py"
exit /b %ERRORLEVEL%
