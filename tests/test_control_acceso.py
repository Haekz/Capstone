"""Control de acceso a las vistas internas del portal de administracion.

La proteccion la aplica el decorador alumnos.decorators.admin_required.
Estos tests detectan si se quita o si falta en una vista nueva.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Genero, Tutor


class AccesoPortalAdminTests(TestCase):
    """Las pantallas internas exigen sesion de admin; la de salida no."""

    # Vistas que dibujan base_admin.html (barra lateral con datos del admin).
    VISTAS_PRIVADAS = (
        'dashboard_admin',
        'crud',
        'alumnos_Add',
        'alumnos_Update',
        'planes_adm',
        'nosotros_adm',
        'contactos_adm',
    )

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        cls.user_admin = User.objects.create_user(
            '10101010-1', password='clave12345'
        )
        cls.tutor = Tutor.objects.create(
            user=cls.user_admin, nombre='Nadia Vera', rut='10101010-1',
            direccion='Calle 10', fecha_nacimiento=date(1980, 1, 1),
            correo_electronico='nadia@lbwus.cl', genero=genero,
        )

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
        victima = Tutor.objects.create(
            user=otro, nombre='Victima', rut='20202020-2',
            direccion='Calle 20', fecha_nacimiento=date(1981, 2, 2),
            correo_electronico='v@lbwus.cl',
            genero=Genero.objects.first(),
        )

        respuesta = self.client.get(
            reverse('alumnos_del', args=[victima.id_tutor])
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Tutor.objects.filter(pk=victima.pk).exists())


class AccesoPanelProfesorTests(TestCase):
    """El panel redirige y los endpoints JSON responden JSON."""

    @classmethod
    def setUpTestData(cls):
        from alumnos.models import Profesor

        genero = Genero.objects.create(descripcion='Otro')
        cls.user_prof = User.objects.create_user(
            '30303030-3', password='clave12345'
        )
        cls.profesor = Profesor.objects.create(
            user=cls.user_prof, nombre='Omar Gil', rut='30303030-3',
            especialidad='Fisica', direccion='Calle 30',
            fecha_nacimiento=date(1988, 3, 3), correo_electronico='o@lbwus.cl',
            telefono='955555555', genero=genero,
        )

    def test_panel_sin_sesion_redirige_al_registro(self):
        respuesta = self.client.get(reverse('panel_profesor'))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('regis_prof'), respuesta['Location'])

    def test_endpoints_json_responden_json_y_no_redirect(self):
        """Un redirect aqui rompe al cliente que espera {'success': ...}."""
        for nombre in ('actualizar_perfil_prof', 'solicitar_retiro'):
            with self.subTest(endpoint=nombre):
                respuesta = self.client.post(reverse(nombre), {})

                self.assertEqual(respuesta.status_code, 200)
                self.assertFalse(respuesta.json()['success'])
                self.assertIn('Sesión inválida', respuesta.json()['message'])
