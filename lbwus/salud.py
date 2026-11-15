"""Direccion de salud: responde si el sitio y su base de datos funcionan (para el monitor de Railway o uno externo).

Sin detalles: no dice por que falla ni expone datos. Esta exenta de la puerta con clave (lbwus/puerta.py).
"""
import logging

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)


@never_cache
@require_safe
def salud(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:  # base caida o sin conexion: el monitor solo necesita saber que no responde
        logger.warning('Salud: la base de datos no responde', exc_info=True)
        return JsonResponse({'estado': 'sin base de datos'}, status=503)
    return JsonResponse({'estado': 'ok'})
