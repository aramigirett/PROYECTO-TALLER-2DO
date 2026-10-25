"""Cierre de Consultorio: TODO lo que muta en el módulo audita con el formato nuevo (módulo + JSON) y SIN contenido clínico.

  1. Estático: cada POST / PUT / PATCH / DELETE de las APIs de Consultorio (incluidas las dos fábricas: referenciales y órdenes) llama a `auditar`; las 18 entidades + `consultas_cab`
     están en MODULO_POR_ENTIDAD / ETIQUETA_ENTIDAD; los 10 movimientos son ENTIDADES_MOVIMIENTO (su BAJA dice Anulado) y los 8 referenciales no.
  2. Dinámico (movimientos): con marcadores secretos en TODOS los campos de texto clínico, un médico recorre alta / edición / estado / anulación / PDF de ficha, diagnóstico, odontograma,
     tratamiento, sesión, receta, las dos órdenes y el justificativo. Cada fila de `auditoria_cambios` de esas operaciones lleva módulo "Módulo Consultorio", una acción válida, JSON
     donde corresponde (ALTA con valores_nuevos, BAJA con el estado Anulado) y NINGUNA contiene un marcador (ni en el detalle ni en los JSON).
  (Los 8 referenciales se prueban dinámicamente en smoke_referenciales_consultorio: auditan la descripción, que es dato de catálogo, no clínico.)
Datos `ZZ` de tests/consultorio/_fixtures.py (se borran por ID con su auditoría).
"""
import ast
import pathlib
import sys
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from app import app
from app.Services.auditoria_detalle import ENTIDADES_MOVIMIENTO, ETIQUETA_ENTIDAD, MODULO_POR_ENTIDAD
from tests._conexion_pruebas import Conexion
from tests.consultorio._fixtures import Fixtures

fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


print('=== 1. Estático')
MOVIMIENTOS = ['consultas_cab', 'ficha_medica_consulta', 'diagnosticos', 'odontograma', 'tratamientos', 'sesiones_tratamiento', 'recetas', 'orden_estudios', 'orden_analisis', 'justificativo_medico']
REFERENCIALES = ['tipo_diagnostico', 'sintoma', 'tipos_tratamiento', 'insumos', 'tipo_procedimiento_medico', 'medicamentos', 'tipo_estudio', 'tipo_analisis']
chk('los 10 movimientos y los 8 referenciales tienen módulo y etiqueta de auditoría', all(e in MODULO_POR_ENTIDAD and e in ETIQUETA_ENTIDAD for e in MOVIMIENTOS + REFERENCIALES))
chk('módulos: movimientos = "Módulo Consultorio", referenciales = "Referenciales Consultorio"',
    all(MODULO_POR_ENTIDAD[e] == 'Módulo Consultorio' for e in MOVIMIENTOS) and all(MODULO_POR_ENTIDAD[e] == 'Referenciales Consultorio' for e in REFERENCIALES))
chk('los movimientos son ENTIDADES_MOVIMIENTO (su BAJA dice "Anulado") y los referenciales no', set(MOVIMIENTOS) <= ENTIDADES_MOVIMIENTO and not set(REFERENCIALES) & ENTIDADES_MOVIMIENTO)


def rutas_que_mutan(arbol):
    """Funciones decoradas con route(..., methods=[POST|PUT|PATCH|DELETE]) y si llaman a auditar / _auditar (o al ayudante  de la fábrica de referenciales, que a su vez llama a auditar)."""
    out = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.FunctionDef):
            continue
        for d in nodo.decorator_list:
            if isinstance(d, ast.Call) and getattr(d.func, 'attr', None) == 'route':
                metodos = []
                for kw in d.keywords:
                    if kw.arg == 'methods' and isinstance(kw.value, (ast.List, ast.Tuple)):
                        metodos = [e.value for e in kw.value.elts if isinstance(e, ast.Constant)]
                if set(metodos) & {'POST', 'PUT', 'PATCH', 'DELETE'}:
                    llamadas = {getattr(n.func, 'id', getattr(n.func, 'attr', '')) for n in ast.walk(nodo) if isinstance(n, ast.Call)}
                    out.append((nodo.name, metodos, bool(llamadas & {'auditar', '_auditar', 'registrar'})))
    return out


