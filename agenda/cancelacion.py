"""El profesor cancela una clase reservada (paso A3b, decidido 02-nov).

- Con 12 horas o mas de anticipacion; antes, primero conversa con el alumno (C1/C2).
- La clase vuelve al paquete del alumno (el estado `cancelada` no cuenta como usada).
- Se cierra esa hora completa, en todas las asignaturas del profesor: avisó que no puede.
- Avisa al alumno adulto, o al apoderado si es menor (agenda/avisos_alumno.py).
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from alumnos.exceptions import InscripcionError
from alumnos.models import Inscripcion, Profesor, SesionClase

from . import avisos_alumno

ANTICIPACION = timedelta(hours=12)


def a_tiempo(sesion, ahora=None):
    """Faltan 12 h o mas para que empiece."""
    return sesion.fecha_hora_inicio - (ahora or timezone.now()) >= ANTICIPACION


def _cerrar_la_hora(sesion):
    """Cancela los bloques del profesor que se cruzan con la hora y no tienen reservas activas."""
    SesionClase.objects.filter(
        clase__profesor=sesion.clase.profesor_id, estado=SesionClase.ESTADO_PROGRAMADA,
        fecha_hora_inicio__lt=sesion.fecha_hora_fin, fecha_hora_fin__gt=sesion.fecha_hora_inicio,
    ).exclude(inscripciones__estado__in=Inscripcion.ESTADOS_ACTIVOS).update(estado=SesionClase.ESTADO_CANCELADA)


def cancelar(profesor, inscripcion_id):
    """Cancela la reserva (solo si es de una clase suya). Devuelve la inscripcion cancelada."""
    with transaction.atomic():
        # Mismo bloqueo que al reservar (B1a): nadie toma otro bloque de esa hora mientras se cierra.
        Profesor.objects.select_for_update().get(pk=profesor.pk)
        try:
            inscripcion = Inscripcion.objects.select_for_update().get(
                pk=inscripcion_id, clase__profesor=profesor, sesion__isnull=False)
        except Inscripcion.DoesNotExist as exc:
            raise InscripcionError('Reserva no encontrada.') from exc
        if not inscripcion.puede_cancelar:
            raise InscripcionError('Esta clase ya comenzó o no está activa: no se puede cancelar.')
        if not a_tiempo(inscripcion.sesion):
            raise InscripcionError('Solo puedes cancelar con 12 horas de anticipación o más. '
                                   'Conversa con el alumno o su apoderado.')
        inscripcion.estado = Inscripcion.ESTADO_CANCELADA
        inscripcion.save(update_fields=['estado'])
        _cerrar_la_hora(inscripcion.sesion)
        transaction.on_commit(lambda: avisos_alumno.cancelacion_del_profesor(inscripcion))
        return inscripcion
