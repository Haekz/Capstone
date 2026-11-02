"""Correr una vez al dia (como generar_bloques): python manage.py borrar_conversaciones_inactivas

Borra las conversaciones con 90 dias sin actividad (reglas y excepciones en mensajes/retencion.py).
Con --simular solo cuenta cuantas se borrarian. Escribe solo cantidades: nunca nombres ni mensajes.
"""

from django.core.management.base import BaseCommand

from mensajes import retencion


class Command(BaseCommand):
    help = f'Borra las conversaciones con {retencion.DIAS_SIN_ACTIVIDAD} dias sin actividad.'

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true', help='Cuenta las que se borrarian, sin borrar.')

    def handle(self, *args, simular=False, **options):
        if simular:
            self.stdout.write(f'Conversaciones que se borrarian: {retencion.candidatas().count()}')
        else:
            self.stdout.write(f'Conversaciones borradas: {retencion.borrar_inactivas()}')
