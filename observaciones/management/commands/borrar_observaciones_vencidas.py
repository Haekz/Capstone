"""Borra las observaciones de clases con mas de OBSERVACIONES_MESES (12 por defecto).

Pensado para un cron diario en Railway: python manage.py borrar_observaciones_vencidas
Es un juicio sobre una persona (a veces un menor): pasado el plazo ya no orienta y no hay razon para conservarlo.
"""

from django.core.management.base import BaseCommand

from observaciones.models import Observacion


class Command(BaseCommand):
    help = 'Borra las observaciones del profesor de clases con mas de OBSERVACIONES_MESES.'

    def handle(self, *args, **options):
        vencidas = Observacion.objects.vencidas()
        cantidad = vencidas.count()
        vencidas.delete()
        self.stdout.write(f'Observaciones borradas por vencidas: {cantidad}')
