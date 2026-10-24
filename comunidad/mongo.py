"""Acceso a MongoDB Atlas con PyMongo.

Un solo MongoClient por proceso, creado de forma perezosa en la primera
llamada (seguro con los workers de Gunicorn: cada worker crea el suyo al
atender su primera peticion, despues del fork).

Si MONGODB_URI no esta definida, MongoDB queda desactivado: get_client()
lanza MongoNoConfigurado y disponible() devuelve False. El resto del sitio
funciona igual.

Regla: la URI nunca se escribe en logs, excepciones ni respuestas.
"""

import logging
import threading
import time

from django.conf import settings
from pymongo import MongoClient

from . import esquemas

logger = logging.getLogger('comunidad')

_cliente = None
_db_nombre = None  # Solo se usa cuando una prueba inyecta un cliente.
_candado = threading.Lock()


class MongoNoConfigurado(Exception):
    """MONGODB_URI no esta definida: MongoDB esta desactivado."""


def get_client():
    global _cliente
    if _cliente is None:
        with _candado:
            if _cliente is None:
                uri = getattr(settings, 'MONGODB_URI', None)
                if not uri:
                    raise MongoNoConfigurado('MONGODB_URI no está definida.')
                timeout = settings.MONGODB_TIMEOUT_MS
                _cliente = MongoClient(
                    uri,
                    serverSelectionTimeoutMS=timeout,
                    connectTimeoutMS=timeout,
                    tz_aware=True,
                    appname='lbwus',
                )
    return _cliente


def nombre_db():
    return _db_nombre or settings.MONGODB_DB


def get_db():
    return get_client()[nombre_db()]


def coleccion(nombre):
    if nombre not in esquemas.COLECCIONES:
        raise ValueError(f'Colección desconocida: {nombre!r}')
    return get_db()[nombre]


def usar_cliente(cliente, db=None):
    """Inyecta un cliente (por ejemplo mongomock.MongoClient()) en pruebas."""
    global _cliente, _db_nombre
    with _candado:
        _cliente = cliente
        _db_nombre = db


def restablecer():
    """Vuelve al estado inicial: el proximo get_client() crea uno nuevo."""
    global _cliente, _db_nombre
    with _candado:
        cliente, _cliente, _db_nombre = _cliente, None, None
    if cliente is not None:
        try:
            cliente.close()
        except Exception:  # mongomock u otro cliente sin close() real
            pass


def ping():
    """Devuelve la latencia del ping en milisegundos.

    Las excepciones de PyMongo (y MongoNoConfigurado) se propagan.
    """
    inicio = time.perf_counter()
    get_client().admin.command('ping')
    return round((time.perf_counter() - inicio) * 1000, 1)


def disponible():
    """True si MongoDB responde. Nunca lanza excepciones."""
    try:
        ping()
        return True
    except MongoNoConfigurado:
        logger.info('MongoDB no está configurado.')
    except Exception as exc:
        # Solo el nombre de la excepcion: el mensaje puede incluir el host.
        logger.warning('MongoDB no disponible: %s', type(exc).__name__)
    return False
