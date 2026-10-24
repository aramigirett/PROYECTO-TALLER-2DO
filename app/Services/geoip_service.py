"""Validación de IP por país con una base GeoIP LOCAL (sin APIs externas: funciona sin internet y no demora el login).

Base: DB-IP Lite Country (https://db-ip.com, licencia CC-BY 4.0), archivo .mmdb en la ruta GEOIP_DB_PATH del .env.
Las IP privadas, loopback y link-local son la red interna de la clínica y siempre se permiten sin consultar la base.

evaluar_ip(ip) devuelve un dict {estado, pais, permitido}; estado es uno de:
  INTERNA          IP privada/loopback/link-local            -> permitido
  PERMITIDA        el país detectado es PAIS_PERMITIDO       -> permitido
  NO_PERMITIDA     el país detectado es otro                 -> rechazado
  SIN_GEOLOCALIZAR IP pública que la base no resuelve, o base ausente/ilegible -> permitido (se audita)
"""
import ipaddress
import os
import pathlib
import threading

from flask import current_app

RAIZ = pathlib.Path(__file__).resolve().parents[2]

ESTADO_INTERNA = 'INTERNA'
ESTADO_PERMITIDA = 'PERMITIDA'
ESTADO_NO_PERMITIDA = 'NO_PERMITIDA'
ESTADO_SIN_GEOLOCALIZAR = 'SIN_GEOLOCALIZAR'

_lock = threading.Lock()
_lector = None          # maxminddb.Reader abierto
_lector_ruta = None     # ruta con la que se abrió (si cambia el .env en un test, se reabre)
_aviso_emitido = False  # el aviso de "base no disponible" se loguea una sola vez


def pais_permitido():
    return (os.environ.get('PAIS_PERMITIDO') or 'PY').strip().upper()


def _ruta_base():
    ruta = pathlib.Path(os.environ.get('GEOIP_DB_PATH') or 'geoip/dbip-country-lite.mmdb')
    return ruta if ruta.is_absolute() else RAIZ / ruta


def _abrir_lector():
    global _lector, _lector_ruta, _aviso_emitido
    ruta = _ruta_base()
    with _lock:
        if _lector is not None and _lector_ruta == ruta:
            return _lector
        _lector = None
        try:
            import maxminddb
            _lector = maxminddb.open_database(str(ruta))
            _lector_ruta = ruta
            _aviso_emitido = False
        except Exception as e:  # archivo ausente, ilegible o librería no instalada
            if not _aviso_emitido:
                current_app.logger.warning(
                    f"Base GeoIP no disponible ({ruta}): {e}. Las IP públicas se tratarán como SIN_GEOLOCALIZAR."
                )
                _aviso_emitido = True
        return _lector


def cerrar_lector():
    """Cierra la base abierta (los tests la usan para forzar una reapertura)."""
    global _lector, _lector_ruta
    with _lock:
        if _lector is not None:
            _lector.close()
        _lector = None
        _lector_ruta = None


def normalizar_ip(ip):
    """ipaddress.ip_address, con las IPv4 mapeadas en IPv6 (::ffff:a.b.c.d) reducidas a IPv4. None si no es una IP válida."""
    try:
        direccion = ipaddress.ip_address((ip or '').strip())
    except ValueError:
        return None
    if direccion.version == 6 and direccion.ipv4_mapped:
        return direccion.ipv4_mapped
    return direccion


def es_ip_interna(ip):
    direccion = normalizar_ip(ip)
    return bool(direccion and (direccion.is_private or direccion.is_loopback or direccion.is_link_local))


def pais_de_ip(ip):
    """Código ISO de 2 letras del país de la IP, o None si la base no la resuelve o no está disponible."""
    direccion = normalizar_ip(ip)
    lector = _abrir_lector()
    if direccion is None or lector is None:
        return None
    try:
        registro = lector.get(str(direccion))
    except Exception:
        return None
    if not registro:
        return None
    pais = (registro.get('country') or registro.get('registered_country') or {}).get('iso_code')
    return pais.upper() if pais else None


def ip_efectiva(ip_real):
    """La IP del cliente; con la app en modo debug, IP_SIMULADA del .env la reemplaza (solo para probar)."""
    simulada = (os.environ.get('IP_SIMULADA') or '').strip()
    if simulada and current_app.debug:
        return simulada
    return ip_real


def evaluar_ip(ip):
    if normalizar_ip(ip) is None:
        # Sin IP reconocible no se puede decidir: se trata como no geolocalizable (se permite y se audita)
        return {'estado': ESTADO_SIN_GEOLOCALIZAR, 'pais': None, 'permitido': True}
    if es_ip_interna(ip):
        return {'estado': ESTADO_INTERNA, 'pais': None, 'permitido': True}
    pais = pais_de_ip(ip)
    if pais is None:
        return {'estado': ESTADO_SIN_GEOLOCALIZAR, 'pais': None, 'permitido': True}
    if pais == pais_permitido():
        return {'estado': ESTADO_PERMITIDA, 'pais': pais, 'permitido': True}
    return {'estado': ESTADO_NO_PERMITIDA, 'pais': pais, 'permitido': False}
