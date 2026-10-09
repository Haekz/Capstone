"""Control de acceso a las vistas internas del portal de administracion.

La proteccion la aplica el decorador alumnos.decorators.admin_required.
Estos tests detectan si se quita o si falta en una vista nueva.
"""
from datetime import date
from django.contrib.auth import get_user_model
User = get_user_model()
from django.test import TestCase
from django.urls import reverse
from alumnos.models import Genero, Tutor

class AccesoPortalAdminTests(TestCase):
    """Las pantallas internas exigen sesion de admin; la de salida no."""
    VISTAS_PRIVADAS = ('dashboard_admin', 'crud', 'alumnos_Add', 'alumnos_Update', 'planes_adm', 'nosotros_adm', 'contactos_adm')

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        cls.user_admin = User.objects.create_user('10101010-1', password='clave12345')
        cls.tutor = Tutor.objects.create(user=cls.user_admin)

    def _entrar_como_admin(self):
        self.client.force_login(self.user_admin)
        sesion = self.client.session
        sesion['admin_id'] = self.tutor.id_tutor
        sesion.save()

    def test_anonimo_no_entra_a_ninguna_vista_interna(self):
        for nombre in self.VISTAS_PRIVADAS:
            with self.subTest(vista=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('login'), respuesta['Location'])

    def test_admin_con_sesion_si_entra(self):
        self._entrar_como_admin()
        for nombre in self.VISTAS_PRIVADAS:
            with self.subTest(vista=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertNotEqual(respuesta.status_code, 302)

    def test_pantalla_de_sesion_cerrada_queda_publica(self):
        """home_adm es el destino de LOGOUT_REDIRECT_URL: se visita justo
        despues de destruir la sesion, asi que no puede exigir admin_id.
        """
        respuesta = self.client.get(reverse('home_adm'))
        self.assertEqual(respuesta.status_code, 200)

    def test_accion_destructiva_no_corre_sin_sesion(self):
        """Un anonimo no debe poder borrar por URL directa."""
        otro = User.objects.create_user('20202020-2', password='x')
        victima = Tutor.objects.create(user=otro)
        respuesta = self.client.get(reverse('alumnos_del', args=[victima.id_tutor]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Tutor.objects.filter(pk=victima.pk).exists())