"""Correr una vez al dia, en un solo servicio Cron de Railway: python manage.py tareas_diarias

Corre en orden las tareas de TAREAS. Si una falla, sigue con las demas y al final termina con
error nombrando las que fallaron, para que Railway marque la corrida como fallida.
Para sumar una tarea diaria nueva basta agregarla a TAREAS: en Railway no se toca nada.

SCRUM-100: si alguna falla, avisa por correo a ALERTAS_CORREOS (lbwus/alertas.py). Si todas terminan bien,
guarda la hora de la corrida para /salud/ y el aviso del panel admin (lbwus/salud.py).

exportar_supresiones no esta porque necesita una ruta de salida fuera de la base de datos.
"""

import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from lbwus import alertas, salud

logger = logging.getLogger(__name__)

TAREAS = (
    'generar_bloques',  # primero: sin ella la agenda se queda sin horas para reservar
    'revisar_pagos_pendientes',
    'borrar_documentos_vencidos',
    'borrar_observaciones_vencidas',
    'borrar_conversaciones_inactivas',
    'avisar_tickets_atrasados',
    'avisar_revisiones_pendientes',
    'avisar_requerimientos_por_vencer',
    'avisar_entregas_videos',
)


class Command(BaseCommand):
    help = 'Corre todas las tareas diarias; si una falla, sigue con las demas.'

    def handle(self, *args, **options):
        fallidas = []
        for tarea in TAREAS:
            self.stdout.write(f'== {tarea}')
            try:
                call_command(tarea, stdout=self.stdout, stderr=self.stderr)
            except Exception:  # aislar cada tarea: una caida no debe dejar sin correr a las demas
                logger.exception('evento=tarea_diaria_fallida tarea=%s', tarea)
                fallidas.append(tarea)
        if fallidas:
            logger.error('evento=tareas_diarias_con_error fallidas=%s total=%s', ','.join(fallidas), len(TAREAS))
            alertas.avisar_tareas_fallidas(fallidas, len(TAREAS))
            raise CommandError(f'Fallaron {len(fallidas)} de {len(TAREAS)}: {", ".join(fallidas)}')
        salud.marcar_corrida()
        logger.info('evento=tareas_diarias_completas total=%s', len(TAREAS))
        self.stdout.write(f'Tareas diarias completas: {len(TAREAS)}')
