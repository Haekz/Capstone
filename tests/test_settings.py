"""DEBUG se lee de la variable de entorno DEBUG (antes estaba fijo en True)."""

import importlib.util
import os
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase


def cargar_settings(**entorno):
    """Ejecuta una copia aparte de lbwus/settings.py con ``entorno``.

    No se recarga lbwus.settings: la configuracion activa de Django no cambia.
    """
    ruta = os.path.join(settings.BASE_DIR, 'lbwus', 'settings.py')
    spec = importlib.util.spec_from_file_location('settings_de_prueba', ruta)
    modulo = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, entorno):
        if 'DEBUG' not in entorno:
            os.environ.pop('DEBUG', None)
        spec.loader.exec_module(modulo)
    return modulo


class DebugDesdeEntornoTests(SimpleTestCase):

    def test_sin_variable_queda_en_true(self):
        self.assertTrue(cargar_settings().DEBUG)

    def test_valores_que_lo_activan(self):
        for valor in ('1', 'true', 'True', 'si'):
            with self.subTest(valor=valor):
                self.assertTrue(cargar_settings(DEBUG=valor).DEBUG)

    def test_valores_que_lo_desactivan(self):
        for valor in ('False', 'false', '0', 'no', ''):
            with self.subTest(valor=valor):
                self.assertFalse(cargar_settings(DEBUG=valor).DEBUG)
