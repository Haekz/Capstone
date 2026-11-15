"""Aviso al alumno (o a su apoderado) cuando su profesor cancela (paso A3b, decidido 02-nov).

Correo + campanita. Un alumno menor no recibe nada: avisa a sus apoderados con vinculo
verificado. Privacidad: no lleva ningun dato del profesor, solo la asignatura y la fecha.
"""

from django.urls import reverse
from django.utils import timezone

from alumnos.correo import enviar
from alumnos.utils import es_menor
from apoderados.models import Vinculo
from notificaciones.models import notificar

PLANTILLA = 'agenda/correo_aviso_alumno.txt'


def _destinatarios(alumno):
    """(usuario, enlace, de_quien) de cada persona a quien avisar."""
    if not es_menor(alumno.user):
        return [(alumno.user, reverse('alumno_pag1'), '')]
    vinculos = Vinculo.objects.filter(alumno=alumno, estado=Vinculo.VERIFICADO).select_related('apoderado__user')
    return [(v.apoderado.user, reverse('apoderado_clases_estudiante', args=[v.pk]),
             f' de {alumno.user.first_name}') for v in vinculos]


def _cuando(momento):
    return timezone.localtime(momento).strftime('%d/%m/%Y a las %H:%M')


def _avisar(alumno, asunto, texto):
    """Campanita y correo a quien corresponda. `texto(de_quien)` dice lo mismo para todos: de_quien es '' para
    el alumno y ' de Ana' para el apoderado de un menor."""
    for user, enlace, de_quien in _destinatarios(alumno):
        mensaje = texto(de_quien)
        notificar(user, mensaje, enlace)
        enviar(asunto, PLANTILLA, {'nombre': user.first_name, 'texto': mensaje}, user.email)


def cancelacion_del_profesor(inscripcion):
    cuando = _cuando(inscripcion.sesion.fecha_hora_inicio)
    asignatura = inscripcion.clase.asignatura.nombre
    _avisar(inscripcion.alumno, 'Tu profesor canceló una clase', lambda de_quien: (
        f'Tu profesor canceló la clase{de_quien} de {asignatura} del {cuando}. '
        'La clase volvió al paquete: ya puedes reagendarla en otro horario.'))


def _clase_extra(solicitud):
    return solicitud.alumno, solicitud.clase.asignatura.nombre, _cuando(solicitud.fecha_hora_inicio)


def clase_extra_aceptada(solicitud):
    alumno, asignatura, cuando = _clase_extra(solicitud)
    _avisar(alumno, 'Tu clase extra fue aceptada', lambda de_quien: (
        f'Tu profesor aceptó la clase extra{de_quien} de {asignatura} del {cuando}. '
        'Ya está reservada y se descontó una clase del paquete.'))


def clase_extra_rechazada(solicitud):
    alumno, asignatura, cuando = _clase_extra(solicitud)
    deja_mensaje = f' Te dejó este mensaje: {solicitud.motivo_rechazo}' if solicitud.motivo_rechazo else ''
    _avisar(alumno, 'Tu clase extra no fue aceptada', lambda de_quien: (
        f'Tu profesor no pudo aceptar la clase extra{de_quien} de {asignatura} del {cuando}.{deja_mensaje} '
        'Puedes pedir otra hora.'))


def clase_extra_vencida(solicitud, motivo):
    alumno, asignatura, cuando = _clase_extra(solicitud)
    _avisar(alumno, 'Tu pedido de clase extra venció', lambda de_quien: (
        f'Tu pedido de clase extra{de_quien} de {asignatura} del {cuando} venció y no se reservó. {motivo} '
        'Puedes pedir otra hora.'))
