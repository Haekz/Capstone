"""Proximos horarios libres de cada profesor, para la tira de dias de la lista de profesores.

Una sola consulta para todos los profesores de la lista (no una por tarjeta). Usa los mismos
criterios que la ventana de horarios, ``SesionClase.disponibles()``: programada, a futuro, con
cupo y con el profesor libre. Fechas y horas en hora local de Chile.
"""

from datetime import datetime, time, timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

from alumnos.models import Inscripcion, SesionClase

DIAS_DE_LA_TIRA = 7


def proximos_horarios(profesores, dias=DIAS_DE_LA_TIRA, alumno=None):
    """{id_profesor: [{id_sesion, asignatura, fecha 'AAAA-MM-DD', hora 'HH:MM'}, ...]}, por inicio.

    Cubre hoy y los ``dias - 1`` siguientes (dias locales completos). Todo profesor recibido
    aparece, con lista vacia si no tiene horarios. Con ``alumno``, deja fuera lo que ya reservo.
    """
    horarios = {profesor.id_profesor: [] for profesor in profesores}
    if not horarios:
        return horarios
    limite = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=dias), time.min))
    sesiones = (
        SesionClase.objects.disponibles()
        .filter(clase__profesor__in=horarios, fecha_hora_inicio__lt=limite)
        .select_related('clase__asignatura')
        .order_by('fecha_hora_inicio')
    )
    if alumno is not None:
        reservada = Inscripcion.objects.filter(
            alumno=alumno, sesion=OuterRef('pk'), estado__in=[Inscripcion.ESTADO_CONFIRMADA, Inscripcion.ESTADO_PENDIENTE],
        )
        sesiones = sesiones.exclude(Exists(reservada))
    for sesion in sesiones:
        local = sesion.inicio_local
        horarios[sesion.clase.profesor_id].append({
            'id_sesion': sesion.pk,
            'asignatura': sesion.clase.asignatura.nombre,
            'fecha': local.strftime('%Y-%m-%d'),
            'hora': local.strftime('%H:%M'),
        })
    return horarios
