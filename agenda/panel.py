"""Datos de la seccion "Mi agenda" del panel del profesor (paso B1c, decidido 02-nov).

Privacidad: de cada reserva solo el nombre de pila del alumno y la asignatura.
"""

from datetime import time, timedelta

from django.db.models import Prefetch
from django.utils import timezone

from alumnos.models import Inscripcion, SesionClase

from . import cancelacion
from .bloques import SEMANAS
from .models import HorarioSemanal

HORAS = [time(h) for h in range(6, 24)]  # opciones del formulario, en punto


def agenda(profesor, ahora=None):
    """Una fila por hora con bloques en las proximas 4 semanas: libre o con sus reservas."""
    ahora = ahora or timezone.now()
    sesiones = (
        SesionClase.objects.filter(clase__profesor=profesor, fecha_hora_inicio__gt=ahora,
                                   fecha_hora_inicio__lte=ahora + timedelta(weeks=SEMANAS))
        .exclude(estado=SesionClase.ESTADO_CANCELADA)
        .select_related('clase__asignatura')
        .prefetch_related(Prefetch(
            'inscripciones', to_attr='activas',
            queryset=Inscripcion.objects.filter(estado__in=Inscripcion.ESTADOS_ACTIVOS).select_related('alumno__user'),
        ))
    )
    filas = {}
    for sesion in sesiones:  # ya vienen por fecha (Meta.ordering)
        fila = filas.setdefault(sesion.fecha_hora_inicio, {'inicio': sesion.inicio_local, 'reservas': []})
        fila['reservas'] += [{'id': i.pk, 'alumno': i.alumno.user.first_name, 'asignatura': sesion.clase.asignatura.nombre,
                              'puede_cancelar': cancelacion.a_tiempo(sesion, ahora)}
                             for i in sesion.activas]
    return list(filas.values())


def contexto(profesor):
    return {
        'franjas': HorarioSemanal.objects.filter(profesor=profesor),
        'agenda_filas': agenda(profesor),
        'dias_semana': HorarioSemanal.DIAS,
        'horas_agenda': HORAS,
        'semanas_agenda': SEMANAS,
    }
