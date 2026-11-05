"""Control de acceso a las vistas internas del portal de administracion.

La proteccion la aplica el decorador alumnos.decorators.admin_required.
Estos tests detectan si se quita o si falta en una vista nueva.
"""
from django.contrib.auth import get_user_model
User = get_user_model()
from django.test import Client, TestCase
from django.urls import reverse
from alumnos.models import Alumno, Genero, SolicitudRetiro, Tutor
from tests.test_apoderados import entrar

class AccesoPortalAdminTests(TestCase):
    """Las pantallas internas exigen sesion de admin; la de salida no."""
    VISTAS_PRIVADAS = ('dashboard_admin', 'crud', 'alumnos_Add', 'alumnos_Update', 'planes_adm', 'nosotros_adm')

    @classmethod
    def setUpTestData(cls):
        Genero.objects.create(descripcion='Otro')
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

    def _crear_alumno(self):
        user = User.objects.create_user('30303030-3', password='x')
        return Alumno.objects.create(user=user, nivel_educacion='media')

    def test_eliminar_alumno_por_get_no_borra(self):
        """Un enlace (o una imagen en otra pagina) no debe poder borrar."""
        alumno = self._crear_alumno()
        self._entrar_como_admin()
        respuesta = self.client.get(reverse('alumnos_del', args=[alumno.id_alumno]))
        self.assertEqual(respuesta.status_code, 405)
        self.assertTrue(Alumno.objects.filter(pk=alumno.pk).exists())

    def test_admin_elimina_alumno_por_post(self):
        alumno = self._crear_alumno()
        self._entrar_como_admin()
        respuesta = self.client.post(reverse('alumnos_del', args=[alumno.id_alumno]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Alumno.objects.filter(pk=alumno.pk).exists())
        self.assertFalse(User.objects.filter(username='30303030-3').exists())


class CsrfEndpointsAlumnoTests(TestCase):
    """inscribir_clase ya no usa @csrf_exempt: el portal del alumno manda el token en
    el encabezado X-CSRFToken. (enviar_reporte se retiro en el paso 6e: ahora son tickets.)"""
    VISTAS = ('inscribir_clase',)

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def test_post_sin_token_es_rechazado(self):
        for nombre in self.VISTAS:
            with self.subTest(vista=nombre):
                respuesta = self.client.post(reverse(nombre), '{}', content_type='application/json')
                self.assertEqual(respuesta.status_code, 403)

    def test_post_con_token_del_encabezado_pasa(self):
        self.client.get(reverse('login'))  # el formulario deja la cookie csrftoken
        token = self.client.cookies['csrftoken'].value
        for nombre in self.VISTAS:
            with self.subTest(vista=nombre):
                respuesta = self.client.post(reverse(nombre), '{}', content_type='application/json',
                                             HTTP_X_CSRFTOKEN=token)
                self.assertNotEqual(respuesta.status_code, 403)


class EndpointsJsonDelAlumnoTests(TestCase):
    """inscribir_clase, sesiones_disponibles y reservar_sesion exigen sesion de alumno con la cuenta
    activa (S-07). Antes bastaba con 'alumno_id' en la sesion: un alumno desactivado por el admin
    seguia reservando hasta que la sesion expiraba."""
    VISTAS = (('inscribir_clase', 'post'), ('sesiones_disponibles', 'get'), ('reservar_sesion', 'post'))

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('40404040-4', password='x')
        cls.alumno = Alumno.objects.create(user=cls.user, nivel_educacion='media')

    def _pedir(self, nombre, metodo):
        return getattr(self.client, metodo)(reverse(nombre))

    def _rechazado_en_json(self, respuesta):
        """401 con JSON: el portal lee data.message; una redireccion romperia su fetch."""
        self.assertEqual(respuesta.status_code, 401)
        self.assertFalse(respuesta.json()['success'])

    def test_alumno_activo_si_entra(self):
        entrar(self.client, self.user, alumno_id=self.alumno.id_alumno)
        respuesta = self.client.get(reverse('sesiones_disponibles'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['success'])

    def test_anonimo_recibe_401_en_json(self):
        for nombre, metodo in self.VISTAS:
            with self.subTest(vista=nombre):
                self._rechazado_en_json(self._pedir(nombre, metodo))

    def test_cuenta_desactivada_con_sesion_abierta_no_entra(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        for nombre, metodo in self.VISTAS:
            with self.subTest(vista=nombre):
                entrar(self.client, self.user, alumno_id=self.alumno.id_alumno)
                self._rechazado_en_json(self._pedir(nombre, metodo))
                self.assertNotIn('alumno_id', self.client.session)  # y se le cierra la sesion

    def test_otro_rol_recibe_json_y_no_una_redireccion(self):
        admin = User.objects.create_user('50505050-5', password='x')
        entrar(self.client, admin, admin_id=Tutor.objects.create(user=admin).id_tutor)
        for nombre, metodo in self.VISTAS:
            with self.subTest(vista=nombre):
                self._rechazado_en_json(self._pedir(nombre, metodo))


class SolicitarRetiroTests(TestCase):
    """Antes leia request.session['profesor_id'] sin decorador: un anonimo
    provocaba KeyError (error 500)."""

    def test_anonimo_recibe_sesion_invalida_y_no_crea_retiro(self):
        respuesta = self.client.post(reverse('solicitar_retiro'), {'monto': '1000'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()['success'])
        self.assertFalse(SolicitudRetiro.objects.exists())