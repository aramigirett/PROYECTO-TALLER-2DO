"""Número a letras (app/Services/numero_letras.py): función pura, sin base de datos."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app.Services.numero_letras import numero_a_letras, monto_en_letras

fallos = []

def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)

CASOS = [
    (0, 'CERO'), (1, 'UNO'), (2, 'DOS'), (10, 'DIEZ'), (15, 'QUINCE'), (16, 'DIECISÉIS'), (20, 'VEINTE'),
    (21, 'VEINTIUNO'), (22, 'VEINTIDÓS'), (23, 'VEINTITRÉS'), (26, 'VEINTISÉIS'), (30, 'TREINTA'),
    (31, 'TREINTA Y UNO'), (45, 'CUARENTA Y CINCO'), (99, 'NOVENTA Y NUEVE'),
    (100, 'CIEN'), (101, 'CIENTO UNO'), (110, 'CIENTO DIEZ'), (121, 'CIENTO VEINTIUNO'), (200, 'DOSCIENTOS'),
    (500, 'QUINIENTOS'), (999, 'NOVECIENTOS NOVENTA Y NUEVE'),
    (1000, 'MIL'), (1001, 'MIL UNO'), (2000, 'DOS MIL'), (15000, 'QUINCE MIL'), (21000, 'VEINTIÚN MIL'),
    (21001, 'VEINTIÚN MIL UNO'), (31000, 'TREINTA Y UN MIL'), (100000, 'CIEN MIL'), (101000, 'CIENTO UN MIL'),
    (200000, 'DOSCIENTOS MIL'), (201000, 'DOSCIENTOS UN MIL'), (77000, 'SETENTA Y SIETE MIL'),
    (1_000_000, 'UN MILLÓN'), (1_000_001, 'UN MILLÓN UNO'), (1_500_000, 'UN MILLÓN QUINIENTOS MIL'),
    (2_000_000, 'DOS MILLONES'), (21_000_000, 'VEINTIÚN MILLONES'), (21_500_000, 'VEINTIÚN MILLONES QUINIENTOS MIL'),
    (31_000_000, 'TREINTA Y UN MILLONES'), (100_000_000, 'CIEN MILLONES'),
    (101_000_000, 'CIENTO UN MILLONES'), (1_000_000_000, 'MIL MILLONES'),
    (999_999_999_999, 'NOVECIENTOS NOVENTA Y NUEVE MIL NOVECIENTOS NOVENTA Y NUEVE MILLONES '
                      'NOVECIENTOS NOVENTA Y NUEVE MIL NOVECIENTOS NOVENTA Y NUEVE'),
]
for n, esperado in CASOS:
    obtenido = numero_a_letras(n)
    chk(f'{n:,}'.replace(',', '.') + f' -> {esperado}' + ('' if obtenido == esperado else f'  (obtuvo: {obtenido})'), obtenido == esperado)

chk('monto_en_letras(200000) = "SON GUARANÍES: DOSCIENTOS MIL."', monto_en_letras(200000) == 'SON GUARANÍES: DOSCIENTOS MIL.')
chk('monto_en_letras acepta Decimal/numérico entero', monto_en_letras(77000) == 'SON GUARANÍES: SETENTA Y SIETE MIL.')

def lanza(valor):
    try:
        numero_a_letras(valor); return False
    except ValueError:
        return True
chk('rechaza negativos', lanza(-1))
chk('rechaza más de 999.999.999.999', lanza(1_000_000_000_000))
chk('rechaza decimales, textos, None y booleanos', lanza(1.5) and lanza('10') and lanza(None) and lanza(True))

# toda la salida es mayúscula y sin dobles espacios
muestra = [numero_a_letras(n) for n in (0, 7, 18, 99, 100, 1234, 56789, 1_234_567, 99_999_999)]
chk('salida en mayúsculas y sin espacios dobles ni al borde', all(s == s.upper() and '  ' not in s and s == s.strip() for s in muestra))

print()
print('FALLOS:', 'ninguno' if not fallos else fallos)
sys.exit(1 if fallos else 0)
