"""Envio de correos: texto plano y, si se pide, tambien una version con diseno. Lo usan apoderados, soporte y avisos."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def enviar(asunto, plantilla, contexto, destinatario, plantilla_html=None):
    """Devuelve False si el correo no salio: un fallo de SMTP nunca deshace lo guardado.

    El texto usa el motor 'correo' (settings.TEMPLATES): texto plano, sin escapar HTML. Con `plantilla_html` el
    correo lleva ademas esa version con diseno, que usa el motor normal: ahi SI se escapa todo lo que viene de
    personas (nombres, asignaturas), porque un nombre con `<` no puede convertirse en HTML.
    """
    try:
        send_mail(f'{asunto} - LBWUS', render_to_string(plantilla, contexto, using='correo'),
                  settings.DEFAULT_FROM_EMAIL, [destinatario],
                  html_message=render_to_string(plantilla_html, contexto) if plantilla_html else None)
    except Exception:  # SMTP caido, timeout, credenciales: se puede reenviar
        # La plantilla y no el asunto: el asunto puede llevar el nombre de un estudiante (SCRUM-100).
        # El correo del destinatario que trae el error SMTP lo enmascara FormatoSeguro (lbwus/registro.py).
        logger.exception('evento=correo_no_enviado plantilla=%s', plantilla)
        return False
    return True
