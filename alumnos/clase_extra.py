"""Clase extra: el alumno propone un dia y hora fuera del horario del profesor y este decide.

Pedirla exige lo mismo que reservar (paquete vigente con ese profesor; un menor, a traves de su apoderado)
y que la hora quede de verdad fuera de lo que el profesor ya ofrece. El modelo y el plazo: models/clase_extra.py.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from agenda.models import HorarioSemanal

from . import avisos_profesor
from .exceptions import SolicitudExtraError
from .models import Inscripcion, SesionClase, SolicitudClaseExtra
from .services import _paquete_con_clases, exigir_mayor_de_edad

MAXIMO_MENSAJE = 500


def _dentro_del_horario(profesor, inicio, fin):
    """La hora cae en una franja semanal del profesor, o ya hay un bloque libre suyo que se cruza.

    Una franja cuenta aunque todavia no tenga bloques (las proximas 4 semanas son las unicas que se crean).
    """
    local = timezone.localtime(inicio)
    en_una_franja = HorarioSemanal.objects.filter(
        profesor=profesor, dia_semana=local.weekday(), hora_inicio__lte=local.time(), hora_fin__gt=local.time(),
    ).exists()
    return en_una_franja or SesionClase.objects.disponibles().filter(
        clase__profesor=profesor, fecha_hora_inicio__lt=fin, fecha_hora_fin__gt=inicio,
    ).exists()


def _exigir_que_se_pueda_pedir(alumno, clase, inicio, ahora):
    """Las reglas que no necesitan bloquear nada, de la mas barata a la que consulta la base."""
    exigir_mayor_de_edad(alumno)
    profesor = clase.profesor
    if not profesor.puede_hacer_clases:
        raise SolicitudExtraError('Este profesor aún no tiene su título validado.')
    local = timezone.localtime(inicio)
    if local.minute or local.second or local.microsecond:
        raise SolicitudExtraError('Elige una hora en punto (por ejemplo 15:00): cada clase dura 60 minutos.')
    anticipacion = SolicitudClaseExtra.ANTICIPACION_MINIMA
    if inicio - ahora < anticipacion:
        raise SolicitudExtraError(
            f'Pide la clase con al menos {int(anticipacion.total_seconds() // 3600)} horas de anticipación.')
    fin = inicio + SolicitudClaseExtra.DURACION
    if Inscripcion.objects.que_se_cruzan(profesor, inicio, fin).exists():
        raise SolicitudExtraError('El profesor ya tiene una clase a esa hora. Elige otro horario.')
    if _dentro_del_horario(profesor, inicio, fin):
        raise SolicitudExtraError(
            'Esa hora ya es parte de los horarios del profesor: reserva uno de sus bloques disponibles.')


def solicitar(alumno, clase, inicio, mensaje='', ahora=None):
    """Registra el pedido y le avisa al profesor. Devuelve la solicitud pendiente.

    Lanza SolicitudExtraError (o los errores de reserva: menor de edad, sin clases en un paquete) con un
    mensaje que se le puede mostrar tal cual al alumno.
    """
    ahora = ahora or timezone.now()
    _exigir_que_se_pueda_pedir(alumno, clase, inicio, ahora)
    repetida = SolicitudExtraError('Ya pediste esa clase extra y el profesor aún no responde.')
    with transaction.atomic():
        _paquete_con_clases(alumno, clase.profesor, inicio)  # solo comprueba: el cupo se gasta al aceptar
        try:
            with transaction.atomic():  # la restriccion unica de la base detecta el pedido repetido
                solicitud = SolicitudClaseExtra.objects.create(
                    alumno=alumno, clase=clase, fecha_hora_inicio=inicio, mensaje=mensaje.strip()[:MAXIMO_MENSAJE],
                    vence_el=SolicitudClaseExtra.plazo(ahora, inicio),
                )
        except IntegrityError as exc:
            raise repetida from exc
        transaction.on_commit(lambda: avisos_profesor.clase_extra_solicitada(solicitud))
    return solicitud
