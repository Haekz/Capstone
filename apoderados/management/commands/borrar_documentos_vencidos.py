"""Borra los documentos de apoderados con mas de 30 dias sin revisar.

Pensado para un cron diario en Railway: python manage.py borrar_documentos_vencidos
Al aprobar o rechazar ya se borran; esto cubre las solicitudes que nadie resolvio.
Antes, avisa una vez al agente de cada ticket cuyos documentos se borran en 5 dias.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apoderados.correo import avisar_vencimientos
from apoderados.models import Documento


class Command(BaseCommand):
    help = 'Borra los documentos de apoderados con mas de 30 dias sin revisar.'

    def handle(self, *args, **options):
        self.stdout.write(f'Tickets avisados por documentos por vencer: {avisar_vencimientos()}')
        borrados, _ = Documento.objects.filter(subido__lt=timezone.now() - Documento.VIGENCIA).delete()
        self.stdout.write(f'Documentos vencidos borrados: {borrados}')
