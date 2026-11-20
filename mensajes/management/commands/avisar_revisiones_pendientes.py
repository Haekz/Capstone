"""Correr una vez al dia (como borrar_conversaciones_inactivas): python manage.py avisar_revisiones_pendientes

Recuerda a los lideres de soporte las conversaciones reportadas que esperan su decision (reglas en
mensajes/avisos_revision.py). Los sabados, domingos y feriados no envia nada. Escribe solo cantidades.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from mensajes.avisos_revision import avisar_pendientes
from soporte.plazos import es_habil


class Command(BaseCommand):
    help = 'Recuerda a los lideres las conversaciones reportadas que esperan decision (solo en dias habiles).'

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        if not es_habil(hoy):
            self.stdout.write('Hoy no es día hábil: no se envían avisos.')
            return
        self.stdout.write(f'Conversaciones por revisar avisadas: {avisar_pendientes(hoy)}')
