"""Esquema versionado de Agendamiento y Seguridad (etapa 1 de la migración a Tabler).

En una base TEMPORAL que crea y borra: aplica en orden schema_agendamiento_base.sql, schema_agendamiento_datos.sql,
schema_seguridad_base.sql, historial/schema_historial_base.sql y schema_agendamiento_etapa1.sql, y compara con la base real las 22 tablas
(columnas, tipos, NOT NULL, valores por defecto, restricciones y índices). También verifica que cada script se pueda volver a correr
(idempotente) y, en la base real, los cambios de la etapa 1 (activo, únicos parciales, FK en RESTRICT, Turno sin CHECK, Día con CHECK).
No modifica la base real.
"""
import os
import pathlib
import re
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import psycopg2
from dotenv import dotenv_values, load_dotenv
from tests._conexion_pruebas import Conexion

load_dotenv(RAIZ / '.env')
env = dotenv_values(RAIZ / '.env')
fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


TABLAS = ['ciudades', 'cargo', 'especialidades', 'consultorio', 'dias', 'turnos', 'estado_cita', 'paciente', 'medico', 'funcionario',
          'disponibilidad_horaria', 'agenda_cabecera', 'agenda_detalle', 'cita_cabecera', 'cita_detalle', 'avisos_recordatorios',
          'historial_medico_paciente', 'roles', 'menu', 'usuarios', 'token_2fa', 'permisos']
ORDEN = ['app/dao/referenciales_agendamiento/schema_agendamiento_base.sql', 'app/dao/referenciales_agendamiento/schema_agendamiento_datos.sql',
         'app/dao/modulo_seguridad/schema_seguridad_base.sql', 'app/dao/referenciales_agendamiento/historial/schema_historial_base.sql',
         'app/dao/referenciales_agendamiento/schema_agendamiento_etapa1.sql']

host, port, user, pwd, real = env['DB_HOST'], env['DB_PORT'], env['TEST_DB_USER'], env['TEST_DB_PASSWORD'], env['DB_NAME']
BIN = pathlib.Path(env.get('PG_BIN_DIR', r'C:\Program Files\PostgreSQL\14\bin'))
tmp = 'zz_esquema_agendamiento'
penv = {**os.environ, 'PGPASSWORD': pwd, 'PGCLIENTENCODING': 'UTF8'}


def conectar(db):
    cx = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=pwd)
    return cx


def _canonica(definicion):
    """Un CHECK `col IN ('A','B')` se escribe distinto según cómo se creó (ARRAY de varchar o de text): se compara por columna y valores."""
    if definicion.startswith('CHECK') and 'ARRAY[' in definicion:
        return 'CHECK IN ' + ','.join(sorted(re.findall(r"'([^']*)'::character varying", definicion))) + ' ' + re.search(r'\(\(?(\w+)\)?::text', definicion).group(1)
    return definicion


def foto(db):
    """Estructura de las 22 tablas: {sección: conjunto de líneas}."""
    cx = conectar(db); cu = cx.cursor()
    cu.execute("""SELECT table_name, column_name, data_type, character_maximum_length, is_nullable,
                         regexp_replace(COALESCE(column_default, ''), 'public\\.', '', 'g')
                  FROM information_schema.columns WHERE table_schema='public' AND table_name = ANY(%s)""", (TABLAS,))
    columnas = {tuple(map(str, r)) for r in cu.fetchall()}
    cu.execute("""SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) FROM pg_constraint
                  WHERE connamespace='public'::regnamespace AND conrelid::regclass::text = ANY(%s)""", (TABLAS,))
    restricciones = {(r[0], r[1], _canonica(r[2])) for r in cu.fetchall()}
    cu.execute("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname='public' AND tablename = ANY(%s)", (TABLAS,))
    indices = {tuple(r) for r in cu.fetchall()}
    cu.execute("""SELECT c.relname, a.attname FROM pg_class s JOIN pg_depend d ON d.objid = s.oid AND d.deptype='a'
                  JOIN pg_class c ON c.oid = d.refobjid JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = d.refobjsubid
                  WHERE s.relkind='S' AND c.relname = ANY(%s)""", (TABLAS,))
    secuencias = {tuple(r) for r in cu.fetchall()}
    cx.close()
    return {'columnas': columnas, 'restricciones': restricciones, 'índices': indices, 'secuencias': secuencias}


def psql(db, archivo):
    return subprocess.run([str(BIN / 'psql.exe'), '-h', host, '-p', port, '-U', user, '-d', db, '-q', '-v', 'ON_ERROR_STOP=1', '-f', str(RAIZ / archivo)],
                          env=penv, capture_output=True, text=True, encoding='utf-8', errors='replace')


