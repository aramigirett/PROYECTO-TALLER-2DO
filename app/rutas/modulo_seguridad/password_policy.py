import re

# Política de complejidad de contraseñas (alta/edición de usuario y recuperación).
# Mantener sincronizada con las reglas de la lista en tiempo real de usuario-index.html.
MIN_LENGTH = 8

REQUISITOS = [
    (f'Al menos {MIN_LENGTH} caracteres', lambda p: len(p) >= MIN_LENGTH),
    ('Una letra mayúscula', lambda p: re.search(r'[A-ZÁÉÍÓÚÑ]', p) is not None),
    ('Un número', lambda p: re.search(r'\d', p) is not None),
    ('Un símbolo (por ejemplo ! @ # $ % & *)', lambda p: re.search(r'[^\w\s]|_', p) is not None),
]


def validar_password_compleja(password):
    """
    Retorna None si la contraseña cumple la política; si no, un mensaje con
    los requisitos que faltan.
    """
    faltantes = [texto for texto, cumple in REQUISITOS if not cumple(password or '')]
    if not faltantes:
        return None
    return 'La contraseña debe tener: ' + '; '.join(t[0].lower() + t[1:] for t in faltantes) + '.'
