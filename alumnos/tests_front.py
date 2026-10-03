from alumnos.models import Especialidad
'Smoke tests del rediseño de front: cada página renderiza, sus CSS/imágenes\nexisten y trae lo necesario para funcionar en móvil (viewport + menú móvil).'
import re
from datetime import date
from django.contrib.auth import get_user_model
User = get_user_model()
from django.contrib.auth.tokens import default_token_generator
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from alumnos.models import Alumno, Genero, Tutor
STATIC_REF = re.compile('(?:href|src)="/static/([^"?#]+)')
STATIC_HASH = re.compile('\\.[0-9a-f]{8,64}(?=\\.[^.]+$)')

def ruta_static_original(ruta):
    """Devuelve la ruta fuente de un static versionado por Django.

    Ejemplos:
    alumnos/css/styles.248bc9a549eb.css -> alumnos/css/styles.css
    alumnos/img/Logo.9a9827ced254.png -> alumnos/img/Logo.png

    Si la ruta no tiene hash, se devuelve sin cambios.
    """
    return STATIC_HASH.sub('', ruta)

class BotonAtrasTests(TestCase):
    """Con "atras" el navegador no debe mostrar copias guardadas.

    Login: si hay sesion, el servidor manda al portal (no a un login viejo).
    Paginas privadas: tras cerrar sesion, no deben verse desde la memoria.
    """
    PRIVADAS_ADMIN = ['dashboard_admin', 'crud', 'alumnos_Add', 'planes_adm', 'nosotros_adm', 'contactos_adm']

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        cls.user = User.objects.create_user(username='88888888-8', password='clave12345')
        cls.alumno = Alumno.objects.create(user=cls.user, nivel_educacion='basica')
        cls.admin_user = User.objects.create_user(username='99999999-9', password='clave12345')
        cls.tutor = Tutor.objects.create(user=cls.admin_user)

    def _entrar(self, user, clave, valor):
        self.client.force_login(user)
        sesion = self.client.session
        sesion[clave] = valor
        sesion.save()

    def assertNoSeGuarda(self, respuesta):
        self.assertIn('no-store', respuesta.get('Cache-Control', ''))
        self.assertIn('e.persisted', respuesta.content.decode(), 'Falta el seguro para el bfcache.')

    def test_login_no_se_guarda_en_el_navegador(self):
        self.assertNoSeGuarda(self.client.get(reverse('login')))

    def test_login_con_sesion_manda_al_portal(self):
        self._entrar(self.user, 'alumno_id', self.alumno.id_alumno)
        self.assertRedirects(self.client.get(reverse('login')), reverse('alumno_pag1'), fetch_redirect_response=False)

    def test_portal_alumno_no_se_guarda(self):
        self._entrar(self.user, 'alumno_id', self.alumno.id_alumno)
        self.assertNoSeGuarda(self.client.get(reverse('alumno_pag1')))

    def test_paginas_admin_no_se_guardan(self):
        self._entrar(self.admin_user, 'admin_id', self.tutor.id_tutor)
        for nombre in self.PRIVADAS_ADMIN:
            with self.subTest(pagina=nombre):
                self.assertNoSeGuarda(self.client.get(reverse(nombre)))

    def test_cambiar_clave_no_se_guarda(self):
        self._entrar(self.user, 'alumno_id', self.alumno.id_alumno)
        self.assertIn('no-store', self.client.get(reverse('password_change')).get('Cache-Control', ''))

    def test_portales_tienen_boton_volver_al_inicio(self):
        self._entrar(self.user, 'alumno_id', self.alumno.id_alumno)
        html = self.client.get(reverse('alumno_pag1')).content.decode()
        self.assertIn(f'''href="{reverse('home')}" class="sb-home"''', html)
        self.assertIn(reverse('logout_alumno'), html)
        self._entrar(self.admin_user, 'admin_id', self.tutor.id_tutor)
        html = self.client.get(reverse('dashboard_admin')).content.decode()
        self.assertIn(f'''href="{reverse('home')}" class="sidebar-home"''', html)
        self.assertIn(reverse('logout_admin'), html)