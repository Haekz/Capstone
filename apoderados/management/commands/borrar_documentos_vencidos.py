"""Borra los documentos de apoderados con mas de 30 dias sin revisar.

Pensado para un cron diario en Railway: python manage.py borrar_documentos_vencidos
Al aprobar o rechazar ya se borran; esto cubre las solicitudes que nadie resolvio.
Antes, avisa una vez al agente de cada ticket cuyos documentos se borran en 5 dias.
Al borrarlos cierra sus tickets y le pide al apoderado que los vuelva a subir.
"""

from django.core.management.base import BaseCommand

from apoderados.correo import avisar_documentos_vencidos, avisar_vencimientos
from apoderados.models import vencer_documentos


class Command(BaseCommand):
    help = 'Borra los documentos de apoderados con mas de 30 dias sin revisar.'

    def handle(self, *args, **options):
        self.stdout.write(f'Tickets avisados por documentos por vencer: {avisar_vencimientos()}')
        apoderados = vencer_documentos()
        for apoderado in apoderados:
            avisar_documentos_vencidos(apoderado)
        self.stdout.write(f'Apoderados con documentos vencidos avisados: {len(apoderados)}')
