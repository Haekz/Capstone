"""Borra los documentos de apoderados con mas de 30 dias sin revisar (fase 2a).

Pensado para un cron diario en Railway: python manage.py borrar_documentos_vencidos
Al aprobar o rechazar ya se borran; esto cubre las solicitudes que nadie resolvio.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apoderados.models import Documento


class Command(BaseCommand):
    help = 'Borra los documentos de apoderados con mas de 30 dias sin revisar.'

    def handle(self, *args, **options):
        borrados, _ = Documento.objects.filter(subido__lt=timezone.now() - Documento.VIGENCIA).delete()
        self.stdout.write(f'Documentos vencidos borrados: {borrados}')
