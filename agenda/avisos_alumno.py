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


def cancelacion_del_profesor(inscripcion):
    cuando = timezone.localtime(inscripcion.sesion.fecha_hora_inicio).strftime('%d/%m/%Y a las %H:%M')
    asignatura = inscripcion.clase.asignatura.nombre
    for user, enlace, de_quien in _destinatarios(inscripcion.alumno):
        texto = (f'Tu profesor canceló la clase{de_quien} de {asignatura} del {cuando}. '
                 'La clase volvió al paquete: ya puedes reagendarla en otro horario.')
        notificar(user, texto, enlace)
        enviar('Tu profesor canceló una clase', PLANTILLA, {'nombre': user.first_name, 'texto': texto}, user.email)
