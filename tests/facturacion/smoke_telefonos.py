"""Teléfonos en formato nacional en todo el sistema: se guarda solo con dígitos y el 0 inicial (celular ^09\\d{8}$, línea baja ^0[2-8]\\d{7,8}$),
se muestra "0984 818 035" / "021 339 8423", WhatsApp solo para celulares (0 -> 595) y la migración 04 (595XXXXXXXXX -> 0XXXXXXXXX).
Cubre: servicio app/Services/telefono.py, validación del servidor en cada API con teléfono (paciente, cliente, consultorio, entidad emisora),
pantallas (campos con formato al salir y tablas formateadas), PDFs, filtro Jinja del dashboard, WhatsApp y la migración sobre datos ZZ.
La comparación JS <-> Python de las mismas reglas está en comparar_js_py.py (casos 'tel', 'telNorm', 'telFmt', 'telWa').
Datos de prueba con prefijo ZZ, borrados POR ID; la auditoría que genera el test se borra por ID."""
import pathlib, sys
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from app import app
from tests._conexion_pruebas import Conexion
from tests.facturacion._limpieza import borrar_auditoria
from tests.facturacion._pdf import texto_pdf
from app.Services import telefono as tel
from app.Services import whatsapp_service as ws
from app.Services import auditoria_pdf_service as pdfaud

fallos = []
c = app.test_client()
MSJ = 'Ingrese un celular (09XX XXX XXX) o una línea baja con código de área (021 XXX XXXX)'


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


# ---------------------------------------------------------------------------------------------------------------------------------
print('== Servicio de teléfonos')
VALIDOS = {'0984818035': '0984818035', '0984 818 035': '0984818035', '0984-818-035': '0984818035', '  0984 818 035  ': '0984818035',
           '021 339 8423': '0213398423', '0213398423': '0213398423', '021 600 600': '021600600', '0361 123456': '0361123456',
           '083 123 4567': '0831234567', '021555123': '021555123'}
for entrada, guardado in VALIDOS.items():
    chk(f'válido {entrada!r} -> se guarda {guardado}', tel.validar_telefono(entrada) == (guardado, None))
INVALIDOS = ['09848180', '098481803512', '0184818035', '0984 818 03(5)', '595984818035', '+595984818035', '984818035', '09a4818035', '0112345678', '0912345678x',
             '021 339 84', '021 3398 42 3 1', 'abc', '123', '0984.818.035', '0984\t818035']
for entrada in INVALIDOS:
    t, e = tel.validar_telefono(entrada)
    chk(f'inválido {entrada!r} -> {MSJ[:25]}…', t is None and e == MSJ + '.')
chk('vacío obligatorio: mensaje de obligatorio', tel.validar_telefono('') == (None, tel.MENSAJE_OBLIGATORIO) and tel.validar_telefono('   ') == (None, tel.MENSAJE_OBLIGATORIO)
    and tel.validar_telefono(None) == (None, tel.MENSAJE_OBLIGATORIO))
chk('vacío opcional: (None, None); cargado inválido sigue dando error', tel.validar_telefono('', False) == (None, None) and tel.validar_telefono('  ', False) == (None, None)
    and tel.validar_telefono('12', False)[1] == MSJ + '.')
chk('el mensaje pedido es exacto', tel.MENSAJE_INVALIDO == MSJ + '.')
FORMATO = {'0984818035': '0984 818 035', '0213398423': '021 339 8423', '021600600': '021 600 600', '0361123456': '036 112 3456', '': '', None: '',
           '595981123456': '595981123456', '0981 123 456': '0981 123 456', ' 0984818035 ': '0984 818 035'}
for entrada, esperado in FORMATO.items():
    chk(f'formatear({entrada!r}) -> {esperado!r}', tel.formatear_telefono(entrada) == esperado)
chk('formatear no cambia un dato que no cumple el formato (dato viejo)', tel.formatear_telefono('+595 21 123456') == '+595 21 123456')
chk('formatear no rompe lo que ya viene con espacios', tel.formatear_telefono('0984 818 035') == '0984 818 035')
chk('es_celular / es_linea_baja', tel.es_celular('0984818035') and not tel.es_celular('0213398423') and tel.es_linea_baja('0213398423') and not tel.es_linea_baja('0984818035'))
chk('a_whatsapp: celular -> 595 sin el 0 (con o sin espacios)', tel.a_whatsapp('0984818035') == '595984818035' and tel.a_whatsapp('0984 818 035') == '595984818035')
chk('a_whatsapp: línea baja o inválido -> None', tel.a_whatsapp('021 339 8423') is None and tel.a_whatsapp('595984818035') is None and tel.a_whatsapp('') is None
    and tel.a_whatsapp(None) is None)

