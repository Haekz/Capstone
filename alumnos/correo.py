"""Envio de correos de texto. Lo usan apoderados y soporte."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def enviar(asunto, plantilla, contexto, destinatario):
    """Devuelve False si el correo no salio: un fallo de SMTP nunca deshace lo guardado."""
    try:
        send_mail(f'{asunto} - LBWUS', render_to_string(plantilla, contexto),
                  settings.DEFAULT_FROM_EMAIL, [destinatario])
    except Exception:  # SMTP caido, timeout, credenciales: se puede reenviar
        logger.exception('No se pudo enviar el correo "%s"', asunto)
        return False
    return True