total, sin_auditar = 0, []
for f in sorted((RAIZ / 'app' / 'rutas' / 'modulo_consultorio').rglob('*.py')):
    if f.name.startswith('__'):
        continue
    for nombre, metodos, audita in rutas_que_mutan(ast.parse(f.read_text(encoding='utf-8'))):
        total += 1
        if not audita:
            sin_auditar.append(f'{f.relative_to(RAIZ)}::{nombre} {metodos}')
for s in sin_auditar:
    print('FAIL sin auditar:', s)
fallos.extend(sin_auditar)
chk(f'las {total} rutas que mutan (POST / PUT / PATCH / DELETE) de las APIs y fábricas de Consultorio llaman a auditar', total >= 25 and not sin_auditar)

print('\n=== 2. Dinámico: sin contenido clínico en ninguna fila')
SECRETO = 'RESERVADO-AUD-5150'
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


try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    tdx, sint, ttr, proc, ins, mdc, tes, tan = (fx.tipo_diagnostico(), fx.sintoma(), fx.tipo_tratamiento(), fx.tipo_procedimiento(), fx.insumo(), fx.medicamento(),
                                                 fx.tipo_estudio(), fx.tipo_analisis())
    est_dental = q("SELECT id_estado_dental FROM estado_dental WHERE aplica_a='SUPERFICIE' AND activo ORDER BY 1 LIMIT 1")[0][0]
    A = cliente(u_med)
    c1 = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec, 'en_proceso')
    fx.auditoria_de('consultas_cab', c1)
    ids = {e: [] for e in MOVIMIENTOS}

    def op(descripcion, r, entidad=None, pk=None, esperado=(200, 201)):
        ok = r.status_code in esperado
        chk(f'{descripcion} -> {r.status_code}', ok)
        if ok and entidad and pk:
            ids[entidad].append(((r.get_json() or {}).get('data') or {}).get(pk))
        return (r.get_json() or {}).get('data') if ok else None

    # ficha: alta, edición, anulación
    op('ficha: alta', A.post('/api/v1/ficha-medica', json={'id_consulta_cab': c1, 'temperatura': '36.5', 'examen_bucal': SECRETO, 'observaciones_medico': SECRETO}))
    ficha = A.get(f'/api/v1/ficha-medica/consulta/{c1}').get_json()['data']; ids['ficha_medica_consulta'].append(ficha['id_ficha_medica'])
    op('ficha: edición', A.put(f"/api/v1/ficha-medica/{ficha['id_ficha_medica']}", json={'temperatura': '37.1', 'examen_fisico_general': SECRETO}))
    op('ficha: anulación', A.delete(f"/api/v1/ficha-medica/{ficha['id_ficha_medica']}"))
    # diagnóstico
    dx = op('diagnóstico: alta', A.post('/api/v1/diagnosticos-medicos', json={'id_consulta_cab': c1, 'id_tipo_diagnostico': tdx, 'sintomas': [sint], 'descripcion_diagnostico': SECRETO,
                                                                           'observaciones': SECRETO, 'pieza_dental': '18'}), 'diagnosticos', 'id_diagnostico')
    op('diagnóstico: anulación', A.delete(f"/api/v1/diagnosticos-medicos/{dx['id_diagnostico']}"))
    # odontograma
    od = op('odontograma: alta', A.post('/api/v1/odontogramas', json={'id_consulta_cab': c1}), 'odontograma', 'id_odontograma')
    h = A.post(f"/api/v1/odontogramas/{od['id_odontograma']}/hallazgos", json={'numero_diente': 18, 'superficie': 'O', 'id_estado_dental': est_dental, 'observacion': SECRETO})
    chk(f'odontograma: agregar hallazgo -> {h.status_code}', h.status_code in (200, 201))
    det = A.get(f"/api/v1/odontogramas/{od['id_odontograma']}").get_json()['data']['hallazgos'][0]['id_odontograma_detalle']
    op('odontograma: quitar hallazgo', A.delete(f'/api/v1/odontogramas/hallazgos/{det}'))
    op('odontograma: anulación', A.delete(f"/api/v1/odontogramas/{od['id_odontograma']}"))
    # tratamiento y sesión
    tr = op('tratamiento: alta', A.post('/api/v1/tratamientos', json={'id_consulta_cab': c1, 'id_tipo_tratamiento': ttr, 'descripcion_tratamiento': SECRETO}), 'tratamientos', 'id_tratamiento')
    se = op('sesión: alta (pasa el tratamiento a en seguimiento)', A.post('/api/v1/sesiones-tratamiento', json={
        'id_tratamiento': tr['id_tratamiento'], 'id_consulta_cab': c1, 'procedimientos': [proc], 'descripcion_procedimiento': SECRETO, 'observaciones': SECRETO,
        'insumos': [{'id_insumo': ins, 'cantidad': 2}]}), 'sesiones_tratamiento', 'id_sesion')
    op('tratamiento: finalizar', A.put(f"/api/v1/tratamientos/{tr['id_tratamiento']}/finalizar"))
    tr2 = op('tratamiento 2: alta', A.post('/api/v1/tratamientos', json={'id_consulta_cab': c1, 'id_tipo_tratamiento': ttr, 'descripcion_tratamiento': SECRETO}), 'tratamientos', 'id_tratamiento')
    op('tratamiento 2: anulación', A.delete(f"/api/v1/tratamientos/{tr2['id_tratamiento']}"))
    tr3 = op('tratamiento 3: alta', A.post('/api/v1/tratamientos', json={'id_consulta_cab': c1, 'id_tipo_tratamiento': ttr, 'descripcion_tratamiento': SECRETO}), 'tratamientos', 'id_tratamiento')
    se3 = op('sesión 3: alta', A.post('/api/v1/sesiones-tratamiento', json={'id_tratamiento': tr3['id_tratamiento'], 'id_consulta_cab': c1, 'procedimientos': [proc],
                                                                          'descripcion_procedimiento': SECRETO}), 'sesiones_tratamiento', 'id_sesion')
    op('sesión 3: anulación (el tratamiento vuelve a pendiente)', A.delete(f"/api/v1/sesiones-tratamiento/{se3['id_sesion']}"))
    # receta + PDF
    rc = op('receta: alta', A.post('/api/v1/recetas', json={'id_consulta_cab': c1, 'indicaciones_generales': SECRETO, 'medicamentos': [{'id_medicamento': mdc, 'dosis': SECRETO, 'frecuencia': SECRETO,
                                                                                                                                     'duracion': SECRETO}]}), 'recetas', 'id_receta')
    op('receta: PDF', A.get(f"/api/v1/recetas/{rc['id_receta']}/pdf"))
    op('receta: anulación', A.delete(f"/api/v1/recetas/{rc['id_receta']}"))
    # órdenes
    for nombre, url, entidad, pk, tipo_col, tipo in (('orden de estudios', '/api/v1/orden-estudios', 'orden_estudios', 'id_orden_estudio', 'id_tipo_estudio', tes),
                                                     ('orden de análisis', '/api/v1/orden-analisis', 'orden_analisis', 'id_orden_analisis', 'id_tipo_analisis', tan)):
        o = op(f'{nombre}: alta', A.post(url, json={'id_consulta_cab': c1, tipo_col: tipo, 'motivo_orden': SECRETO, 'indicaciones': SECRETO}), entidad, pk)
        op(f'{nombre}: avanzar', A.put(f"{url}/{o[pk]}/estado"))
        op(f'{nombre}: PDF', A.get(f"{url}/{o[pk]}/pdf"))
        op(f'{nombre}: cancelar', A.delete(f"{url}/{o[pk]}"))
    # justificativo
    ju = op('justificativo: alta', A.post('/api/v1/justificativos', json={'id_consulta_cab': c1, 'dias_reposo': 4, 'recomendaciones': SECRETO}), 'justificativo_medico', 'id_justificativo')
    op('justificativo: generar', A.put(f"/api/v1/justificativos/{ju['id_justificativo']}/emitir"))
    op('justificativo: PDF', A.get(f"/api/v1/justificativos/{ju['id_justificativo']}/pdf"))
    op('justificativo: anulación', A.delete(f"/api/v1/justificativos/{ju['id_justificativo']}"))

    for entidad, lista in ids.items():
        for i in lista:
            if i:
                fx.auditoria_de(entidad, i)
    todas = []
    for entidad in MOVIMIENTOS:
        if entidad == 'consultas_cab':
            continue
        lista = [i for i in ids[entidad] if i]
        if lista:
            todas += q("SELECT entidad, id_registro, accion, modulo, valores_anteriores, valores_nuevos, detalle FROM auditoria_cambios WHERE entidad=%s AND id_registro = ANY(%s) ORDER BY id_auditoria_cambio", (entidad, lista))
    por_entidad = {}
    for f in todas:
        por_entidad.setdefault(f[0], []).append(f)
    chk(f'se auditaron operaciones de los 9 movimientos clínicos ({len(todas)} filas)', len(por_entidad) == 9 and len(todas) >= 25)
    chk('todas las filas tienen módulo "Módulo Consultorio" y una acción válida', all(f[3] == 'Módulo Consultorio' and f[2] in ('ALTA', 'MODIFICACION', 'BAJA', 'EXPORTACION') for f in todas))
    chk('todo ALTA trae valores_nuevos (JSON) y toda BAJA el estado Anulado', all(f[5] for f in todas if f[2] == 'ALTA') and all((f[5] or {}).get('Estado') == 'Anulado' for f in todas if f[2] == 'BAJA'))
    chk('cada cambio de estado (MODIFICACION de tratamiento, orden y justificativo) guarda el estado anterior y el nuevo',
        all(f[4] and f[5] and set(f[4]) == {'Estado'} == set(f[5]) for f in todas if f[2] == 'MODIFICACION' and f[0] in ('tratamientos', 'orden_estudios', 'orden_analisis', 'justificativo_medico')))
    chk('las descargas de PDF quedaron como EXPORTACION (receta, 2 órdenes y justificativo)', sum(1 for f in todas if f[2] == 'EXPORTACION') == 4)
    chk('el detalle de cada fila nombra el N.º de documento o la consulta y al paciente, no el contenido', all(('CON-' in f[6] or 'JUS-' in f[6] or 'OES-' in f[6] or 'OAN-' in f[6] or 'RCT-' in f[6]) for f in todas if f[2] != 'MODIFICACION' or f[0] != 'ficha_medica_consulta'))
    contenido = [f for f in todas if SECRETO in str(f[6]) or SECRETO in str(f[4]) or SECRETO in str(f[5])]
    chk(f'NINGUNA fila de auditoría ({len(todas)}) contiene los marcadores clínicos (detalle, valores anteriores ni nuevos)', not contenido)
    for f in contenido[:5]:
        print('     contenido filtrado:', f[0], f[2], str(f[6])[:100])
    # la auditoría sigue inmutable
    try:
        cu.execute("UPDATE auditoria_cambios SET detalle='x' WHERE entidad='recetas' AND id_registro=%s", (ids['recetas'][0],)); cx.commit(); inmutable = False
    except Exception:
        cx.rollback(); inmutable = True
    chk('la auditoría sigue siendo inmutable (UPDATE rechazado por el trigger, incluso como postgres)', inmutable)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