print('\n== WhatsApp')
chk('whatsapp_service.normalizar_telefono usa la misma regla', ws.normalizar_telefono('0984 818 035') == '595984818035' and ws.normalizar_telefono('021 339 8423') is None
    and ws.normalizar_telefono('+595984818035') is None)

# ---------------------------------------------------------------------------------------------------------------------------------
cx = Conexion().getConexion(); cx.autocommit = True; cu = cx.cursor()
cu.execute("SELECT COALESCE(MAX(id_auditoria_cambio), 0) FROM auditoria_cambios"); BASE = cu.fetchone()[0]
cu.execute("SELECT id_ciudad FROM ciudades WHERE activo ORDER BY 1 LIMIT 1"); CIUDAD = cu.fetchone()[0]
creados = {'paciente': [], 'cliente': [], 'consultorio': [], 'entidad_emisora': []}


def api(metodo, url, esperado, cuerpo=None):
    r = getattr(c, metodo)(url, json=cuerpo) if cuerpo is not None else getattr(c, metodo)(url)
    return r, (r.get_json(silent=True) or {})


try:
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

    print('\n== APIs: el servidor valida y guarda solo dígitos')
    paciente = {'nombre': 'ZZ Tel', 'apellido': 'ZZ Prueba', 'cedula_entidad': '9970001', 'fecha_nacimiento': '1990-01-01', 'telefono': '0984 818 035',
                'telefono_emergencia': '021 339 8423', 'direccion': 'Calle de prueba 1', 'correo': 'zz.tel@test.invalid', 'id_ciudad': CIUDAD}
    r, d = api('post', '/api/v1/pacientes', 201, paciente)
    chk('Paciente: alta con espacios -> 201', r.status_code == 201, )
    if r.status_code == 201:
        pid = d['data']['id_paciente']; creados['paciente'].append(pid)
        cu.execute("SELECT telefono, telefono_emergencia FROM paciente WHERE id_paciente = %s", (pid,))
        chk('Paciente: en la base quedan solo dígitos con el 0 (celular y línea baja)', cu.fetchone() == ('0984818035', '0213398423'))
    for campo in ('telefono', 'telefono_emergencia'):
        for malo in ('12345', '+595 984 818035', '0984 818 03', 'abc'):
            r, d = api('post', '/api/v1/pacientes', 400, {**paciente, 'cedula_entidad': '9970002', 'correo': 'zz.tel2@test.invalid', campo: malo})
            chk(f'Paciente: {campo} {malo!r} -> 400 con el mensaje de formato y el campo', r.status_code == 400 and MSJ in d.get('error', '') and d.get('campo') == campo)
    r, d = api('post', '/api/v1/pacientes', 400, {**paciente, 'cedula_entidad': '9970002', 'correo': 'zz.tel2@test.invalid', 'telefono': ''})
    chk('Paciente: teléfono vacío -> 400 (obligatorio)', r.status_code == 400 and 'obligatorio' in d.get('error', ''))
    if creados['paciente']:
        r, d = api('put', f"/api/v1/pacientes/{creados['paciente'][0]}", 200, {**paciente, 'telefono': '0991 717 821'})
        cu.execute("SELECT telefono FROM paciente WHERE id_paciente = %s", (creados['paciente'][0],))
        chk('Paciente: edición con espacios -> se guarda sin espacios', r.status_code == 200 and cu.fetchone()[0] == '0991717821')

    r, d = api('post', '/api/v1/clientes', 201, {'nombre': 'zz tel', 'apellido': 'zz', 'ci_ruc': '9970010', 'telefono': '0981-123-456', 'correo': ''})
    chk('Cliente: alta con guiones -> 201 y se guarda 0981123456', r.status_code == 201 and d['data']['telefono'] == '0981123456')
    if r.status_code == 201:
        creados['cliente'].append(d['data']['id_cliente'])
    r, d = api('post', '/api/v1/clientes', 201, {'nombre': 'zz tel dos', 'apellido': '', 'ci_ruc': '9970011', 'telefono': '', 'correo': ''})
    chk('Cliente: teléfono opcional vacío -> NULL', r.status_code == 201 and d['data']['telefono'] is None)
    if r.status_code == 201:
        creados['cliente'].append(d['data']['id_cliente'])
    r, d = api('post', '/api/v1/clientes', 400, {'nombre': 'zz tel tres', 'ci_ruc': '9970012', 'telefono': '0984 818 03', 'correo': ''})
    chk('Cliente: teléfono cargado e inválido -> 400 con el mensaje de formato', r.status_code == 400 and MSJ in d.get('error', '') and d.get('campo') == 'telefono')

    r, d = api('post', '/api/v1/consultorios', 201, {'nombre_consultorio': 'ZZ Consultorio Tel', 'direccion': 'Calle 1', 'telefono': '021 339 8423', 'correo': 'zz.cons.tel@test.invalid'})
    chk('Consultorio: línea baja con espacios -> se guarda 0213398423', r.status_code == 201 and d['data']['telefono'] == '0213398423')
    if r.status_code == 201:
        creados['consultorio'].append(d['data']['codigo'])
    r, d = api('post', '/api/v1/consultorios', 400, {'nombre_consultorio': 'ZZ Consultorio Tel 2', 'direccion': 'Calle 1', 'telefono': '595981123456', 'correo': 'zz.cons.tel2@test.invalid'})
    chk('Consultorio: ya no acepta el formato 595… (400 con el mensaje de formato)', r.status_code == 400 and MSJ in d.get('error', ''))

    r, d = api('post', '/api/v1/entidades-emisoras', 201, {'descripcion': 'zz banco tel', 'direccion': 'Av. Test 1', 'telefono': '021 123 4567', 'correo': 'zz@tel.com'})
    chk('Entidad emisora: alta -> se guarda 0211234567', r.status_code == 201 and d['data']['telefono'] == '0211234567')
    if r.status_code == 201:
        creados['entidad_emisora'].append(d['data']['id_entidad_emisora'])
    r, d = api('post', '/api/v1/entidades-emisoras', 400, {'descripcion': 'zz banco tel 2', 'direccion': 'Av. Test 1', 'telefono': '+595 21 123456', 'correo': 'zz2@tel.com'})
    chk('Entidad emisora: +595 21 123456 ya no es válido -> 400 con el mensaje de formato', r.status_code == 400 and MSJ in d.get('error', '') and d.get('campo') == 'telefono')

    # ---------------------------------------------------------------------------------------------------------------------------
    print('\n== Pantallas')
    PAGINAS = [('/referenciales/paciente/paciente-index', 2), ('/referenciales/medico/medico-index', 1), ('/referenciales/funcionario/funcionario-index', 1),
               ('/referenciales/consultorio/consultorio-index', 1), ('/referenciales/cliente/cliente-index', 1),
               ('/referenciales/entidad-emisora/entidad-emisora-index', 1), ('/referenciales/entidad-adherida/entidad-adherida-index', 1)]
    cu.execute("SELECT 1")
    for url, n in PAGINAS:
        r = c.get(url)
        html = r.get_data(as_text=True)
        chk(f'{url.split("/")[2]}: carga, {n} campo(s) con data-telefono y tabla / edición formateadas', r.status_code == 200 and html.count('data-telefono') == n
            and 'formatearTelefono' in html)
    js = c.get('/static/js/facturacion-validadores.js').get_data(as_text=True)
    chk('el JS expone normalizarTelefono, formatearTelefono, aWhatsapp y el formato al salir del campo', all(x in js for x in ('normalizarTelefono', 'formatearTelefono', 'aWhatsapp', "hasAttribute('data-telefono')"))
        and 'telefonoPy' not in js)
    chk('el JS trae el mensaje exacto', MSJ in js)
    for url in ('/referenciales/consultorio/consultorio-index',):
        chk('consultorio: ya no usa el validador telefonoPy', 'telefonoPy' not in c.get(url).get_data(as_text=True))
    chk('filtro Jinja |telefono', app.jinja_env.filters['telefono']('0984818035') == '0984 818 035' and app.jinja_env.filters['telefono'](None) == '')
    cu.execute("SELECT telefono FROM paciente ORDER BY id_paciente DESC LIMIT 1")      # el dashboard lista los 5 últimos
    fila = cu.fetchone()
    r = c.get('/referenciales/vista/vista-index')
    chk('dashboard: el teléfono del paciente reciente sale formateado', r.status_code == 200 and (not fila or not fila[0] or tel.formatear_telefono(fila[0]) in r.get_data(as_text=True)))

    # ---------------------------------------------------------------------------------------------------------------------------
    print('\n== PDFs')
    datos = pdfaud.calcular_datos_informe('PRUEBA', {'razon_social': 'EMPRESA ZZ', 'ruc': '1-1', 'direccion': 'X', 'telefono': '0984818035'}, [], [('A', 1, 'L')], [['x']], 'ZZ')
    chk('PDF: el teléfono de la empresa sale formateado ("Tel.: 0984 818 035")', 'Tel.: 0984 818 035' in texto_pdf(pdfaud.generarInformePdf(datos)))
    datos = pdfaud.calcular_datos_informe('PRUEBA', {'razon_social': 'EMPRESA ZZ', 'ruc': '1-1', 'direccion': 'X', 'telefono': '021600600'}, [], [('A', 1, 'L')], [['x']], 'ZZ')
    chk('PDF: línea baja de 9 dígitos "021 600 600"', 'Tel.: 021 600 600' in texto_pdf(pdfaud.generarInformePdf(datos)))

    # ---------------------------------------------------------------------------------------------------------------------------
    print('\n== Migración 04 (sobre datos ZZ)')
    M = RAIZ / 'migraciones' / '04_migracion_telefonos.sql'
    cu.execute("""INSERT INTO cliente(nombre, ci_ruc, telefono) VALUES ('ZZ MIG 1', '9970020', '595981123456'), ('ZZ MIG 2', '9970021', '0981 123 456'),
                  ('ZZ MIG 3', '9970022', '+595 21 339 8423'), ('ZZ MIG 4', '9970023', '5952133984'), ('ZZ MIG 5', '9970024', '12345'), ('ZZ MIG 6', '9970025', '0984818035'),
                  ('ZZ MIG 7', '9970026', '021 339 8423') RETURNING id_cliente""")
    mig = [r[0] for r in cu.fetchall()]; creados['cliente'] += mig
    cx.set_client_encoding('UTF8')
    cu.execute(M.read_text(encoding='utf-8'))
    cu.execute(M.read_text(encoding='utf-8'))        # idempotente
    cu.execute("SELECT telefono FROM cliente WHERE id_cliente = ANY(%s) ORDER BY id_cliente", (mig,))
    r = [x[0] for x in cu.fetchall()]
    chk('595981123456 -> 0981123456 (celular)', r[0] == '0981123456')
    chk('"0981 123 456" -> 0981123456 (se quitan los espacios)', r[1] == '0981123456')
    chk('"+595 21 339 8423" -> 0213398423 (línea baja)', r[2] == '0213398423')
    chk('5952133984 (595 + solo 7 dígitos: no es un teléfono válido) queda tal cual', r[3] == '5952133984')
    chk('un dato que no llega a ser válido (12345) no se toca', r[4] == '12345')
    chk('un número ya válido no cambia', r[5] == '0984818035')
    chk('"021 339 8423" -> 0213398423', r[6] == '0213398423')
    cu.execute("""SELECT count(*) FROM (SELECT telefono FROM cliente UNION ALL SELECT telefono FROM medico UNION ALL SELECT telefono FROM paciente UNION ALL
                  SELECT telefono_emergencia FROM paciente UNION ALL SELECT telefono FROM funcionario UNION ALL SELECT telefono FROM consultorio UNION ALL
                  SELECT telefono FROM entidad_emisora UNION ALL SELECT telefono FROM entidad_adherida UNION ALL SELECT telefono FROM empresa) t
                  WHERE telefono ~ '^595' OR telefono ~ '[ +\\-]'""")
    chk('después de la migración no queda ningún teléfono con 595, espacios, guiones ni "+" (salvo datos no válidos de prueba)', cu.fetchone()[0] <= 1)

