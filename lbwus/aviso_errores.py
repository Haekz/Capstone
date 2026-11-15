"""Aviso por correo de los errores 500: lo minimo para enterarse y encontrarlos, sin datos de las personas.

Django registra cada 500 en el logger django.request. Este handler (settings.LOGGING) manda un correo corto a
settings.ERRORES_CORREOS con la pantalla (el patron de la ruta, no la direccion real: puede llevar un token), el tipo
de error y las lineas del codigo por donde paso. NO lleva el mensaje del error (los de base de datos traen datos
reales), ni parametros, ni datos enviados, ni cookies, ni el nombre o correo de quien navegaba (solo su id): el sitio
atiende a menores. El detalle completo queda en los registros de Railway.

Un mismo error en la misma pantalla avisa una vez cada 10 minutos por proceso, para que una caida no llene el buzon.
Sin ERRORES_CORREOS no hace nada.
"""
import logging
import time
import traceback

from django.conf import settings
from django.utils import timezone

from alumnos.correo import enviar

ESPERA_SEGUNDOS = 600
PASOS_A_MOSTRAR = 8
_ultimo_aviso = {}  # (tipo de error, pantalla) -> cuando se aviso por ultima vez; uno por proceso


class AvisoDeError(logging.Handler):

    def emit(self, record):
        try:
            self._avisar(record)
        except Exception:  # un fallo del aviso nunca debe tapar el error original
            self.handleError(record)

    def _avisar(self, record):
        if not settings.ERRORES_CORREOS or not record.exc_info:
            return
        tipo, _, trazado = record.exc_info
        request = getattr(record, 'request', None)
        coincidencia = getattr(request, 'resolver_match', None)
        pantalla = getattr(coincidencia, 'route', None) or '(pantalla sin identificar)'
        clave = (tipo.__name__, pantalla)
        ahora = time.monotonic()
        if ahora - _ultimo_aviso.get(clave, -ESPERA_SEGUNDOS) < ESPERA_SEGUNDOS:
            return
        _ultimo_aviso[clave] = ahora

        usuario = getattr(request, 'user', None)
        raiz = str(settings.BASE_DIR)
        marcos = traceback.extract_tb(trazado)
        propios = [m for m in marcos if m.filename.startswith(raiz)] or marcos[-3:]  # el codigo del proyecto, no el de Django
        contexto = {
            'cuando': timezone.localtime().strftime('%d-%m-%Y %H:%M'),
            'metodo': getattr(request, 'method', ''),
            'pantalla': pantalla,
            'tipo': tipo.__name__,
            'usuario_id': usuario.pk if getattr(usuario, 'is_authenticated', False) else None,
            'pasos': [f'{m.filename.replace(raiz, "")}:{m.lineno} en {m.name}' for m in propios[-PASOS_A_MOSTRAR:]],
        }
        for destino in settings.ERRORES_CORREOS:
            enviar(f'Error 500 en {pantalla}', 'correo_error.txt', contexto, destino)
