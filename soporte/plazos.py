"""Plazos de los tickets en dias habiles de Chile: sin sabados, domingos ni feriados."""

from datetime import datetime, time, timedelta
from functools import lru_cache

import holidays
from django.utils import timezone


@lru_cache(maxsize=None)
def _feriados(anio):
    return holidays.country_holidays('CL', years=anio)


def es_habil(dia):
    return dia.weekday() < 5 and dia not in _feriados(dia.year)


def vencimiento(desde, dias_habiles):
    """Fin del dia habil numero ``dias_habiles`` despues de ``desde``, en hora de Chile.

    El dia en que se abre no cuenta: abierto un viernes con 1 dia, vence el lunes
    a las 23:59 (o el martes si el lunes es feriado).
    """
    dia = timezone.localdate(desde)
    while dias_habiles:
        dia += timedelta(days=1)
        if es_habil(dia):
            dias_habiles -= 1
    return timezone.make_aware(datetime.combine(dia, time(23, 59, 59)))