finally:
    # Limpieza: SOLO lo creado por este test, por ID.
    if creados['cliente']:
        cu.execute("DELETE FROM cliente WHERE id_cliente = ANY(%s)", (creados['cliente'],))
    if creados['paciente']:
        cu.execute("DELETE FROM paciente WHERE id_paciente = ANY(%s)", (creados['paciente'],))
    if creados['consultorio']:
        cu.execute("DELETE FROM consultorio WHERE codigo = ANY(%s)", (creados['consultorio'],))
    if creados['entidad_emisora']:
        cu.execute("DELETE FROM entidad_emisora WHERE id_entidad_emisora = ANY(%s)", (creados['entidad_emisora'],))
    cu.execute("SELECT id_auditoria_cambio FROM auditoria_cambios WHERE id_auditoria_cambio > %s AND id_usuario = 1 AND ip = '127.0.0.1'", (BASE,))
    ids = [x[0] for x in cu.fetchall()]
    cu.execute("SET session_replication_role = replica")
    cu.execute("DELETE FROM auditoria_cambios WHERE id_auditoria_cambio = ANY(%s)", (ids,))
    cu.execute("RESET session_replication_role")
    print(f'(limpieza: {sum(len(v) for v in creados.values())} registros y {len(ids)} filas de auditoría de prueba borrados por ID)')
    cu.close(); cx.close()

print('FALLOS:', 'ninguno' if not fallos else fallos)
