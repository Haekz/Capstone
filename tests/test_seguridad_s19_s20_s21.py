import importlib
from django.test import TestCase, override_settings
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from alumnos.models import Genero, Alumno, Profesor, Tutor

User = get_user_model()


class TestS19LogoutMetodoSeguro(TestCase):
    """S-19: Eliminar métodos de logout inseguros vía GET.
    
    El cierre de sesión altera el estado de la aplicación y la sesión del usuario.
    Conforme a RFC 7231, Django 5.x y los estándares de seguridad OWASP
    (Session Management & Cross-Site Request Forgery), el logout DEBE ejecutarse
    exclusivamente mediante peticiones HTTP POST con protección CSRF.
    Cualquier petición GET debe ser rechazada con HTTP 405 (Method Not Allowed).
    """

    def setUp(self):
        self.genero = Genero.objects.create(descripcion='No especificado')

        # Alumno
        self.user_alumno = User.objects.create_user(
            username='12345678-5',
            rut='12345678-5',
            email='alumno_seguro@test.cl',
            password='Password123!',
            rol='alumno',
            genero=self.genero
        )
        self.alumno = Alumno.objects.create(user=self.user_alumno)

        # Admin
        self.user_admin = User.objects.create_user(
            username='11111111-1',
            rut='11111111-1',
            email='admin_seguro@test.cl',
            password='Password123!',
            rol='admin',
            genero=self.genero
        )
        self.admin = Tutor.objects.create(user=self.user_admin)

        # Profesor
        self.user_prof = User.objects.create_user(
            username='22222222-2',
            rut='22222222-2',
            email='prof_seguro@test.cl',
            password='Password123!',
            rol='profesor',
            genero=self.genero
        )
        self.profesor = Profesor.objects.create(user=self.user_prof)

    def test_logout_alumno_rechaza_get(self):
        """GET /alumnos/logout_alumno/ debe responder 405 Method Not Allowed."""
        self.client.force_login(self.user_alumno)
        response = self.client.get(reverse('logout_alumno'))
        self.assertEqual(response.status_code, 405)

    def test_logout_admin_rechaza_get(self):
        """GET /admin_portal/logout_admin/ debe responder 405 Method Not Allowed."""
        self.client.force_login(self.user_admin)
        response = self.client.get(reverse('logout_admin'))
        self.assertEqual(response.status_code, 405)

    def test_logout_prof_rechaza_get(self):
        """GET /profesor/logout debe responder 405 Method Not Allowed."""
        self.client.force_login(self.user_prof)
        response = self.client.get(reverse('logout_prof'))
        self.assertEqual(response.status_code, 405)

    def test_logout_alumno_via_post_cierra_sesion_exitosamente(self):
        """POST /alumnos/logout_alumno/ debe invalidar sesión y redirigir a 'home'."""
        self.client.force_login(self.user_alumno)
        session = self.client.session
        session['alumno_id'] = self.alumno.id_alumno
        session.save()

        response = self.client.post(reverse('logout_alumno'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('alumno_id', self.client.session)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_admin_via_post_cierra_sesion_exitosamente(self):
        """POST /admin_portal/logout_admin/ debe invalidar sesión y redirigir a 'home'."""
        self.client.force_login(self.user_admin)
        session = self.client.session
        session['admin_id'] = self.admin.id_tutor
        session.save()

        response = self.client.post(reverse('logout_admin'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('admin_id', self.client.session)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_prof_via_post_cierra_sesion_exitosamente(self):
        """POST /profesor/logout debe invalidar sesión y redirigir a 'home'."""
        self.client.force_login(self.user_prof)
        session = self.client.session
        session['profesor_id'] = self.profesor.id_profesor
        session.save()

        response = self.client.post(reverse('logout_prof'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('profesor_id', self.client.session)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_plantillas_contienen_formulario_post_y_csrf_para_logout(self):
        """Verifica que los templates de los portales rendericen <form method='post'> con token CSRF."""
        # 1. Navbar con sesión de alumno
        self.client.force_login(self.user_alumno)
        session = self.client.session
        session['alumno_id'] = self.alumno.id_alumno
        session.save()
        resp_home = self.client.get(reverse('home'))
        html_home = resp_home.content.decode('utf-8')
        self.assertIn('form-logout-desktop', html_home)
        self.assertIn('form-logout-mobile', html_home)
        self.assertIn('csrfmiddlewaretoken', html_home)
        self.assertIn(reverse('logout_alumno'), html_home)

        # 2. Portal alumno
        resp_alum = self.client.get(reverse('alumno_pag1'))
        html_alum = resp_alum.content.decode('utf-8')
        self.assertIn('form-sb-logout', html_alum)
        self.assertIn('csrfmiddlewaretoken', html_alum)
        self.assertIn(reverse('logout_alumno'), html_alum)

        # 3. Portal admin
        self.client.force_login(self.user_admin)
        session = self.client.session
        session['admin_id'] = self.admin.id_tutor
        session.save()
        resp_admin = self.client.get(reverse('dashboard_admin'))
        html_admin = resp_admin.content.decode('utf-8')
        self.assertIn('form-sidebar-logout', html_admin)
        self.assertIn('csrfmiddlewaretoken', html_admin)
        self.assertIn(reverse('logout_admin'), html_admin)

        # 4. Portal profesor
        self.client.force_login(self.user_prof)
        session = self.client.session
        session['profesor_id'] = self.profesor.id_profesor
        session.save()
        resp_prof = self.client.get(reverse('panel_profesor'))
        html_prof = resp_prof.content.decode('utf-8')
        self.assertIn('form-prof-logout', html_prof)
        self.assertIn('csrfmiddlewaretoken', html_prof)
        self.assertIn(reverse('logout_prof'), html_prof)


class TestS20GoogleLoginSeguro(TestCase):
    """S-20: Desactivar login Google por GET y exigir POST con CSRF.
    
    Iniciación de autenticación OAuth por GET expone al usuario a ataques de
    Login CSRF (OWASP). SOCIALACCOUNT_LOGIN_ON_GET debe ser estrictamente False,
    y el botón de Google debe ser un formulario POST con token CSRF.
    """

    def setUp(self):
        app = SocialApp.objects.create(provider='google', name='Google', client_id='test_id', secret='test_secret')
        app.sites.add(Site.objects.get_current())

    def test_socialaccount_login_on_get_desactivado(self):
        """SOCIALACCOUNT_LOGIN_ON_GET debe ser False."""
        self.assertFalse(
            getattr(settings, 'SOCIALACCOUNT_LOGIN_ON_GET', True),
            "SOCIALACCOUNT_LOGIN_ON_GET debe ser estrictamente False para prevenir Login CSRF"
        )

    def test_google_login_via_get_no_inicia_oauth_directo(self):
        """Petición GET a /accounts/google/login/ no debe redirigir a Google directamente."""
        response = self.client.get('/accounts/google/login/')
        if response.status_code == 302:
            self.assertNotIn('accounts.google.com', response.url)

    def test_formulario_login_contiene_post_csrf_para_google(self):
        """La pantalla de login debe incluir un formulario POST con token CSRF para Google."""
        response = self.client.get(reverse('login'))
        html = response.content.decode('utf-8')
        self.assertIn('form-google', html)
        self.assertIn('btn-google', html)
        self.assertIn('csrfmiddlewaretoken', html)


class TestS21RutasTestErrorRestringidasADebug(TestCase):
    """S-21: Limitar rutas test404/ y test500/ a DEBUG=True.
    
    Rutas de diagnóstico o prueba de plantillas de error jamás deben quedar
    expuestas en entornos de producción.
    """

    def test_rutas_test_estan_definidas_condicionalmente_segun_debug(self):
        """Verifica que el archivo urls.py evalúe settings.DEBUG antes de añadir test404/test500."""
        import lbwus.urls as urls_module
        
        # Simular recarga con DEBUG = False
        with override_settings(DEBUG=False):
            importlib.reload(urls_module)
            nombres_rutas = [getattr(p, 'name', None) for p in urls_module.urlpatterns]
            patrones_str = [str(p.pattern) for p in urls_module.urlpatterns]
            self.assertNotIn('test404', nombres_rutas)
            self.assertNotIn('test500', nombres_rutas)
            self.assertFalse(any('test404' in s for s in patrones_str))
            self.assertFalse(any('test500' in s for s in patrones_str))

        # Simular recarga con DEBUG = True
        with override_settings(DEBUG=True):
            importlib.reload(urls_module)
            nombres_rutas = [getattr(p, 'name', None) for p in urls_module.urlpatterns]
            self.assertIn('test404', nombres_rutas)
            self.assertIn('test500', nombres_rutas)

        # Restaurar estado original del módulo
        importlib.reload(urls_module)
