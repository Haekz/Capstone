"""Correr una vez al dia (como avisar_tickets_atrasados): mantiene 4 semanas de bloques."""

from django.core.management.base import BaseCommand

from agenda.bloques import SEMANAS, generar
from alumnos.models import Profesor


class Command(BaseCommand):
    help = f'Crea los bloques de las proximas {SEMANAS} semanas segun el horario semanal de cada profesor.'

    def handle(self, *args, **options):
        profesores = Profesor.objects.habilitados().filter(horario_semanal__isnull=False).distinct()
        total = sum(generar(profesor) for profesor in profesores)
        self.stdout.write(f'Bloques nuevos: {total}')
