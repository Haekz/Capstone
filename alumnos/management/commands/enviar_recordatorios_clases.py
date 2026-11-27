"""Correr cada 15 minutos, en su propio servicio Cron de Railway: python manage.py enviar_recordatorios_clases

Envia los recordatorios de clase de 24 y de 2 horas antes (alumnos/recordatorios.py). No va en `tareas_diarias`: esa
corre una vez al dia y un aviso de 2 horas no puede esperar hasta manana.

Si alguna reserva falla, sigue con las demas y termina con error (Railway marca la corrida como fallida); lo que fallo se
reintenta en la proxima corrida. Solo una corrida sin fallos deja el latido que lee /salud/ (lbwus/salud.py).
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from alumnos import recordatorios
from lbwus import salud

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envia los recordatorios de clase de 24 y 2 horas antes.'

    def handle(self, *args, **options):
        un_dia, dos_horas, fallidos = recordatorios.enviar_pendientes()
        resumen = f'Recordatorios: {un_dia} de 24 horas, {dos_horas} de 2 horas, {fallidos} con error'
        self.stdout.write(resumen)
        if fallidos:
            logger.error('evento=recordatorios_con_error de_un_dia=%s de_dos_horas=%s fallidos=%s',
                         un_dia, dos_horas, fallidos)
            raise CommandError(f'{resumen}. Se reintentan en la proxima corrida.')
        salud.marcar_recordatorios()
        logger.info('evento=recordatorios_enviados de_un_dia=%s de_dos_horas=%s', un_dia, dos_horas)
