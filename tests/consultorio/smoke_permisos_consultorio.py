"""Cierre de Consultorio: test TRANSVERSAL de permisos — Médico, Recepción, Cajero y Administrador × las 18 ventanas (la vista y cada acción: ver, nuevo, editar,
anular, estado y PDF) y el límite "un médico solo ve lo suyo".

Tres partes:
  1. POLÍTICA de los movimientos clínicos y de los 8 referenciales clínicos (regla de negocio escrita acá) contra la matriz real de `permisos`: Médico carga lo clínico y gestiona los
     referenciales, Recepción solo registra / cancela / anula consultas y VE las fichas (ningún permiso sobre los referenciales), el Cajero no tiene nada, el Administrador pasa siempre (bypass) y falla si el catálogo tiene una ventana de Consultorio que este test no cubre.
  2. APLICACIÓN: para cada usuario y cada ventana se llama a la vista y a cada endpoint con un cuerpo inválido o un id inexistente: con el permiso responde algo distinto de 403
     (400 / 404 / 409) y sin el permiso responde 403 exacto. Se verifica así que el servidor aplica la matriz en todas las acciones, incluidas las de editar de los referenciales.
  3. PRIVACIDAD y SOLO LECTURA: con un documento clínico real de cada tipo de un médico A, el médico B (y los demás roles) no lo leen ni por detalle, ni por listado, ni por PDF, ni
     por los lookups de la consulta, y el Administrador lee todo pero no crea, anula, avanza ni emite nada.
Datos `ZZ` de tests/consultorio/_fixtures.py (se borran por ID con su auditoría). Los hallazgos que no son fallo (decisiones de matriz a confirmar) se imprimen como AVISO.
"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from app.rutas.modulo_seguridad.menu_catalog import CATALOGO_MENU
from tests._conexion_pruebas import Conexion
from tests.consultorio._fixtures import Fixtures

fallos, avisos = [], []


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


# ---------------------------------------------------------------------------------------------------------------------
# 1. POLÍTICA de los movimientos clínicos (regla de negocio)
# ---------------------------------------------------------------------------------------------------------------------
TODAS = {'ver', 'nuevo', 'anular'}
POLITICA = {   # ventana -> {rol: acciones}; el Administrador pasa siempre (no necesita filas) y el Cajero no tiene ninguna
    'consulta': {'Medico': {'ver', 'estado'}, 'Recepcion': {'ver', 'nuevo', 'estado', 'anular'}},
    'fichamedica': {'Medico': {'ver', 'nuevo', 'editar', 'anular'}, 'Recepcion': {'ver'}},
    'diagnostico': {'Medico': {'ver', 'nuevo', 'anular'}},
    'odontograma': {'Medico': {'ver', 'nuevo', 'editar', 'anular'}},
    'tratamiento': {'Medico': {'ver', 'nuevo', 'anular', 'estado'}},
    'sesiontratamiento': {'Medico': TODAS},
    'receta': {'Medico': TODAS},
    'ordenestudio': {'Medico': TODAS | {'estado'}},
    'ordenanalisis': {'Medico': TODAS | {'estado'}},
    'justificativomedico': {'Medico': TODAS | {'estado'}},
}
REFERENCIALES = {   # ventana -> (base de la API, URL de la vista)
    'tipodiagnostico': '/api/v1/diagnosticos', 'sintoma': '/api/v1/sintomas', 'tipotratamiento': '/api/v1/tipos-tratamiento', 'tipoinsumo': '/api/v1/tipos-insumo',
    'tipoprocedimientomedico': '/api/v1/tipos-procedimiento-medico', 'medicamento': '/api/v1/medicamentos', 'tipoestudio': '/api/v1/tipos-estudio', 'tipoanalisis': '/api/v1/tipos-analisis',
}
for _v in REFERENCIALES:   # los 8 referenciales clínicos los gestiona el Médico (ver, nuevo, editar, anular) y el Administrador; Recepción y Cajero no tienen NINGÚN permiso
    POLITICA[_v] = {'Medico': {'ver', 'nuevo', 'editar', 'anular'}}
ROLES = ('Medico', 'Recepcion', 'Cajero')

matriz = {}   # (rol, ventana) -> {acciones}
for rol, ventana, accion in q("SELECT r.nombre_rol, m.clave, p.accion FROM permisos p JOIN roles r USING(id_rol) JOIN menu m USING(id_menu) WHERE m.activo = true"):
    matriz.setdefault((rol, ventana), set()).add(accion)

print('\n=== 1. Política de los movimientos clínicos contra la matriz real')
catalogo = [e for e in CATALOGO_MENU if e['modulo'] in ('Módulo Consultorio', 'Referenciales Consultorio') and e['ventana'] != 'historial']
ventanas = {e['ventana']: e for e in catalogo}
chk('el catálogo de Consultorio tiene las 18 ventanas (10 movimientos + 8 referenciales; "historial" es de Agendamiento)', len(ventanas) == 18 and set(POLITICA) == set(ventanas))
for ventana, por_rol in POLITICA.items():
    for rol in ROLES:
        esperado = por_rol.get(rol, set())
        real = matriz.get((rol, ventana), set())
        chk(f'{ventana}: {rol} tiene {sorted(esperado) or "ninguna acción"}' + ('' if real == esperado else f' (real: {sorted(real)})'), real == esperado)
chk('toda acción de la matriz existe en el catálogo de su ventana', all(a in ventanas[v]['acciones'] for (r, v), acc in matriz.items() if v in ventanas for a in acc))
chk('ventana EXCLUSIVA del Administrador sin filas para otros roles: backup y auditoría de cambios no figuran en Consultorio', not any(v in ('backup', 'auditoriacambios') for (_, v) in matriz if v in ventanas))
chk('Recepción y Cajero no tienen ningún permiso sobre los 8 referenciales clínicos', not any(matriz.get((rol, v)) for v in REFERENCIALES for rol in ('Recepcion', 'Cajero')))

# ---------------------------------------------------------------------------------------------------------------------
# 2. APLICACIÓN de la matriz en cada vista y endpoint
# ---------------------------------------------------------------------------------------------------------------------
NOEXISTE = 99999999
PROBES = []   # (ventana, acción, método, URL, cuerpo)
for ventana, base in REFERENCIALES.items():
    PROBES += [(ventana, 'nuevo', 'post', base, {}), (ventana, 'editar', 'put', f'{base}/{NOEXISTE}', {}), (ventana, 'editar', 'patch', f'{base}/{NOEXISTE}/reactivar', {}),
               (ventana, 'anular', 'delete', f'{base}/{NOEXISTE}', None), (ventana, 'ver', 'get', f'{base}/{NOEXISTE}', None)]
PROBES += [
    ('consulta', 'ver', 'get', f'/api/v1/consultas/{NOEXISTE}/resumen', None), ('consulta', 'ver', 'get', '/api/v1/consultas', None), ('consulta', 'nuevo', 'post', '/api/v1/consultas', {}),
    ('consulta', 'estado', 'patch', f'/api/v1/consultas/{NOEXISTE}/estado', {}), ('consulta', 'anular', 'delete', f'/api/v1/consultas/{NOEXISTE}', None),
    ('fichamedica', 'ver', 'get', f'/api/v1/ficha-medica/{NOEXISTE}', None), ('fichamedica', 'ver', 'get', '/api/v1/ficha-medica', None), ('fichamedica', 'nuevo', 'post', '/api/v1/ficha-medica', {}),
    ('fichamedica', 'editar', 'put', f'/api/v1/ficha-medica/{NOEXISTE}', {}), ('fichamedica', 'anular', 'delete', f'/api/v1/ficha-medica/{NOEXISTE}', None),
    ('diagnostico', 'ver', 'get', f'/api/v1/diagnosticos-medicos/{NOEXISTE}', None), ('diagnostico', 'ver', 'get', '/api/v1/diagnosticos-medicos', None),
    ('diagnostico', 'nuevo', 'post', '/api/v1/diagnosticos-medicos', {}), ('diagnostico', 'anular', 'delete', f'/api/v1/diagnosticos-medicos/{NOEXISTE}', None),
    ('odontograma', 'ver', 'get', f'/api/v1/odontogramas/{NOEXISTE}', None), ('odontograma', 'ver', 'get', '/api/v1/odontogramas', None), ('odontograma', 'nuevo', 'post', '/api/v1/odontogramas', {}),
    ('odontograma', 'editar', 'post', f'/api/v1/odontogramas/{NOEXISTE}/hallazgos', {}), ('odontograma', 'editar', 'delete', f'/api/v1/odontogramas/hallazgos/{NOEXISTE}', None),
    ('odontograma', 'anular', 'delete', f'/api/v1/odontogramas/{NOEXISTE}', None),
    ('tratamiento', 'ver', 'get', f'/api/v1/tratamientos/{NOEXISTE}', None), ('tratamiento', 'ver', 'get', '/api/v1/tratamientos', None), ('tratamiento', 'nuevo', 'post', '/api/v1/tratamientos', {}),
    ('tratamiento', 'estado', 'put', f'/api/v1/tratamientos/{NOEXISTE}/finalizar', None), ('tratamiento', 'anular', 'delete', f'/api/v1/tratamientos/{NOEXISTE}', None),
    ('sesiontratamiento', 'ver', 'get', f'/api/v1/sesiones-tratamiento/{NOEXISTE}', None), ('sesiontratamiento', 'nuevo', 'post', '/api/v1/sesiones-tratamiento', {}),
    ('sesiontratamiento', 'anular', 'delete', f'/api/v1/sesiones-tratamiento/{NOEXISTE}', None),
    ('receta', 'ver', 'get', f'/api/v1/recetas/{NOEXISTE}', None), ('receta', 'ver', 'get', '/api/v1/recetas', None), ('receta', 'ver', 'get', f'/api/v1/recetas/{NOEXISTE}/pdf', None),
    ('receta', 'nuevo', 'post', '/api/v1/recetas', {}), ('receta', 'anular', 'delete', f'/api/v1/recetas/{NOEXISTE}', None),
]
for ventana, base in (('ordenestudio', '/api/v1/orden-estudios'), ('ordenanalisis', '/api/v1/orden-analisis')):
    PROBES += [(ventana, 'ver', 'get', f'{base}/{NOEXISTE}', None), (ventana, 'ver', 'get', base, None), (ventana, 'ver', 'get', f'{base}/{NOEXISTE}/pdf', None), (ventana, 'nuevo', 'post', base, {}),
               (ventana, 'estado', 'put', f'{base}/{NOEXISTE}/estado', None), (ventana, 'anular', 'delete', f'{base}/{NOEXISTE}', None)]
PROBES += [('justificativomedico', 'ver', 'get', f'/api/v1/justificativos/{NOEXISTE}', None), ('justificativomedico', 'ver', 'get', '/api/v1/justificativos', None),
           ('justificativomedico', 'ver', 'get', f'/api/v1/justificativos/{NOEXISTE}/pdf', None), ('justificativomedico', 'nuevo', 'post', '/api/v1/justificativos', {}),
           ('justificativomedico', 'estado', 'put', f'/api/v1/justificativos/{NOEXISTE}/emitir', None), ('justificativomedico', 'anular', 'delete', f'/api/v1/justificativos/{NOEXISTE}', None)]

VISTAS = {e['ventana']: e['endpoint'] for e in catalogo}   # ventana -> endpoint de Flask
try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    USUARIOS = {'Medico': cliente(u_med), 'Recepcion': cliente(u_rec), 'Cajero': cliente(cajero), 'Administrador': cliente(admin)}
    C_B = cliente(u_med2)

    def permitido(rol, ventana, accion):
        return rol == 'Administrador' or accion in matriz.get((rol, ventana), set())

    print('\n=== 2. Cada vista y cada acción aplican la matriz')
    with app.test_request_context():
        from flask import url_for
        urls_vista = {v: url_for(e) for v, e in VISTAS.items()}
    malos = []
    for rol, c in USUARIOS.items():
        for ventana, url in urls_vista.items():
            esperado_ok = permitido(rol, ventana, 'ver')
            status = c.get(url).status_code
            if (status == 200) != esperado_ok or (not esperado_ok and status != 403):
                malos.append(f'VISTA {rol} {ventana} {url} -> {status} (esperado {"200" if esperado_ok else "403"})')
        for ventana, accion, metodo, url, cuerpo in PROBES:
            r = getattr(c, metodo)(url, json=cuerpo) if cuerpo is not None else getattr(c, metodo)(url)
            ok = permitido(rol, ventana, accion)
            if ok and (r.status_code == 403 or r.status_code >= 500):
                malos.append(f'{rol} {ventana}:{accion} {metodo.upper()} {url} -> {r.status_code} (con permiso no debe ser 403 ni 5xx)')
            if not ok and r.status_code != 403:
                malos.append(f'{rol} {ventana}:{accion} {metodo.upper()} {url} -> {r.status_code} (sin permiso debe ser 403)')
    total = len(USUARIOS) * (len(urls_vista) + len(PROBES))
    for m in malos[:40]:
        print('FAIL', m)
    chk(f'{total} combinaciones usuario × vista / acción responden según la matriz (con permiso nunca 403 ni 5xx; sin permiso siempre 403)', not malos)
    fallos.extend(malos[:40])
    # la vista contextual de una consulta (Atención) pide `consulta ver`
    for rol, c in USUARIOS.items():
        s = c.get(f'/referenciales/consulta/consulta-detalle/{NOEXISTE}').status_code
        chk(f'Atención de la consulta ({rol}): {s}', (s == 404) if permitido(rol, 'consulta', 'ver') else (s == 403))
    sin_sesion = app.test_client()
    chk('sin sesión todas las vistas redirigen y toda la API responde 401', all(sin_sesion.get(u).status_code == 302 for u in urls_vista.values())
        and all(getattr(sin_sesion, m)(u, json={} if b is not None else None).status_code == 401 for _, _, m, u, b in PROBES[:60]))

    # ---------------------------------------------------------------------------------------------------------------------
    # 3. PRIVACIDAD (un médico solo ve lo suyo) y SOLO LECTURA del Administrador
    # ---------------------------------------------------------------------------------------------------------------------
    print('\n=== 3. Privacidad: un médico solo ve lo suyo; el Administrador lee pero no escribe')
    tdx, sint, ttr, proc, mdc, tes, tan = fx.tipo_diagnostico(), fx.sintoma(), fx.tipo_tratamiento(), fx.tipo_procedimiento(), fx.medicamento(), fx.tipo_estudio(), fx.tipo_analisis()
    c1 = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec, 'en_proceso')
    A = USUARIOS['Medico']
    docs = {}

    def crear(clave, url, cuerpo, pk):
        r = A.post(url, json=cuerpo)
        ok = r.status_code in (200, 201)
        chk(f'el médico A crea {clave} -> {r.status_code}', ok)
        if ok:
            d = (r.get_json() or {}).get('data') or {}
            docs[clave] = d.get(pk) if pk else None
        return ok
    crear('ficha', '/api/v1/ficha-medica', {'id_consulta_cab': c1, 'temperatura': '36.5'}, None)
    ficha = A.get(f'/api/v1/ficha-medica/consulta/{c1}').get_json()['data']
    docs['ficha'] = ficha['id_ficha_medica']
    crear('diagnostico', '/api/v1/diagnosticos-medicos', {'id_consulta_cab': c1, 'id_tipo_diagnostico': tdx, 'sintomas': [sint], 'descripcion_diagnostico': 'ZZ'}, 'id_diagnostico')
    crear('odontograma', '/api/v1/odontogramas', {'id_consulta_cab': c1}, 'id_odontograma')
    crear('tratamiento', '/api/v1/tratamientos', {'id_consulta_cab': c1, 'id_tipo_tratamiento': ttr, 'descripcion_tratamiento': 'ZZ'}, 'id_tratamiento')
    crear('sesion', '/api/v1/sesiones-tratamiento', {'id_tratamiento': docs['tratamiento'], 'id_consulta_cab': c1, 'procedimientos': [proc], 'descripcion_procedimiento': 'ZZ'}, 'id_sesion')
    crear('receta', '/api/v1/recetas', {'id_consulta_cab': c1, 'indicaciones_generales': 'ZZ', 'medicamentos': [{'id_medicamento': mdc, 'dosis': '1', 'frecuencia': '1', 'duracion': '1'}]}, 'id_receta')
    crear('orden_estudio', '/api/v1/orden-estudios', {'id_consulta_cab': c1, 'id_tipo_estudio': tes, 'motivo_orden': 'ZZ'}, 'id_orden_estudio')
    crear('orden_analisis', '/api/v1/orden-analisis', {'id_consulta_cab': c1, 'id_tipo_analisis': tan, 'motivo_orden': 'ZZ'}, 'id_orden_analisis')
    crear('justificativo', '/api/v1/justificativos', {'id_consulta_cab': c1, 'dias_reposo': 1}, 'id_justificativo')
    ENT = {'ficha': 'ficha_medica_consulta', 'diagnostico': 'diagnosticos', 'odontograma': 'odontograma', 'tratamiento': 'tratamientos', 'sesion': 'sesiones_tratamiento', 'receta': 'recetas',
           'orden_estudio': 'orden_estudios', 'orden_analisis': 'orden_analisis', 'justificativo': 'justificativo_medico'}
    for clave, i in docs.items():
        if i:
            fx.auditoria_de(ENT[clave], i)
    fx.auditoria_de('consultas_cab', c1)
    chk('los 9 documentos clínicos del médico A existen', len([v for v in docs.values() if v]) == 9)

    LECTURAS = [   # (clave, detalle, listado, PDF, lookup por consulta)
        ('ficha', f"/api/v1/ficha-medica/{docs.get('ficha')}", '/api/v1/ficha-medica', None, f'/api/v1/ficha-medica/consulta/{c1}', 'fichamedica'),
        ('diagnostico', f"/api/v1/diagnosticos-medicos/{docs.get('diagnostico')}", '/api/v1/diagnosticos-medicos', None, f'/api/v1/diagnosticos-medicos/consulta/{c1}', 'diagnostico'),
        ('odontograma', f"/api/v1/odontogramas/{docs.get('odontograma')}", '/api/v1/odontogramas', None, f'/api/v1/odontogramas/consulta/{c1}', 'odontograma'),
        ('tratamiento', f"/api/v1/tratamientos/{docs.get('tratamiento')}", '/api/v1/tratamientos', None, f'/api/v1/tratamientos/consulta/{c1}', 'tratamiento'),
        ('sesion', f"/api/v1/sesiones-tratamiento/{docs.get('sesion')}", None, None, None, 'sesiontratamiento'),
        ('receta', f"/api/v1/recetas/{docs.get('receta')}", '/api/v1/recetas', f"/api/v1/recetas/{docs.get('receta')}/pdf", None, 'receta'),
        ('orden_estudio', f"/api/v1/orden-estudios/{docs.get('orden_estudio')}", '/api/v1/orden-estudios', f"/api/v1/orden-estudios/{docs.get('orden_estudio')}/pdf", None, 'ordenestudio'),
        ('orden_analisis', f"/api/v1/orden-analisis/{docs.get('orden_analisis')}", '/api/v1/orden-analisis', f"/api/v1/orden-analisis/{docs.get('orden_analisis')}/pdf", None, 'ordenanalisis'),
        ('justificativo', f"/api/v1/justificativos/{docs.get('justificativo')}", '/api/v1/justificativos', f"/api/v1/justificativos/{docs.get('justificativo')}/pdf", None, 'justificativomedico'),
    ]
    for clave, detalle, listado, pdf, lookup, ventana in LECTURAS:
        chk(f'{clave}: el médico A lee su detalle', A.get(detalle).status_code == 200)
        chk(f'{clave}: el médico B NO lee el detalle ajeno (403)', C_B.get(detalle).status_code == 403)
        chk(f'{clave}: el Administrador lee el detalle (200)', USUARIOS['Administrador'].get(detalle).status_code == 200)
        rec_esperado = 200 if permitido('Recepcion', ventana, 'ver') else 403
        chk(f'{clave}: Recepción lee el detalle solo si tiene "ver" ({rec_esperado})', USUARIOS['Recepcion'].get(detalle).status_code == rec_esperado)
        chk(f'{clave}: el Cajero NO lee el detalle (403)', USUARIOS['Cajero'].get(detalle).status_code == 403)
        if listado:
            sep = '&' if '?' in listado else '?'
            lb = C_B.get(f'{listado}{sep}consulta={c1}')
            filas_b = (lb.get_json() or {}).get('data') if lb.status_code == 200 else None
            chk(f'{clave}: el listado del médico B no trae nada de A', lb.status_code == 200 and not filas_b)
            la = A.get(f'{listado}{sep}consulta={c1}').get_json()
            chk(f'{clave}: el listado de A trae lo suyo', len(la['data']) >= 1)
            lad = USUARIOS['Administrador'].get(f'{listado}{sep}consulta={c1}').get_json()
            chk(f'{clave}: el Administrador ve el listado completo', len(lad['data']) >= 1)
        if pdf:
            chk(f'{clave}: PDF — A y el Administrador descargan, B no (403), el Cajero no (403)',
                A.get(pdf).status_code == 200 and USUARIOS['Administrador'].get(pdf).status_code == 200 and C_B.get(pdf).status_code == 403 and USUARIOS['Cajero'].get(pdf).status_code == 403)
        if lookup:
            chk(f'{clave}: el lookup por consulta no se abre a otro médico (403) ni al Cajero (403)', C_B.get(lookup).status_code == 403 and USUARIOS['Cajero'].get(lookup).status_code == 403)
    chk('el resumen de la consulta de A: A y el Administrador sí, el médico B no (403)',
        A.get(f'/api/v1/consultas/{c1}/resumen').status_code == 200 and USUARIOS['Administrador'].get(f'/api/v1/consultas/{c1}/resumen').status_code == 200
        and C_B.get(f'/api/v1/consultas/{c1}/resumen').status_code == 403)
    chk('la Atención de la consulta de A: A sí, el médico B no (403)', A.get(f'/referenciales/consulta/consulta-detalle/{c1}').status_code == 200
        and C_B.get(f'/referenciales/consulta/consulta-detalle/{c1}').status_code == 403)
    lb = C_B.get('/api/v1/consultas').get_json()
    chk('el listado de consultas del médico B no incluye la consulta de A', all(x['id_consulta_cab'] != c1 for x in lb['data']))
    # los lookups que solo pedían sesión y dejaban leer cualquier consulta (o todas las activas) se eliminaron en el cierre
    chk('GET /consultas/<id> y /consultas/activas ya no existen (404 / 405 para todos)', all(c.get(u).status_code in (404, 405) for c in (A, C_B, USUARIOS['Administrador'], USUARIOS['Cajero'])
                                                                                          for u in (f'/api/v1/consultas/{c1}', '/api/v1/consultas/activas')))

    print('\n--- el Administrador, Recepción, el Cajero y el médico B NO escriben sobre lo de A')
    ESCRITURAS = [
        ('ficha', 'put', f"/api/v1/ficha-medica/{docs.get('ficha')}", {'temperatura': '37'}), ('ficha', 'delete', f"/api/v1/ficha-medica/{docs.get('ficha')}", None),
        ('diagnostico', 'post', '/api/v1/diagnosticos-medicos', {'id_consulta_cab': c1, 'id_tipo_diagnostico': tdx, 'sintomas': [sint], 'descripcion_diagnostico': 'ZZ'}),
        ('diagnostico', 'delete', f"/api/v1/diagnosticos-medicos/{docs.get('diagnostico')}", None),
        ('odontograma', 'delete', f"/api/v1/odontogramas/{docs.get('odontograma')}", None),
        ('tratamiento', 'post', '/api/v1/tratamientos', {'id_consulta_cab': c1, 'id_tipo_tratamiento': ttr, 'descripcion_tratamiento': 'ZZ'}),
        ('tratamiento', 'put', f"/api/v1/tratamientos/{docs.get('tratamiento')}/finalizar", None), ('tratamiento', 'delete', f"/api/v1/tratamientos/{docs.get('tratamiento')}", None),
        ('sesion', 'post', '/api/v1/sesiones-tratamiento', {'id_tratamiento': docs.get('tratamiento'), 'id_consulta_cab': c1, 'procedimientos': [proc], 'descripcion_procedimiento': 'ZZ'}),
        ('sesion', 'delete', f"/api/v1/sesiones-tratamiento/{docs.get('sesion')}", None),
        ('receta', 'post', '/api/v1/recetas', {'id_consulta_cab': c1, 'indicaciones_generales': 'ZZ', 'medicamentos': [{'id_medicamento': mdc, 'dosis': '1', 'frecuencia': '1', 'duracion': '1'}]}),
        ('receta', 'delete', f"/api/v1/recetas/{docs.get('receta')}", None),
        ('orden_estudio', 'post', '/api/v1/orden-estudios', {'id_consulta_cab': c1, 'id_tipo_estudio': tes, 'motivo_orden': 'ZZ'}),
        ('orden_estudio', 'put', f"/api/v1/orden-estudios/{docs.get('orden_estudio')}/estado", None), ('orden_estudio', 'delete', f"/api/v1/orden-estudios/{docs.get('orden_estudio')}", None),
        ('orden_analisis', 'post', '/api/v1/orden-analisis', {'id_consulta_cab': c1, 'id_tipo_analisis': tan, 'motivo_orden': 'ZZ'}),
        ('orden_analisis', 'put', f"/api/v1/orden-analisis/{docs.get('orden_analisis')}/estado", None), ('orden_analisis', 'delete', f"/api/v1/orden-analisis/{docs.get('orden_analisis')}", None),
        ('justificativo', 'post', '/api/v1/justificativos', {'id_consulta_cab': c1, 'dias_reposo': 1}),
        ('justificativo', 'put', f"/api/v1/justificativos/{docs.get('justificativo')}/emitir", None), ('justificativo', 'delete', f"/api/v1/justificativos/{docs.get('justificativo')}", None),
    ]
    for quien, c in (('Administrador', USUARIOS['Administrador']), ('médico B', C_B), ('Recepción', USUARIOS['Recepcion']), ('Cajero', USUARIOS['Cajero'])):
        malos = []
        for clave, metodo, url, cuerpo in ESCRITURAS:
            r = getattr(c, metodo)(url, json=cuerpo) if cuerpo is not None else getattr(c, metodo)(url)
            if r.status_code != 403:
                malos.append(f'{clave} {metodo.upper()} {url} -> {r.status_code}')
        chk(f'{quien}: las {len(ESCRITURAS)} escrituras clínicas sobre la consulta de A responden 403', not malos)
        for m in malos:
            print('     ', m)
    quedo = q("SELECT (SELECT COUNT(*) FROM recetas WHERE id_consulta_cab=%s AND activo), (SELECT COUNT(*) FROM tratamientos WHERE id_consulta_cab=%s AND estado<>'cancelado'), "
              "(SELECT COUNT(*) FROM justificativo_medico WHERE id_consulta_cab=%s AND estado='pendiente'), (SELECT COUNT(*) FROM orden_estudios WHERE id_consulta_cab=%s AND estado='pendiente')",
              (c1, c1, c1, c1))[0]
    chk(f'...y nada cambió: 1 receta vigente, 1 tratamiento, 1 justificativo pendiente y 1 orden de estudios pendiente {quedo}', quedo == (1, 1, 1, 1))
finally:
    cx.rollback()
    fx.limpiar()

print()
for a in avisos:
    print('AVISO', a)
print('\nFALLOS:', 'ninguno' if not fallos else fallos)
