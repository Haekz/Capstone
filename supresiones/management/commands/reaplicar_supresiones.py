"""Correr tras restaurar un respaldo y ANTES de reabrir el servicio:

    python manage.py reaplicar_supresiones --archivo RUTA.json [--simular]

Vuelve a eliminar las cuentas que ya se habian eliminado y que el respaldo trajo de vuelta (supresiones/registro.py).
--archivo: el ultimo exportar_supresiones; se suma al registro de la base (que pudo quedar atrasado). --simular:
solo cuenta, sin importar ni eliminar nada. Escribe solo cantidades: nunca RUT, correos ni nombres.
"""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from supresiones import registro


class Command(BaseCommand):
    help = 'Vuelve a eliminar las cuentas ya eliminadas que trajo un respaldo restaurado.'

    def add_arguments(self, parser):
        parser.add_argument('--archivo', help='Archivo de exportar_supresiones, para sumarlo al registro.')
        parser.add_argument('--simular', action='store_true', help='Cuenta las que se eliminarian, sin tocar nada.')

    def _leer(self, ruta):
        try:
            with open(ruta, encoding='utf-8') as archivo:
                return json.load(archivo)
        except (OSError, ValueError) as error:
            raise CommandError(f'No se pudo leer el archivo: {error}')

    def handle(self, *args, archivo=None, simular=False, **options):
        with transaction.atomic():  # simular: lo importado se deshace al final
            nuevas = 0
            if archivo:
                try:
                    nuevas = registro.importar(self._leer(archivo))
                except (ValueError, TypeError) as error:
                    raise CommandError(str(error))
            cuentas = registro.reaplicar(simular=simular)
            if simular:
                transaction.set_rollback(True)
        self.stdout.write(f'Supresiones nuevas del archivo: {nuevas}')
        self.stdout.write(f'Cuentas que se eliminarian: {cuentas}' if simular else f'Cuentas eliminadas de nuevo: {cuentas}')
