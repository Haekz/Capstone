"""Avisa los tickets de soporte vencidos: un resumen a cada agente y otro a los lideres.

Pensado para un cron diario en Railway: python manage.py avisar_tickets_atrasados
Los sabados, domingos y feriados no envia nada: el aviso es de cada dia habil.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from soporte.correo import avisar_atrasados
from soporte.plazos import es_habil


class Command(BaseCommand):
    help = 'Avisa los tickets de soporte vencidos (solo en dias habiles).'

    def handle(self, *args, **options):
        if not es_habil(timezone.localdate()):
            self.stdout.write('Hoy no es día hábil: no se envían avisos.')
            return
        self.stdout.write(f'Tickets atrasados avisados: {avisar_atrasados()}')
