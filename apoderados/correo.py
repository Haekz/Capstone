"""Correos del modulo: confirmaciones, invitacion al apoderado y avisos de clases.

Cada funcion devuelve False si el correo no salio (se puede reenviar).
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import Apoderado, Vinculo
from .tokens import firmar_invitacion, token_correo, token_correo_adolescente

logger = logging.getLogger(__name__)


def _enviar(asunto, plantilla, contexto, destinatario):
    try:
        send_mail(f'{asunto} - LBWUS', render_to_string(plantilla, contexto),
                  settings.DEFAULT_FROM_EMAIL, [destinatario])
    except Exception:  # SMTP caido, timeout, credenciales: se puede reenviar
        logger.exception('No se pudo enviar el correo "%s"', asunto)
        return False
    return True


def _enlace_confirmacion(request, ruta, user, generador):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return request.build_absolute_uri(reverse(ruta, args=[uid, generador.make_token(user)]))


def enviar_confirmacion(request, apoderado):
    user = apoderado.user
    return _enviar('Confirma tu correo', 'apoderados/correo_confirmacion.txt', {
        'nombre': apoderado.nombre,
        'enlace': _enlace_confirmacion(request, 'apoderado_confirmar_correo', user, token_correo),
        'horas': settings.PASSWORD_RESET_TIMEOUT // 3600,
    }, user.email)


def enviar_confirmacion_adolescente(request, user):
    return _enviar('Confirma tu correo', 'apoderados/correo_confirmacion_adolescente.txt', {
        'nombre': user.first_name,
        'enlace': _enlace_confirmacion(request, 'adolescente_confirmar_correo', user, token_correo_adolescente),
        'horas': settings.PASSWORD_RESET_TIMEOUT // 3600,
    }, user.email)


def enviar_invitacion(request, invitacion):
    # Solo el nombre del estudiante: ni RUT ni fecha de nacimiento (minimizacion).
    return _enviar('Invitación para ser apoderado', 'apoderados/correo_invitacion.txt', {
        'nombre': invitacion.solicitud.alumno.user.first_name,
        'enlace': request.build_absolute_uri(reverse('apoderado_invitacion', args=[firmar_invitacion(invitacion)])),
        'dias': invitacion.VIGENCIA.days,
    }, invitacion.correo)


def avisar_apoderados(inscripcion, accion, autor):
    """Avisa a cada apoderado con vinculo verificado del estudiante.

    Un correo por persona: ningun apoderado ve la direccion del otro. Un fallo
    de SMTP no deshace la reserva, que ya quedo guardada.
    """
    destinatarios = (Vinculo.objects.filter(alumno=inscripcion.alumno, estado=Vinculo.VERIFICADO,
                                            apoderado__estado=Apoderado.VERIFICADO)
                     .values_list('apoderado__user__email', flat=True))
    estudiante = inscripcion.alumno.user.first_name
    contexto = {'accion': accion, 'autor': autor, 'estudiante': estudiante,
                'clase': inscripcion.clase, 'sesion': inscripcion.sesion}
    return all([_enviar(f'Clases de {estudiante}', 'apoderados/correo_aviso_clase.txt', contexto, correo)
                for correo in destinatarios])
