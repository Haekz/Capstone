"""Recordatorios de clase (21-nov): 24 y 2 horas antes, al alumno (o a sus apoderados) y al profesor.

Los envia `manage.py enviar_recordatorios_clases`, que corre cada 15 minutos en su propio servicio Cron (el de
`tareas_diarias` corre una vez al dia). Cada reserva lleva dos marcas (Inscripcion.recordatorio_1d y _2h): cuando se
avisó, o se dio por innecesario porque se reservo ya dentro de esa ventana: una reserva con menos de 24 h no recibe el
de un dia, que llegaria minutos despues de la confirmacion. Reagendar las reinicia.

Ventanas: el de un dia sale cuando faltan entre 2 y 24 h; el de dos horas, cuando faltan menos de 2 h. El texto dice
«en menos de»: es cierto aunque el Cron se atrase.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from agenda import avisos_alumno

from . import avisos_profesor
from .models import Inscripcion, SesionClase

logger = logging.getLogger(__name__)

UN_DIA = timedelta(hours=24)
DOS_HORAS = timedelta(hours=2)
CAMPOS = ('recordatorio_1d', 'recordatorio_2h')


def marcas_al_agendar(inicio, ahora=None):
    """Marcas de una reserva nueva o reagendada: queda hecho `ahora` lo que la clase ya tiene mas cerca que esa ventana."""
    ahora = ahora or timezone.now()
    falta = inicio - ahora
    return {'recordatorio_1d': ahora if falta <= UN_DIA else None,
            'recordatorio_2h': ahora if falta <= DOS_HORAS else None}


def _recordar(pk, campo, plazo, ahora):
    """Avisa y marca, todo o nada: si algo falla antes de marcar, la proxima corrida reintenta sin duplicar la campanita.

    Bloquea la reserva (skip_locked: si otra corrida la tiene, la deja) y vuelve a mirar la marca con el bloqueo puesto.
    """
    with transaction.atomic():
        inscripcion = (Inscripcion.objects.select_for_update(skip_locked=True, of=('self',))
                       .select_related('alumno__user', 'clase__asignatura', 'clase__profesor__user', 'sesion')
                       .filter(pk=pk, **{f'{campo}__isnull': True}).first())
        if inscripcion is None:
            return False
        avisos_alumno.recordatorio(inscripcion, plazo)
        avisos_profesor.recordatorio(inscripcion, plazo)
        setattr(inscripcion, campo, ahora)
        inscripcion.save(update_fields=[campo])
        return True


def enviar_pendientes(ahora=None):
    """Envia los recordatorios que tocan. Devuelve (de_un_dia, de_dos_horas, fallidos).

    Una reserva que falla no frena a las demas: se registra y se reintenta en la proxima corrida.
    """
    ahora = ahora or timezone.now()
    en_ventana = Inscripcion.objects.filter(
        estado=Inscripcion.ESTADO_CONFIRMADA, sesion__estado=SesionClase.ESTADO_PROGRAMADA,
        sesion__fecha_hora_inicio__gt=ahora, sesion__fecha_hora_inicio__lte=ahora + UN_DIA)
    grupos = (('recordatorio_2h', '2 horas', en_ventana.filter(sesion__fecha_hora_inicio__lte=ahora + DOS_HORAS)),
              ('recordatorio_1d', '24 horas', en_ventana.filter(sesion__fecha_hora_inicio__gt=ahora + DOS_HORAS)))
    enviados, fallidos = {}, 0
    for campo, plazo, consulta in grupos:
        enviados[campo] = 0
        for pk in consulta.filter(**{f'{campo}__isnull': True}).values_list('pk', flat=True):
            try:
                enviados[campo] += _recordar(pk, campo, plazo, ahora)
            except Exception:  # aislar cada reserva: una caida no debe dejar sin aviso a las demas
                logger.exception('evento=recordatorio_fallido inscripcion=%s plazo=%s', pk, plazo)
                fallidos += 1
    return enviados['recordatorio_1d'], enviados['recordatorio_2h'], fallidos
