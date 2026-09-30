"""Smoke tests del rediseño de front: cada página renderiza, sus CSS/imágenes
existen y trae lo necesario para funcionar en móvil (viewport + menú móvil)."""
import re
from datetime import date

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from alumnos.models import Alumno, Genero, Tutor

STATIC_REF = re.compile(r'(?:href|src)="/static/([^"?#]+)')
STATIC_HASH = re.compile(r'\.[0-9a-f]{8,64}(?=\.[^.]+$)')


def ruta_static_original(ruta):
    """Devuelve la ruta fuente de un static versionado por Django.

    Ejemplos:
    alumnos/css/styles.248bc9a549eb.css -> alumnos/css/styles.css
    alumnos/img/Logo.9a9827ced254.png -> alumnos/img/Logo.png

    Si la ruta no tiene hash, se devuelve sin cambios.
    """
    return STATIC_HASH.sub('', ruta)


class FrontRediseñoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Femenino')
        cls.user = User.objects.create_user(username='55555555-5', password='clave12345',
                                            email='front@lbwus.cl')
        cls.alumno = Alumno.objects.create(
            user=cls.user, nombre='Fran Front', rut='55555555-5', nivel_educacion='superior',
            direccion='Calle 5', fecha_nacimiento=date(1999, 1, 1),
            correo_electronico='front@lbwus.cl', genero=genero,
        )

    # ---------- helpers ----------
    def assertPaginaMovilOk(self, respuesta):
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertRegex(html, r'<meta name="viewport" content="width=device-width, initial-scale=1\.0">',
                         'Sin viewport la página se ve diminuta en el celular.')
        self.assertNotIn('href="#" class="auth-logo"', html, 'Quedó un enlace de maqueta (href="#").')
        for ruta in set(STATIC_REF.findall(html)):
            ruta_original = ruta_static_original(ruta)
            self.assertTrue(
                finders.find(ruta_original),
                f'No existe el archivo estático: {ruta_original} '
                f'(renderizado como: {ruta})'
            )
        return html

    def _login_alumno(self):
        self.client.force_login(self.user)
        sesion = self.client.session
        sesion['alumno_id'] = self.alumno.id_alumno
        sesion.save()

    def _login_admin(self):
        admin = Tutor.objects.create(**self._tutor_datos())
        sesion = self.client.session
        sesion['admin_id'] = admin.id_tutor
        sesion.save()

    def _tutor_datos(self):
        campos = {f.name for f in Tutor._meta.get_fields()}
        datos = {'nombre': 'Admin Front'}
        opcionales = {'rut': '66666666-6', 'correo_electronico': 'admin@lbwus.cl', 'telefono': '900000000',
                      'direccion': 'Oficina', 'fecha_nacimiento': date(1990, 1, 1),
                      'genero': Genero.objects.first(), 'password': 'x'}
        datos.update({k: v for k, v in opcionales.items() if k in campos})
        return datos

    # ---------- sitio público ----------
    def test_home_publico(self):
        html = self.assertPaginaMovilOk(self.client.get(reverse('home')))
        self.assertIn('hero-trust', html)
        self.assertIn('hamburger', html, 'El home necesita el menú hamburguesa para móvil.')

    # ---------- login / registro / recuperación ----------
    def test_login(self):
        html = self.assertPaginaMovilOk(self.client.get(reverse('login')))
        self.assertIn('csrfmiddlewaretoken', html)
        self.assertIn('auth-mobile-logo', html)

    def test_registro_alumno(self):
        self.assertPaginaMovilOk(self.client.get(reverse('regis_alum')))

    def test_recuperar_formulario_y_envio(self):
        html = self.assertPaginaMovilOk(self.client.get(reverse('password_reset')))
        self.assertIn('csrfmiddlewaretoken', html)
        respuesta = self.client.post(reverse('password_reset'), {'email': 'front@lbwus.cl'}, follow=True)
        self.assertContains(respuesta, 'Revisa tu correo')

    def test_recuperar_link_valido_y_cambio(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        respuesta = self.client.get(reverse('password_reset_confirm', args=[uid, token]), follow=True)
        html = self.assertPaginaMovilOk(respuesta)
        self.assertIn('name="new_password1"', html)
        self.assertIn('name="new_password2"', html)
        respuesta = self.client.post(respuesta.redirect_chain[-1][0],
                                     {'new_password1': 'NuevaClave#2026', 'new_password2': 'NuevaClave#2026'},
                                     follow=True)
        self.assertContains(respuesta, 'Contraseña actualizada')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NuevaClave#2026'))

    def test_recuperar_link_vencido(self):
        respuesta = self.client.get(reverse('password_reset_confirm', args=['MQ', 'token-malo']))
        html = self.assertPaginaMovilOk(respuesta)
        self.assertIn('ya no es válido', html)

    # ---------- portal alumno ----------
    def test_portal_alumno(self):
        self._login_alumno()
        html = self.assertPaginaMovilOk(self.client.get(reverse('alumno_pag1')))
        self.assertIn('id="hamburger-btn"', html)
        self.assertIn('id="sidebar-menu"', html)
        self.assertIn('sidebar-overlay', html)

    # ---------- portal admin ----------
    def test_admin_paginas(self):
        self._login_admin()
        for nombre in ['dashboard_admin', 'crud', 'alumnos_Add', 'planes_adm', 'nosotros_adm', 'contactos_adm']:
            with self.subTest(pagina=nombre):
                html = self.assertPaginaMovilOk(self.client.get(reverse(nombre)))
                self.assertIn('id="sidebar-toggle"', html, 'Falta el botón del menú móvil del admin.')
                self.assertIn('id="sidebar-overlay"', html)

    def test_admin_sesion_cerrada(self):
        html = self.assertPaginaMovilOk(self.client.get(reverse('home_adm')))
        self.assertIn('Sesión cerrada', html)

    # ---------- modo oscuro sin destello blanco ----------
    def assertTemaAntesDelContenido(self, html, clave):
        """El tema guardado debe aplicarse apenas abre el <body>, antes de pintar nada.

        Si se aplica en DOMContentLoaded, el navegador alcanza a mostrar la
        pagina clara y en modo oscuro se ve un destello blanco al navegar.
        """
        cuerpo = html[html.index('<body'):]
        primer_script = cuerpo.index('<script')
        self.assertIn(f"localStorage.getItem('{clave}')", cuerpo[primer_script:primer_script + 400])
        antes = re.sub(r'<body[^>]*>', '', cuerpo[:primer_script])
        self.assertEqual(antes.strip(), '', 'Hay contenido antes del script del tema.')

    def test_modo_oscuro_sin_destello(self):
        self._login_alumno()
        for nombre in ['home', 'nosotros', 'servicios', 'planes', 'contactos', 'alumno_pag1']:
            with self.subTest(pagina=nombre):
                self.assertTemaAntesDelContenido(self.client.get(reverse(nombre)).content.decode(), 'theme')
        self._login_admin()
        self.assertTemaAntesDelContenido(self.client.get(reverse('dashboard_admin')).content.decode(),
                                         'admin-theme')


class MenuCuentaTests(TestCase):
    """Circulo con iniciales en el navbar: portal, cambiar contrasena y cerrar sesion."""

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Femenino')
        cls.user = User.objects.create_user(username='77777777-7', password='ClaveVieja#1')
        cls.alumno = Alumno.objects.create(
            user=cls.user, nombre='Alumno Prueba', rut='77777777-7', nivel_educacion='media',
            direccion='Calle 7', fecha_nacimiento=date(2001, 1, 1),
            correo_electronico='menu@lbwus.cl', genero=genero,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_navbar_muestra_circulo_con_iniciales_y_opciones(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('id="cuenta-btn"', html)
        self.assertRegex(html, r'class="cuenta-avatar"[^>]*>\s*AP\s*</button>')
        for url in [reverse('alumno_pag1'), reverse('password_change'), reverse('logout_alumno')]:
            self.assertIn(f'href="{url}"', html)
        self.assertNotIn('sesion-saludo', html, 'Quedó el saludo antiguo "Hola, ...".')

    def test_anonimo_no_ve_menu_de_cuenta(self):
        self.client.logout()
        html = self.client.get(reverse('home')).content.decode()
        self.assertNotIn('id="cuenta-btn"', html)
        self.assertIn(reverse('login'), html)

    def test_cambiar_clave_requiere_sesion(self):
        self.client.logout()
        respuesta = self.client.get(reverse('password_change'))
        self.assertEqual(respuesta.status_code, 302)

    def test_cambiar_clave_rechaza_clave_actual_incorrecta(self):
        respuesta = self.client.post(reverse('password_change'), {
            'old_password': 'no-es-esta', 'new_password1': 'ClaveNueva#2', 'new_password2': 'ClaveNueva#2'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'field-error')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ClaveVieja#1'))

    def test_cambiar_clave_funciona_y_mantiene_la_sesion(self):
        pagina = self.client.get(reverse('password_change'))
        self.assertContains(pagina, 'csrfmiddlewaretoken')
        self.assertContains(pagina, 'name="old_password"')

        respuesta = self.client.post(reverse('password_change'), {
            'old_password': 'ClaveVieja#1', 'new_password1': 'ClaveNueva#2', 'new_password2': 'ClaveNueva#2'},
            follow=True)
        self.assertContains(respuesta, 'Contraseña actualizada')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ClaveNueva#2'))
        # Django rota la sesion al cambiar la clave: el usuario sigue dentro
        self.assertTrue(self.client.get(reverse('home')).context['usuario_sesion']['autenticado'])


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
        cls.alumno = Alumno.objects.create(
            user=cls.user, nombre='Ana Atras', rut='88888888-8', nivel_educacion='basica',
            direccion='Calle 8', fecha_nacimiento=date(2002, 2, 2),
            correo_electronico='atras@lbwus.cl', genero=genero,
        )
        cls.admin_user = User.objects.create_user(username='99999999-9', password='clave12345')
        cls.tutor = Tutor.objects.create(
            user=cls.admin_user, nombre='Admin Atras', rut='99999999-9', direccion='Oficina',
            fecha_nacimiento=date(1990, 1, 1), correo_electronico='admin.atras@lbwus.cl', genero=genero,
        )

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
        self.assertRedirects(self.client.get(reverse('login')), reverse('alumno_pag1'),
                             fetch_redirect_response=False)

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
        self.assertIn(f'href="{reverse("home")}" class="sb-home"', html)
        self.assertIn(reverse('logout_alumno'), html)

        self._entrar(self.admin_user, 'admin_id', self.tutor.id_tutor)
        html = self.client.get(reverse('dashboard_admin')).content.decode()
        self.assertIn(f'href="{reverse("home")}" class="sidebar-home"', html)
        self.assertIn(reverse('logout_admin'), html)
