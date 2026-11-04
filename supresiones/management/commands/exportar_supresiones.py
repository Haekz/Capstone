"""Correr a diario (como borrar_conversaciones_inactivas) y guardar el archivo FUERA de la base de datos:

    python manage.py exportar_supresiones RUTA.json

Restaurar un respaldo de la base devuelve tambien el registro de supresiones a como estaba. Este archivo conserva las
supresiones posteriores para reaplicarlas (reaplicar_supresiones --archivo). Solo tiene huellas, no RUT ni correos,
pero sigue siendo informacion de personas: guardarlo con el mismo cuidado que los respaldos y la clave
SUPRESIONES_CLAVE, y borrarlo segun la politica de conservacion. Escribe solo cantidades.
"""

import json

from django.core.management.base import BaseCommand, CommandError

from supresiones import registro


class Command(BaseCommand):
    help = 'Exporta el registro de supresiones a un archivo JSON (solo huellas).'

    def add_arguments(self, parser):
        parser.add_argument('ruta', help='Archivo de salida, guardado fuera de la base de datos.')

    def handle(self, *args, ruta, **options):
        filas = registro.exportar()
        try:
            with open(ruta, 'w', encoding='utf-8') as archivo:
                json.dump(filas, archivo)
        except OSError as error:
            raise CommandError(f'No se pudo escribir el archivo: {error.strerror}')
        self.stdout.write(f'Supresiones exportadas: {len(filas)}')
