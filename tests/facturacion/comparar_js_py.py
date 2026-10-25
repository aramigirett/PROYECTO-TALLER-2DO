"""Compara las salidas del JS (ejecutado con JScript) contra utils.py para los mismos casos."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app.rutas.modulo_facturacion import utils as u

ruta = sys.argv[1]
filas = [l.split('\t') for l in open(ruta, encoding='utf-8-sig').read().split('\n') if l.strip('\r')]
fallos = 0
def py(tipo, entrada):
    if tipo == 'ciRuc': return u.validar_ci_ruc(entrada)[1] or ''
    if tipo == 'dv': return str(u.calcular_dv_ruc(entrada))
    if tipo == 'nombre': return u.validar_nombre(entrada, 'nombre', True)[1] or ''
    if tipo == 'apellido': return u.validar_nombre(entrada, 'apellido', False)[1] or ''
    if tipo == 'telOpc': return u.validar_telefono_opcional(entrada)[1] or ''
    if tipo == 'corOpc': return u.validar_correo_opcional(entrada)[1] or ''
    if tipo == 'monto': return u.validar_monto(entrada)[1] or ''
    if tipo == 'cantPos': return u.validar_cantidad_positiva(entrada)[1] or ''
    if tipo == 'observacion': return u.validar_observacion(entrada)[1] or ''
    if tipo == 'montoPos': return u.validar_monto_positivo(entrada)[1] or ''
    if tipo == 'codigo': return (u.validar_codigo(entrada, 'referencia', 30, True)[1] or '') + '|' + (u.validar_codigo(entrada, 'referencia', 30, False)[1] or '')
    if tipo == 'ultDig': return u.validar_ultimos_digitos(entrada)[1] or ''
    if tipo == 'nroCuenta': return u.validar_numero_cuenta(entrada)[1] or ''
    if tipo == 'presentacion': return u.validar_presentacion(entrada)[1] or ''
    if tipo == 'descMed': return u.normalizar_descripcion({'nombre_comercial': entrada}, 200, True, 'nombre_comercial', 'nombre comercial', 'El')[1] or ''
    if tipo == 'ubicacion': return None
for f in filas:
    tipo, entrada, js = f[0], f[1], (f[2].rstrip('\r') if len(f) > 2 else '')
    esperado = py(tipo, entrada)
    if esperado is None:
        continue
    ok = esperado == js
    fallos += (not ok)
    print(('OK  ' if ok else 'DIFF'), tipo, repr(entrada), '->', repr(js) if ok else f'JS={js!r} PY={esperado!r}')
print('DIFERENCIAS:', fallos, 'de', len(filas))
