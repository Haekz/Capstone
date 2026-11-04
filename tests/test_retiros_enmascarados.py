"""Retiros antiguos con el numero de cuenta en claro: la migracion 0019 los enmascara (02-nov).

Datos ficticios.
"""

import importlib

from django.apps import apps
from django.test import TestCase

from alumnos.models import SolicitudRetiro
from tests.test_soporte import crear_profesor

migracion = importlib.import_module('alumnos.migrations.0019_enmascarar_retiros_antiguos')


class EnmascararRetirosAntiguosTests(TestCase):

    def test_solo_quedan_los_ultimos_4_digitos_como_en_los_retiros_nuevos(self):
        profesor = crear_profesor()
        antiguo, nuevo, sin_cuenta = (SolicitudRetiro.objects.create(profesor=profesor, monto=1000, numero_cuenta=numero)
                                      for numero in ('12-345 6789', '•••• 4321', ''))
        migracion.enmascarar(apps, None)
        migracion.enmascarar(apps, None)  # volver a correrla no cambia nada
        for retiro, esperado in ((antiguo, '•••• 6789'), (nuevo, '•••• 4321'), (sin_cuenta, '')):
            retiro.refresh_from_db()
            self.assertEqual(retiro.numero_cuenta, esperado)
