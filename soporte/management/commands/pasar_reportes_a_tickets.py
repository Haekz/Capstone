"""Pasa a tickets los reportes del canal viejo que siguen pendientes (paso 6e).

Se corre una vez al desplegar: python manage.py pasar_reportes_a_tickets
Cada reporte pendiente queda como ticket "Otro" de su mismo autor, con plazo desde
hoy, y el reporte se marca resuelto. Volver a correrlo no duplica nada.

Los de menores no se pasan: no abren tickets (D18). Se listan para que un lider
decida como seguir.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from alumnos.models import Reporte
from alumnos.utils import es_menor
from soporte.models import Ticket
from soporte.tickets import abrir_reporte


class Command(BaseCommand):
    help = 'Pasa a tickets los reportes viejos pendientes (una vez, al desplegar el paso 6e).'

    def handle(self, *args, **options):
        pasados, de_menores = 0, []
        for reporte in Reporte.objects.filter(estado='pendiente').select_related('remitente').order_by('id_reporte'):
            if es_menor(reporte.remitente):
                de_menores.append(reporte.id_reporte)
                continue
            with transaction.atomic():
                abrir_reporte(reporte.remitente, Ticket.OTRO, f'Reporte anterior #{reporte.id_reporte}',
                              reporte.descripcion)
                reporte.estado = 'resuelto'
                reporte.save(update_fields=['estado'])
            pasados += 1
        self.stdout.write(f'Reportes pasados a tickets: {pasados}')
        if de_menores:
            self.stdout.write(f'De menores, para que decida un lider: {", ".join(map(str, de_menores))}')
