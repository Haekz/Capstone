"""Salud del sitio para un monitor externo (SCRUM-100): ¿corrio tareas_diarias en las ultimas 26 horas?

La hora de la ultima corrida completa (todas las tareas sin error) se guarda en la cache compartida
(DatabaseCache, tabla ``lbwus_cache_table`` de PostgreSQL): sobrevive a despliegues y reinicios, y la leen
tanto el servicio Cron que la escribe como el servicio web que la consulta. Sin migraciones.

Si la entrada se pierde (la cache se limpia o se poda al pasar MAX_ENTRIES), la salud dice "atrasado"
hasta la proxima corrida completa: una falsa alarma, nunca un falso "ok".
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)

CLAVE_ULTIMA_CORRIDA = 'salud_tareas_diarias_ultima_corrida'
ATRASO_MAXIMO = timedelta(hours=26)  # el Cron corre cada 24 h: 2 h de margen por demoras del propio Cron
# La entrada vence sola: pasado este plazo ya estaria atrasada igual, y no queda una hora vieja para siempre.
DURACION_ENTRADA = 7 * 24 * 60 * 60

# Recordatorios de clase (enviar_recordatorios_clases): su Cron corre cada 15 min. Solo cuenta con SALUD_RECORDATORIOS.
CLAVE_ULTIMOS_RECORDATORIOS = 'salud_recordatorios_ultima_corrida'
ATRASO_RECORDATORIOS = timedelta(hours=1)  # 45 min de margen sobre los 15 de la frecuencia


def marcar_corrida(cuando=None):
    cache.set(CLAVE_ULTIMA_CORRIDA, cuando or timezone.now(), DURACION_ENTRADA)


def marcar_recordatorios(cuando=None):
    cache.set(CLAVE_ULTIMOS_RECORDATORIOS, cuando or timezone.now(), DURACION_ENTRADA)


def _leer(clave):
    """La hora guardada en `clave`, o None si no hay registro o la cache no responde."""
    try:
        return cache.get(clave)
    except Exception as error:  # base caida: el monitor debe ver "atrasado", no un 500
        logger.error('evento=salud_cache_no_disponible error=%s', type(error).__name__)
        return None


def ultima_corrida():
    """Fecha y hora (UTC) de la ultima corrida completa, o None si no hay registro o la cache no responde."""
    return _leer(CLAVE_ULTIMA_CORRIDA)


def tareas_atrasadas(ahora=None):
    ultima = ultima_corrida()
    return ultima is None or (ahora or timezone.now()) - ultima > ATRASO_MAXIMO


def recordatorios_atrasados(ahora=None):
    ultima = _leer(CLAVE_ULTIMOS_RECORDATORIOS)
    return ultima is None or (ahora or timezone.now()) - ultima > ATRASO_RECORDATORIOS


@never_cache
@require_safe  # GET y HEAD: los monitores gratuitos (UptimeRobot) consultan con HEAD
def salud(request):
    """Publica, sin login ni puerta. Solo dice "ok" o "atrasado": ningun otro dato interno."""
    if tareas_atrasadas() or (settings.SALUD_RECORDATORIOS and recordatorios_atrasados()):
        return JsonResponse({'estado': 'atrasado'}, status=503)
    return JsonResponse({'estado': 'ok'})
