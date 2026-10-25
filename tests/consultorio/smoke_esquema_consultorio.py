"""Etapa 0 de la migración de Consultorio a Tabler: esquema versionado.

Cubre: `consultas_detalle` eliminada (y sin referencias en app/), `odontograma.activo` con su único parcial, los únicos de los
referenciales con UPPER, el mapa de auditoría de las 18 entidades y, en una base TEMPORAL que crea y borra, que
schema_consultorio_base.sql reconstruye las 23 tablas idénticas a la real (columnas, constraints, índices, trigger) y es idempotente.
No modifica ninguna fila de la base real.
"""
import os
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from dotenv import load_dotenv
from tests._conexion_pruebas import Conexion

load_dotenv(RAIZ / '.env')
fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


DAO = RAIZ / 'app' / 'dao' / 'referenciales_consultorio'
TABLAS = ['tipo_diagnostico', 'sintoma', 'tipos_tratamiento', 'insumos', 'tipo_procedimiento_medico', 'medicamentos', 'tipo_analisis',
          'tipo_estudio', 'estado_dental', 'consultas_cab', 'ficha_medica_consulta', 'diagnosticos', 'diagnostico_sintoma', 'odontograma',
          'odontograma_detalle', 'tratamientos', 'sesiones_tratamiento', 'sesion_insumos', 'recetas', 'receta_medicamento',
          'orden_estudios', 'orden_analisis', 'justificativo_medico']
cx = Conexion().getConexion(); cu = cx.cursor()


def q(sql, p=()):
    cu.execute(sql, p)
    return cu.fetchall()


# ---------- base real ----------
chk('consultas_detalle ya no existe', q("SELECT to_regclass('public.consultas_detalle')")[0][0] is None)
usos = [str(f.relative_to(RAIZ)) for f in (RAIZ / 'app').rglob('*')
        if f.is_file() and f.suffix in ('.py', '.html', '.js') and 'vendor' not in f.parts and 'consultas_detalle' in f.read_text(encoding='utf-8', errors='ignore')]
chk('ningún archivo de app/ referencia consultas_detalle', usos == [])
chk('odontograma.activo BOOLEAN NOT NULL DEFAULT true',
    q("SELECT data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name='odontograma' AND column_name='activo'")
    == [('boolean', 'NO', 'true')])
chk('único parcial ux_odontograma_consulta_activo (id_consulta_cab) WHERE activo',
    'WHERE (activo = true)' in q("SELECT indexdef FROM pg_indexes WHERE indexname='ux_odontograma_consulta_activo'")[0][0])
chk('ningún odontograma inactivo con activo = true', q("SELECT count(*) FROM odontograma WHERE estado='Inactivo' AND activo")[0][0] == 0)
for idx in ('uk_tipo_trat_descripcion', 'uk_insumos_descripcion', 'uk_tipo_proc_descripcion', 'uk_medicamento_nombre_comercial',
            'uk_tipo_analisis_descripcion', 'uk_tipo_estudio_descripcion'):
    d = q("SELECT indexdef FROM pg_indexes WHERE indexname=%s", (idx,))
    chk(f'{idx}: UNIQUE sobre UPPER(...) WHERE activo', bool(d) and 'upper(' in d[0][0].lower() and 'WHERE (activo = true)' in d[0][0])

# ---------- mapa de auditoría ----------
from app.Services.auditoria_detalle import ENTIDADES_MOVIMIENTO, MODULO_POR_ENTIDAD, ETIQUETA_ENTIDAD, estado_de_accion
REFS = ['tipos_tratamiento', 'insumos', 'tipo_procedimiento_medico', 'medicamentos', 'tipo_estudio', 'tipo_analisis', 'tipo_diagnostico', 'sintoma']
MOVS = ['consultas_cab', 'ficha_medica_consulta', 'diagnosticos', 'odontograma', 'tratamientos', 'sesiones_tratamiento', 'recetas',
        'orden_estudios', 'orden_analisis', 'justificativo_medico']
chk('8 referenciales con módulo "Referenciales Consultorio" y etiqueta',
    all(MODULO_POR_ENTIDAD.get(e) == 'Referenciales Consultorio' and e in ETIQUETA_ENTIDAD for e in REFS))
chk('10 movimientos con módulo "Módulo Consultorio" y etiqueta',
    all(MODULO_POR_ENTIDAD.get(e) == 'Módulo Consultorio' and e in ETIQUETA_ENTIDAD for e in MOVS))
