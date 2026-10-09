from django.test import TestCase, Client
from django.urls import reverse
from alumnos.models import CustomUser, Alumno, Profesor, Tutor
from datetime import date

class AuthenticationIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Configurar datos iniciales que no cambian entre pruebas
        cls.alumno_user = CustomUser.objects.create_user(
            username='11111111-1', rut='11111111-1', email='alumno@test.com', password='password123', rol='alumno',
            first_name='Juan', last_name='Perez'
        )
        cls.alumno_profile = Alumno.objects.create(user=cls.alumno_user)

        cls.prof_user = CustomUser.objects.create_user(
            username='22222222-2', rut='22222222-2', email='profesor@test.com', password='password123', rol='profesor',
            first_name='Maria', last_name='Gomez'
        )
        cls.prof_profile = Profesor.objects.create(user=cls.prof_user)

        cls.admin_user = CustomUser.objects.create_user(
            username='33333333-3', rut='33333333-3', email='admin@test.com', password='password123', rol='admin',
            first_name='Carlos', last_name='Soto'
        )
        cls.admin_profile = Tutor.objects.create(user=cls.admin_user)

    def setUp(self):
        # Se ejecuta antes de cada prueba individual
        self.client = Client()

    def test_login_rut_normal(self):
        """Regresión: Probar inicio de sesión con RUT normal (con guión)."""
        response = self.client.post(reverse('login'), {'username': '11111111-1', 'password': 'password123'})
        self.assertRedirects(response, reverse('alumno_pag1'), fetch_redirect_response=False)

    def test_login_rut_sin_guion(self):
        """Regresión: Probar inicio de sesión con RUT sin guión."""
        response = self.client.post(reverse('login'), {'username': '111111111', 'password': 'password123'})
        self.assertRedirects(response, reverse('alumno_pag1'), fetch_redirect_response=False)

    def test_login_rut_con_puntos(self):
        """Regresión: Probar inicio de sesión con RUT con puntos y guión."""
        response = self.client.post(reverse('login'), {'username': '11.111.111-1', 'password': 'password123'})
        self.assertRedirects(response, reverse('alumno_pag1'), fetch_redirect_response=False)

    def test_login_email(self):
        """Regresión: Probar inicio de sesión usando el correo electrónico."""
        response = self.client.post(reverse('login'), {'username': 'alumno@test.com', 'password': 'password123'})
        self.assertRedirects(response, reverse('alumno_pag1'), fetch_redirect_response=False)

    def test_role_based_redirection(self):
        """Integración: Probar la redirección automática basada en el rol."""
        # Login Alumno
        response_alumno = self.client.post(reverse('login'), {'username': '11111111-1', 'password': 'password123'})
        self.assertRedirects(response_alumno, reverse('alumno_pag1'), fetch_redirect_response=False)
        self.client.logout()

        # Login Profesor
        response_prof = self.client.post(reverse('login'), {'username': '22222222-2', 'password': 'password123'})
        self.assertRedirects(response_prof, reverse('panel_profesor'), fetch_redirect_response=False)
        self.client.logout()

        # Login Admin/Tutor
        response_admin = self.client.post(reverse('login'), {'username': '33333333-3', 'password': 'password123'})
        self.assertRedirects(response_admin, reverse('dashboard_admin'), fetch_redirect_response=False)

    def test_invalid_login(self):
        """Regresión: Probar inicio de sesión con credenciales inválidas."""
        response = self.client.post(reverse('login'), {'username': '11111111-1', 'password': 'wrongpassword'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'RUT/Correo o contraseña incorrectos. Inténtalo de nuevo.')