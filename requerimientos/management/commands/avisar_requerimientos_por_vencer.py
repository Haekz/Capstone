"""Correr una vez al dia (como avisar_revisiones_pendientes): python manage.py avisar_requerimientos_por_vencer

Recuerda a los lideres de soporte los requerimientos de autoridad abiertos cuyo plazo se acerca o ya paso (reglas en
requerimientos/avisos.py). Los sabados, domingos y feriados no envia nada. Escribe solo cantidades.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from requerimientos.avisos import avisar
from soporte.plazos import es_habil


class Command(BaseCommand):
    help = 'Recuerda a los lideres los requerimientos de autoridad por vencer o atrasados (solo en dias habiles).'

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        if not es_habil(hoy):
            self.stdout.write('Hoy no es día hábil: no se envían avisos.')
            return
        self.stdout.write(f'Requerimientos por vencer o atrasados avisados: {avisar(hoy)}')
