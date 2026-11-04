"""Pasa a la base, cifrados, los titulos de profesores que siguen en disco (paso 9b-2).

Se corre una vez al desplegar el paso 9b: python manage.py pasar_titulos_a_base
Los que estan en revision se cifran; si el archivo ya no existe, el profesor debe
volver a subirlo. Los ya aprobados o rechazados solo se borran del disco (el original
no se guarda). Volver a correrlo no hace nada. Despues se quita titulo_archivo (9b-3).
"""

from collections import Counter

from django.core.management.base import BaseCommand

from alumnos.models import Profesor
from user_profesor import titulo


class Command(BaseCommand):
    help = 'Pasa a la base, cifrados, los titulos que siguen en disco (una vez, al desplegar el paso 9b).'

    def handle(self, *args, **options):
        resultados = Counter(titulo.pasar_a_base(profesor)
                             for profesor in Profesor.objects.exclude(titulo_archivo='').order_by('id_profesor'))
        self.stdout.write(f'Titulos pasados a la base: {resultados[titulo.PASADO]}')
        self.stdout.write(f'No se recuperaron (el profesor debe volver a subirlo): {resultados[titulo.A_RESUBIR]}')
        self.stdout.write(f'Ya decididos, borrados del disco: {resultados[titulo.BORRADO]}')
