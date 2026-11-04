"""Avisos al profesor cuando le reservan, cancelan o reagendan (paso B2b, decidido 02-nov).

Correo + campanita. Privacidad: solo el nombre de pila del alumno, aunque actue
su apoderado (el profesor no recibe datos del apoderado). InscripcionService los
llama con transaction.on_commit: si la operacion se deshace, no sale ningun aviso.
Un fallo del correo no afecta la campanita ni la reserva (correo.enviar lo registra).
"""

from django.urls import reverse
from django.utils import timezone

from notificaciones.models import notificar

from .correo import enviar


def _fecha(sesion):
    return timezone.localtime(sesion.fecha_hora_inicio).strftime('%d/%m/%Y a las %H:%M')


def _avisar(inscripcion, asunto, texto):
    user = inscripcion.clase.profesor.user
    notificar(user, texto, reverse('panel_profesor'))
    enviar(asunto, 'alumnos/correo_aviso_profesor.txt', {'nombre': user.first_name, 'texto': texto}, user.email)


def _quien_y_que(inscripcion):
    return inscripcion.alumno.user.first_name, inscripcion.clase.asignatura.nombre


def reserva(inscripcion):
    alumno, asignatura = _quien_y_que(inscripcion)
    _avisar(inscripcion, 'Nueva reserva', f'{alumno} reservó {asignatura} para el {_fecha(inscripcion.sesion)}.')


def cancelacion(inscripcion):
    alumno, asignatura = _quien_y_que(inscripcion)
    cuando = f' del {_fecha(inscripcion.sesion)}' if inscripcion.sesion_id else ''
    texto = f'{alumno} canceló {asignatura}{cuando}.'
    if inscripcion.estado == inscripcion.ESTADO_CANCELADA_TARDE:
        texto += ' Fue con menos de 4 horas: la clase se te paga igual.'
    _avisar(inscripcion, 'Clase cancelada', texto)


def reagenda(inscripcion, sesion_anterior):
    alumno, asignatura = _quien_y_que(inscripcion)
    _avisar(inscripcion, 'Clase reagendada',
            f'{alumno} movió {asignatura} del {_fecha(sesion_anterior)} al {_fecha(inscripcion.sesion)}.')
