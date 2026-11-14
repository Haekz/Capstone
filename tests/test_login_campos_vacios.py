"""Login con campos vacios (alumnos.views.custom_login). El resto de sus mensajes ya los fijan otras pruebas.

Se escribio antes de partir custom_login en funciones (integracion del PR #107 de Franco).
"""

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse


class LoginCamposVaciosTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_sin_usuario_o_sin_clave_pide_todos_los_campos(self):
        for datos in ({'username': '', 'password': 'x'}, {'username': '11111111-1', 'password': ''}, {}):
            with self.subTest(datos=datos):
                respuesta = self.client.post(reverse('login'), datos)
                self.assertContains(respuesta, 'Por favor ingrese todos los campos.')

    def test_un_login_vacio_no_cuenta_como_intento_fallido(self):
        for _ in range(6):
            self.client.post(reverse('login'), {'username': '11111111-1', 'password': ''})
        respuesta = self.client.post(reverse('login'), {'username': '11111111-1', 'password': ''})
        self.assertNotContains(respuesta, 'Demasiados intentos')