chk('los 10 movimientos son ENTIDADES_MOVIMIENTO y los referenciales no', set(MOVS) <= ENTIDADES_MOVIMIENTO and not set(REFS) & ENTIDADES_MOVIMIENTO)
est_mov, est_ref = estado_de_accion('BAJA', 'recetas')[1], estado_de_accion('BAJA', 'sintoma')[1]
chk('BAJA de un movimiento clínico = Anulado; de un referencial = Inactivo', 'Anulado' in str(est_mov) and 'Inactivo' in str(est_ref))
from app.rutas.modulo_consultorio import utils as u
chk('modulo_consultorio/utils.py reexporta auditar y detalle_cambios', callable(u.auditar) and callable(u.detalle_cambios))

# ---------- schema_consultorio_base.sql en una base temporal ----------
B = pathlib.Path(os.environ['PG_BIN_DIR'])
env = dict(os.environ, PGPASSWORD=os.environ['TEST_DB_PASSWORD'], PGCLIENTENCODING='UTF8')
h = os.environ.get('TEST_DB_HOST') or os.environ['DB_HOST']; p = str(os.environ.get('TEST_DB_PORT') or os.environ['DB_PORT'])
usr = os.environ['TEST_DB_USER']; real = os.environ.get('TEST_DB_NAME') or os.environ['DB_NAME']; tmp = 'zz_consultorio_base_test'
adm = Conexion('postgres').getConexion(); adm.autocommit = True; ac = adm.cursor()
ac.execute(f'DROP DATABASE IF EXISTS {tmp}'); ac.execute(f'CREATE DATABASE {tmp}')


def firma(cur):
    f = []
    for t in TABLAS:
        cur.execute("""SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull, pg_get_expr(d.adbin, d.adrelid), a.attidentity
                       FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                       WHERE a.attrelid=%s::regclass AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum""", (t,))
        f.append(cur.fetchall())
        cur.execute("SELECT conname, CASE WHEN contype='c' THEN 'CHECK' ELSE pg_get_constraintdef(oid) END FROM pg_constraint "
                    "WHERE conrelid=%s::regclass ORDER BY 1", (t,))
        f.append(cur.fetchall())
        cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename=%s ORDER BY 1", (t,)); f.append(cur.fetchall())
    cur.execute("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal AND tgrelid='odontograma'::regclass"); f.append(cur.fetchall())
    cur.execute("SELECT id_estado_dental, descripcion, simbolo FROM estado_dental ORDER BY 1"); f.append(cur.fetchall())
    return f


try:
    dump = subprocess.run([str(B / 'pg_dump.exe'), '-h', h, '-p', p, '-U', usr, '-s', '-d', real], env=env, capture_output=True,
                          text=True, encoding='utf-8')
    chk('pg_dump del esquema real', dump.returncode == 0)
    arch = pathlib.Path(os.environ['TEMP']) / 'zz_consultorio_esquema.sql'; arch.write_text(dump.stdout, encoding='utf-8')
    subprocess.run([str(B / 'psql.exe'), '-h', h, '-p', p, '-U', usr, '-d', tmp, '-q', '-f', str(arch)], env=env, capture_output=True, text=True)
    t = Conexion(tmp).getConexion(); tc = t.cursor()
    tc.execute('DROP TABLE ' + ', '.join(TABLAS) + ' CASCADE'); t.commit()
    sql = (DAO / 'schema_consultorio_base.sql').read_text(encoding='utf-8')
    tc.execute(sql); t.commit(); chk('schema_consultorio_base.sql corre sobre una base sin las tablas de Consultorio', True)
    chk('las 23 tablas, constraints, índices, trigger y estados dentales son IGUALES a la base real', firma(cu) == firma(tc))
    tc.execute(sql); t.commit(); chk('schema_consultorio_base.sql es IDEMPOTENTE (2.ª corrida sin errores)', True)
    chk('la 2.ª corrida no duplica los estados dentales', firma(cu)[-1] == firma(tc)[-1])
    tc.execute((DAO / 'schema_consultorio_etapa0.sql').read_text(encoding='utf-8')); t.commit()
    chk('schema_consultorio_etapa0.sql sobre una base ya al día es un no-op', firma(cu) == firma(tc))
    for etapa in ('schema_consultorio_etapa2.sql', 'schema_consultorio_etapa3.sql'):
        tc.execute((DAO / etapa).read_text(encoding='utf-8')); t.commit()
        chk(f'{etapa} sobre una base ya al día es un no-op', firma(cu) == firma(tc))
    t.close()
except Exception as e:
    chk(f'base temporal: {e}', False)
finally:
    ac.execute(f'DROP DATABASE IF EXISTS {tmp}')

print('FALLOS:', 'ninguno' if not fallos else fallos)
