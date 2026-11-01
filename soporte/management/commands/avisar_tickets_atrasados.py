"""Avisa los tickets de soporte vencidos: un resumen a cada agente, otro a los lideres
y una disculpa a quien espera la respuesta (D11).

Pensado para un cron diario en Railway: python manage.py avisar_tickets_atrasados
Cada ticket se avisa el primer dia habil de atraso y despues cada 3 dias habiles
(Ticket.AVISO_CADA). Los sabados, domingos y feriados no envia nada.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from soporte.correo import avisar_atrasados
from soporte.plazos import es_habil


class Command(BaseCommand):
    help = 'Avisa los tickets de soporte vencidos (solo en dias habiles).'

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        if not es_habil(hoy):
            self.stdout.write('Hoy no es día hábil: no se envían avisos.')
            return
        self.stdout.write(f'Tickets atrasados avisados: {avisar_atrasados(hoy)}')
