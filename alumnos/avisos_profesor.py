"""Avisos al profesor cuando le reservan, cancelan o reagendan (paso B2b, decidido 02-nov).

Correo + campanita. Privacidad: solo el nombre de pila del alumno, aunque actue
su apoderado (el profesor no recibe datos del apoderado). InscripcionService los
llama con transaction.on_commit: si la operacion se deshace, no sale ningun aviso.
Un fallo del correo no afecta la campanita ni la reserva (correo.enviar lo registra).

Tambien la bienvenida al registrarse, por cualquiera de los dos caminos (formulario o Google).

Y lo que soporte decide sobre su titulo o una especializacion (fase 5, decidido 07-nov). El motivo de un
rechazo no va ni en la campanita ni en el correo: se lee solo en el panel (como en los escalamientos).
"""

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from notificaciones.models import notificar

from .correo import enviar


def bienvenida(user):
    """Correo de bienvenida al profesor nuevo. Sale solo si el registro se confirma."""
    transaction.on_commit(lambda: enviar('Te damos la bienvenida al equipo docente',
                                         'alumnos/correo_bienvenida_profesor.txt',
                                         {'nombre': user.first_name}, user.email))


def _asignaturas(clases):
    """Fin del aviso: que asignaturas nuevas quedo dictando (nada si no hay)."""
    return f' Asignaturas nuevas: {", ".join(c.asignatura.nombre for c in clases)}.' if clases else ''


def _decision(user, asunto, texto):
    notificar(user, texto, reverse('panel_profesor'))
    enviar(asunto, 'alumnos/correo_decision_profesor.txt', {'nombre': user.first_name, 'texto': texto}, user.email)


def titulo(profesor, aprobado, clases_nuevas=()):
    """Soporte decidio su titulo. Sale solo si la decision se confirma (on_commit)."""
    if aprobado:
        texto = f'Tu título profesional fue aprobado. Ya puedes hacer clases.{_asignaturas(clases_nuevas)}'
    else:
        texto = 'Tu título profesional fue rechazado. Revisa el motivo en tu panel y vuelve a subirlo.'
    transaction.on_commit(lambda: _decision(profesor.user, 'Tu título fue revisado', texto))


def especializacion(especializacion, aprobada, clases_nuevas=()):
    """Soporte decidio una especializacion. Sale solo si la decision se confirma (on_commit)."""
    nombre = f'«{especializacion.nombre}»'
    if aprobada:
        texto = f'Tu especialización {nombre} fue aprobada.{_asignaturas(clases_nuevas)}'
    else:
        texto = f'Tu especialización {nombre} fue rechazada. Revisa el motivo en tu panel.'
    transaction.on_commit(lambda: _decision(especializacion.profesor.user, 'Tu especialización fue revisada', texto))


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
