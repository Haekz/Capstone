"""Correr una vez al dia (como avisar_tickets_atrasados): mantiene 4 semanas de bloques."""

import logging

from django.core.management.base import BaseCommand

from agenda.bloques import SEMANAS, generar
from alumnos.models import Profesor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = f'Crea los bloques de las proximas {SEMANAS} semanas segun el horario semanal de cada profesor.'

    def handle(self, *args, **options):
        profesores = Profesor.objects.habilitados().filter(horario_semanal__isnull=False).distinct()
        total = 0
        for profesor in profesores:
            try:
                total += generar(profesor)
            except Exception:
                logger.exception('Error generando bloques para profesor %s', profesor.pk)
        self.stdout.write(f'Bloques nuevos: {total}')