# ---------- base temporal ----------
adm = conectar('postgres'); adm.autocommit = True; ac = adm.cursor()
ac.execute(f'DROP DATABASE IF EXISTS {tmp}'); ac.execute(f'CREATE DATABASE {tmp}')
try:
    for f in ORDEN:
        r = psql(tmp, f)
        chk(f'se aplica {pathlib.Path(f).name} en una base vacía', r.returncode == 0)
        if r.returncode:
            print(r.stderr[-600:])
    for f in ORDEN:
        r = psql(tmp, f)
        chk(f'{pathlib.Path(f).name} es idempotente (se vuelve a correr sin error)', r.returncode == 0)
        if r.returncode:
            print(r.stderr[-600:])
    A, B = foto(real), foto(tmp)
    for seccion in A:
        solo_real, solo_tmp = A[seccion] - B[seccion], B[seccion] - A[seccion]
        chk(f'{seccion}: la base reconstruida es idéntica a la real', not solo_real and not solo_tmp)
        for x in sorted(solo_real)[:3]:
            print('   solo en la REAL:', x)
        for x in sorted(solo_tmp)[:3]:
            print('   solo en la TEMPORAL:', x)
    cx = conectar(tmp); cu = cx.cursor()
    cu.execute("SELECT COUNT(*) FROM estado_cita"); chk('estado_cita: 6 estados fijos', cu.fetchone()[0] == 6)
    cu.execute("SELECT COUNT(*) FROM roles"); chk('roles: 4 roles', cu.fetchone()[0] == 4)
    cx.close()
finally:
    ac.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{tmp}'")
    ac.execute(f'DROP DATABASE IF EXISTS {tmp}')
    adm.close()

# ---------- base real: cambios de la etapa 1 ----------
cx = Conexion().getConexion(); cu = cx.cursor()


def q(sql, p=()):
    cu.execute(sql, p)
    return cu.fetchall()


for t in ('ciudades', 'cargo', 'especialidades', 'consultorio', 'dias', 'turnos', 'estado_cita', 'paciente', 'medico', 'funcionario', 'disponibilidad_horaria'):
    chk(f'{t}.activo BOOLEAN NOT NULL DEFAULT true',
        q("SELECT data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name=%s AND column_name='activo'", (t,)) == [('boolean', 'NO', 'true')])
for idx in ('ux_ciudades_descripcion_activo', 'ux_cargo_descripcion_activo', 'ux_especialidades_nombre_activo', 'ux_dias_descripcion_activo',
            'ux_turnos_descripcion_activo', 'ux_consultorio_nombre_activo', 'ux_consultorio_correo_activo', 'ux_disponibilidad_activo'):
    d = q("SELECT indexdef FROM pg_indexes WHERE indexname=%s", (idx,))
    chk(f'{idx}: único PARCIAL (WHERE activo = true)', bool(d) and 'UNIQUE' in d[0][0] and 'activo = true' in d[0][0])
chk('consultorio_correo_key (UNIQUE total) ya no existe', q("SELECT COUNT(*) FROM pg_constraint WHERE conname='consultorio_correo_key'")[0][0] == 0)
chk('uk_disponibilidad (UNIQUE total) ya no existe', q("SELECT COUNT(*) FROM pg_constraint WHERE conname='uk_disponibilidad'")[0][0] == 0)
chk('Turno sin CHECK; Día conserva el suyo', q("SELECT COUNT(*) FROM pg_constraint WHERE conname='chk_turnos'")[0][0] == 0
    and q("SELECT COUNT(*) FROM pg_constraint WHERE conname='chk_dias'")[0][0] == 1)
for tabla, nombre in (('cita_cabecera', 'cita_cabecera_id_paciente_fkey'), ('cita_cabecera', 'cita_cabecera_id_agenda_cabecera_fkey'),
                      ('historial_medico_paciente', 'fk_historial_paciente'), ('medico', 'medico_id_ciudad_fkey'), ('avisos_recordatorios', 'fk_medico')):
    chk(f'{nombre}: ON DELETE RESTRICT', q("SELECT confdeltype FROM pg_constraint WHERE conname=%s AND conrelid=%s::regclass", (nombre, tabla)) == [('r',)])
# solo quedan en cascada las dos relaciones cabecera -> detalle (un detalle no existe sin su cabecera; la app nunca borra una cabecera)
cascadas = q("""SELECT conrelid::regclass::text, confrelid::regclass::text FROM pg_constraint WHERE contype='f' AND confdeltype IN ('c','n')
                AND (conrelid::regclass::text = ANY(%s) OR confrelid::regclass::text = ANY(%s)) ORDER BY 1""", (TABLAS, TABLAS))
chk('las únicas FK en cascada de Agendamiento son agenda_detalle -> agenda_cabecera y cita_detalle -> cita_cabecera',
    cascadas == [('agenda_detalle', 'agenda_cabecera'), ('cita_detalle', 'cita_cabecera')])
print('FALLOS:', fallos or 'ninguno')
