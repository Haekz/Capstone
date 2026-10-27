"""Envio del enlace de confirmacion de correo."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import token_correo

logger = logging.getLogger(__name__)


def enviar_confirmacion(request, apoderado):
    """Envia el enlace. Devuelve False si el correo no salio (se puede reenviar)."""
    user = apoderado.user
    ruta = reverse('apoderado_confirmar_correo', args=[
        urlsafe_base64_encode(force_bytes(user.pk)), token_correo.make_token(user),
    ])
    cuerpo = render_to_string('apoderados/correo_confirmacion.txt', {
        'nombre': apoderado.nombre,
        'enlace': request.build_absolute_uri(ruta),
        'horas': settings.PASSWORD_RESET_TIMEOUT // 3600,
    })
    try:
        send_mail('Confirma tu correo - LBWUS', cuerpo, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception:  # SMTP caido, timeout, credenciales: el apoderado puede reenviar
        logger.exception('No se pudo enviar la confirmacion al apoderado %s', apoderado.pk)
        return False
    return True
