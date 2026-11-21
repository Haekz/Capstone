"""Alertas por correo al equipo (SCRUM-100). Hoy: cuando falla alguna tarea de tareas_diarias.

Destinatarios: ``settings.ALERTAS_CORREOS`` (variable de entorno, separada por comas). Vacia: no se envia nada.
El correo dice que tareas fallaron y a que hora; nunca trazas ni datos personales (la traza queda en el log).
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


def avisar_tareas_fallidas(fallidas, total, cuando=None):
    """Devuelve True si el correo salio. Nunca lanza: una alerta caida no debe tapar el error de las tareas."""
    destinatarios = list(getattr(settings, 'ALERTAS_CORREOS', []))
    if not destinatarios:
        logger.warning('evento=alerta_omitida motivo=sin_ALERTAS_CORREOS fallidas=%s', ','.join(fallidas))
        return False
    hora = timezone.localtime(cuando or timezone.now()).strftime('%d-%m-%Y %H:%M (%Z)')
    asunto = f'[LBWUS] Fallaron {len(fallidas)} de {total} tareas diarias'
    cuerpo = '\n'.join([
        f'La corrida de tareas_diarias del {hora} termino con error.',
        '',
        'Tareas que fallaron:',
        *(f'- {tarea}' for tarea in fallidas),
        '',
        'Las demas tareas si corrieron. El detalle del error esta en los logs del servicio Cron en Railway',
        '(ver docs/CONFIGURACION_PRODUCCION.md, seccion "Logging, monitoreo y alertas").',
    ])
    try:
        send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, destinatarios)
    except Exception as error:  # SMTP caido o sin credenciales: queda en el log, el comando falla igual
        logger.error('evento=alerta_no_enviada error=%s', type(error).__name__)
        return False
    logger.info('evento=alerta_enviada destinatarios=%s fallidas=%s', len(destinatarios), ','.join(fallidas))
    return True
