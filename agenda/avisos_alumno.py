"""Aviso al alumno (o a su apoderado) cuando su profesor cancela (paso A3b, decidido 02-nov).

Correo + campanita. Un alumno menor no recibe nada: avisa a sus apoderados con vinculo
verificado. Privacidad: la cancelacion y la clase extra no llevan ningun dato del profesor, solo la asignatura y la
fecha; la reserva (21-nov) lleva ademas su nombre y apellido, sin ningun otro dato.
"""

from django.urls import reverse
from django.utils import timezone

from alumnos.correo_clase import enviar_aviso_clase
from alumnos.utils import es_menor
from apoderados.models import Vinculo
from notificaciones.models import notificar


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
        enviar_aviso_clase(user, asunto, asunto, [mensaje], 'Ver mis clases', enlace)


def reserva(inscripcion, vinculo=None):
    """Reserva confirmada (21-nov): avisa al alumno adulto o, si es menor, a sus apoderados verificados, incluido quien
    la hizo. Con el nombre y apellido del profesional y sin ningun otro dato suyo (solo si alumnos/services.py la
    enlaza al confirmarse, on_commit)."""
    cuando = _cuando(inscripcion.sesion.fecha_hora_inicio)
    asignatura = inscripcion.clase.asignatura.nombre
    profesor = inscripcion.clase.profesor.nombre
    autor = f' La reservó {vinculo.apoderado.nombre}.' if vinculo else ''

    def texto(de_quien):
        sujeto = f'La clase{de_quien}' if de_quien else 'Tu clase'
        return (f'{sujeto} ({asignatura}) con {profesor} quedó reservada para el {cuando}.'
                f'{autor if de_quien else ""}')
    _avisar(inscripcion.alumno, 'Clase reservada', texto)


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
