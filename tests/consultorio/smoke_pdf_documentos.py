"""Etapa 6 (commit 1): los PDF de la Receta, la Orden de Estudios y la Orden de Análisis — encabezado de la clínica, N.º, fecha, paciente con CI, médico con
especialidad (el N.º de registro solo si lo tiene), contenido clínico, firma, marca ANULADA / CANCELADA, varias páginas, acceso (privacidad) y auditoría de CADA
descarga como EXPORTACION (sin contenido clínico). Se decodifican los streams con tests/facturacion/_pdf.py. Datos `ZZ` de tests/consultorio/_fixtures.py.
"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from tests._conexion_pruebas import Conexion
from tests.consultorio._fixtures import Fixtures
from tests.facturacion._pdf import paginas_pdf, texto_pdf

fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


cx = Conexion().getConexion(); cu = cx.cursor()
fx = Fixtures(cx)


def q(sql, p=()):
    cu.execute(sql, p)
    return cu.fetchall()


def cliente(id_usuario):
    c = app.test_client()
    id_rol, nombre = q("SELECT u.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=%s", (id_usuario,))[0]
    with c.session_transaction() as s:
        s['id_usuario'] = id_usuario; s['id_rol'] = id_rol; s['nombre_rol'] = nombre
    return c


SECRETO = 'CONTENIDO-CLINICO-9981'
creados = {'recetas': [], 'orden_estudios': [], 'orden_analisis': []}

try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med_sin, u_med_sin = fx.medico()
    med2, u_med2 = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    esp = q("SELECT id_especialidad, nombre_especialidad FROM especialidades WHERE activo ORDER BY 1 LIMIT 1")[0]
    cu.execute("UPDATE medico SET id_especialidad=%s, num_registro='ZZREG-7788' WHERE id_medico=%s", (esp[0], med)); cx.commit()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_SIN, C_MED2, C_ADM = cliente(u_rec), cliente(u_med), cliente(u_med_sin), cliente(u_med2), cliente(admin)
    cedula = q("SELECT cedula_entidad FROM paciente WHERE id_paciente=%s", (pac,))[0][0]
    clinica = q("SELECT razon_social FROM empresa ORDER BY id_empresa LIMIT 1")[0][0]
    m1, m2 = fx.medicamento(), fx.medicamento()
    t_est, t_ana = fx.tipo_estudio(), fx.tipo_analisis()
    c1 = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec, 'en_proceso')
    c_sin = fx.registrar_consulta(fx.cita(med_sin, pac, cons, f_rec), f_rec, 'en_proceso')
    MED = lambda mid, **kw: {'id_medicamento': mid, 'dosis': '500 mg', 'frecuencia': 'cada 8 horas', 'duracion': '7 días', **kw}

    r = C_MED.post('/api/v1/recetas', json={'id_consulta_cab': c1, 'indicaciones_generales': 'Reposo relativo ' + SECRETO, 'medicamentos': [MED(m1), MED(m2, dosis='2 comprimidos')]})
    id_rec = r.get_json()['data']['id_receta']; creados['recetas'].append(id_rec)
    r = C_MED.post('/api/v1/orden-estudios', json={'id_consulta_cab': c1, 'id_tipo_estudio': t_est, 'motivo_orden': 'Control radiográfico ' + SECRETO, 'indicaciones': 'En ayunas'})
    id_est = r.get_json()['data']['id_orden_estudio']; creados['orden_estudios'].append(id_est)
    r = C_MED.post('/api/v1/orden-analisis', json={'id_consulta_cab': c1, 'id_tipo_analisis': t_ana, 'motivo_orden': 'Hemograma ' + SECRETO})
    id_ana = r.get_json()['data']['id_orden_analisis']; creados['orden_analisis'].append(id_ana)
    DOCS = [('receta', f'/api/v1/recetas/{id_rec}/pdf', f'RCT-{id_rec:07d}', 'RECETA', 'recetas', id_rec),
            ('orden de estudios', f'/api/v1/orden-estudios/{id_est}/pdf', f'OES-{id_est:07d}', 'ORDEN DE ESTUDIOS', 'orden_estudios', id_est),
            ('orden de análisis', f'/api/v1/orden-analisis/{id_ana}/pdf', f'OAN-{id_ana:07d}', 'ORDEN DE AN', 'orden_analisis', id_ana)]

    for nombre, url, numero, titulo, entidad, i in DOCS:
        print(f'\n=== PDF de la {nombre}')
        r = C_MED.get(url)
        chk(f'el médico descarga -> {r.status_code} application/pdf', r.status_code == 200 and r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF')
        t = texto_pdf(r.data)
        chk('encabezado de la clínica (razón social)', clinica.split()[0] in t or 'ODONTOCLINIC' in t)
        chk('título y N.º de documento', titulo in t and numero in t)
        chk('fecha de emisión con formato dd/mm/aaaa', __import__('re').search(r'Fecha: \d{2}/\d{2}/\d{4}', t) is not None)
        chk('paciente con su CI', 'ZZ PACIENTE' in t and cedula in t)
        chk('médico con su especialidad y su N.º de registro', 'ZZ MEDICO' in t and esp[1].split()[0] in t and 'ZZREG-7788' in t)
        chk('el contenido clínico va en el PDF', SECRETO in t)
        chk('espacio para la firma', 'Firma y sello' in t)
        chk('1 página y sin marca', paginas_pdf(r.data) == 1 and 'ANULADA' not in t and 'CANCELADA' not in t)
        llamar_otro = [(C_MED2, 403, 'otro médico'), (C_REC, 403, 'Recepción')]
        for c, esperado, quien in llamar_otro:
            chk(f'{quien} NO descarga -> {esperado}', c.get(url).status_code == esperado)
        chk('el Administrador descarga -> 200', C_ADM.get(url).status_code == 200)
        chk('sin sesión -> 401', app.test_client().get(url).status_code == 401)
        chk('un id inexistente -> 404', C_MED.get(url.replace(str(i), '99999999')).status_code == 404)
        fx.auditoria_de(entidad, i)
        filas = q("SELECT detalle, id_usuario, modulo, valores_anteriores::text, valores_nuevos::text FROM auditoria_cambios WHERE entidad=%s AND id_registro=%s AND accion='EXPORTACION' ORDER BY id_auditoria_cambio", (entidad, i))
        chk(f'cada descarga válida queda auditada como EXPORTACION (2: el médico y el Administrador): {len(filas)}', len(filas) == 2 and [f[1] for f in filas] == [u_med, admin])
        chk('...con el N.º, la consulta y el paciente, en el módulo Consultorio', all(numero in f[0] and 'Consulta CON-' in f[0] and 'ZZ PACIENTE' in f[0] and f[2] == 'Módulo Consultorio' for f in filas))
        chk('...SIN contenido clínico', not any(SECRETO in str(x or '') for f in filas for x in f))

    print('\n=== N.º de registro: se omite si el médico no lo tiene (sin columnas nuevas)')
    r = C_SIN.post('/api/v1/orden-estudios', json={'id_consulta_cab': c_sin, 'id_tipo_estudio': t_est, 'motivo_orden': 'Control'})
    id_s = r.get_json()['data']['id_orden_estudio']; creados['orden_estudios'].append(id_s)
    t = texto_pdf(C_SIN.get(f'/api/v1/orden-estudios/{id_s}/pdf').data)
    chk('el PDF de un médico sin N.º de registro no lo menciona y sale igual', 'Registro N' not in t and 'ZZ MEDICO' in t)
    fx.auditoria_de('orden_estudios', id_s)

    print('\n=== Documento anulado: se descarga con la marca')
    C_MED.delete(f'/api/v1/recetas/{id_rec}')
    t = texto_pdf(C_MED.get(DOCS[0][1]).data)
    chk('receta ANULADA: marca en el PDF y contenido intacto', 'ANULADA' in t and SECRETO in t)
    C_MED.delete(f'/api/v1/orden-estudios/{id_est}')
    t = texto_pdf(C_MED.get(DOCS[1][1]).data)
    chk('orden de estudios CANCELADA: marca en el PDF', 'CANCELADA' in t and SECRETO in t)
    chk('...y el estado de la orden aparece en las no anuladas', 'Estado:' in texto_pdf(C_MED.get(DOCS[2][1]).data) and 'Pendiente' in texto_pdf(C_MED.get(DOCS[2][1]).data))

    print('\n=== Varias páginas')
    c_larga = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec, 'en_proceso')
    meds = [fx.medicamento() for _ in range(28)]
    r = C_MED.post('/api/v1/recetas', json={'id_consulta_cab': c_larga, 'indicaciones_generales': ('Indicación larga. ' * 110).strip(),
                                            'medicamentos': [MED(m, dosis='Dosis ' + 'x' * 60) for m in meds]})
    id_l = r.get_json()['data']['id_receta']; creados['recetas'].append(id_l)
    pdf = C_MED.get(f'/api/v1/recetas/{id_l}/pdf').data
    t = texto_pdf(pdf)
    chk(f'una receta con 28 medicamentos sigue en más páginas ({paginas_pdf(pdf)})', paginas_pdf(pdf) >= 2)
    chk('...con los 28 medicamentos, el encabezado repetido y la firma al final', t.count('ZZ MEDICAMENTO') == 28 and t.count('RECETA') >= 2 and 'Firma y sello' in t)
    fx.auditoria_de('recetas', id_l)

    for ent, ids in creados.items():
        for i in ids:
            fx.auditoria_de(ent, i)
    for (i,) in q("SELECT id_consulta_cab FROM consultas_cab WHERE id_paciente=%s", (pac,)):
        fx.auditoria_de('consultas_cab', i)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
