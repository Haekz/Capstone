"""Ajustes del admin (20-nov): el formulario guarda de verdad. Antes hacia preventDefault() y mostraba "Ajustes guardados"
sin enviar nada, y sus campos no tenian name.

Nombre y correo obligatorios; telefono y direccion opcionales (crear_admin no los pide). El RUT no se edita: es la
identidad de la cuenta y el registro de supresiones guarda su huella. Datos ficticios.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from alumnos.utils import normalizar_telefono
from tests.test_retiros import RUT_ADMIN, crear_admin, entrar_admin

VALIDOS = {'nombre': 'Tamara', 'correo': 'tamara@lbwus.cl', 'telefono': '+56 9 1234 5678', 'direccion': 'Av. Siempre Viva 742'}
CSS_PANTALLAS = settings.BASE_DIR / 'admin_portal/static/admin_portal/css/admin_panel/06c_pulido_admin_pantallas.css'


class LegibilidadDeLosCamposTests(SimpleTestCase):
    """Medido en el navegador (21-nov): con --text-muted el texto de ejemplo daba 2,75:1 en claro y el RUT de solo lectura
    tambien. Con --text-secondary dan 5,1:1 en claro y 8,0:1 en oscuro (minimo 4,5:1, WCAG 1.4.3)."""

    def test_el_texto_de_ejemplo_y_el_campo_de_solo_lectura_usan_el_color_legible(self):
        css = CSS_PANTALLAS.read_text(encoding='utf-8')
        self.assertRegex(css, r'#portal-admin \.form-input::placeholder \{\s*color: var\(--text-secondary\);\s*opacity: 1;')
        self.assertRegex(css, r'#portal-admin \.form-input\[readonly\] \{\s*color: var\(--text-secondary\);')


class NormalizarTelefonoTests(SimpleTestCase):

    def test_numeros_chilenos_quedan_en_sus_9_digitos(self):
        for texto in ('912345678', '9 1234 5678', '+56 9 1234 5678', '+56912345678', '56912345678', '(9) 1234-5678'):
            with self.subTest(texto=texto):
                self.assertEqual(normalizar_telefono(texto), '912345678')
        self.assertEqual(normalizar_telefono('2 2345 6789'), '223456789')  # fijo de Santiago

    def test_vacio_es_vacio(self):
        for texto in ('', '   ', None):
            with self.subTest(texto=texto):
                self.assertEqual(normalizar_telefono(texto), '')

    def test_lo_que_no_es_un_numero_chileno_es_none(self):
        for texto in ('12345678', '9123456789', '012345678', '112345678', '+1 912345678', 'nueve', '9123x5678'):
            with self.subTest(texto=texto):
                self.assertIsNone(normalizar_telefono(texto))


class AjustesDelAdminTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin, cls.tutor = crear_admin()
        cls.admin.email = 'admin@lbwus.cl'
        cls.admin.save(update_fields=['email'])
        get_user_model().objects.create_user(username='12345678-5', rut='12345678-5', email='otra@lbwus.cl',
                                             password='OtraClave123!', rol='alumno')

    def setUp(self):
        entrar_admin(self.client, self.admin, self.tutor)

    def guardar(self, **cambios):
        return self.client.post(reverse('ajustes_admin'), {**VALIDOS, **cambios})

    def admin_guardado(self):
        return get_user_model().objects.get(pk=self.admin.pk)

    def test_guarda_los_datos_y_vuelve_a_ajustes_con_aviso(self):
        respuesta = self.guardar()
        self.assertRedirects(respuesta, reverse('dashboard_admin') + '#ajustes', fetch_redirect_response=False)
        admin = self.admin_guardado()
        self.assertEqual((admin.first_name, admin.email, admin.telefono, admin.direccion),
                         ('Tamara', 'tamara@lbwus.cl', '912345678', 'Av. Siempre Viva 742'))
        pagina = self.client.get(reverse('dashboard_admin')).content.decode()
        self.assertIn('Guardamos tus datos.', pagina)
        self.assertIn('<div class="sidebar-user-name">Tamara</div>', pagina)  # el menu ya usa el nombre nuevo

    def test_el_rut_no_se_cambia_aunque_lo_envien(self):
        self.guardar(rut='11111111-1', username='11111111-1')
        admin = self.admin_guardado()
        self.assertEqual((admin.rut, admin.username), (RUT_ADMIN, RUT_ADMIN))

    def test_el_rut_se_muestra_de_solo_lectura_y_sin_name(self):
        pagina = self.client.get(reverse('dashboard_admin')).content.decode()
        self.assertRegex(pagina, rf'<input type="text" class="form-input" id="ajustes-rut" value="{RUT_ADMIN}" readonly')
        self.assertNotIn('name="rut"', pagina)

    def test_correo_de_otra_cuenta_se_rechaza_aunque_cambien_mayusculas(self):
        respuesta = self.guardar(correo='OTRA@lbwus.cl')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.admin_guardado().first_name, 'Admin')  # no se guardo nada
        self.assertErrorJuntoAlCampo(respuesta, 'correo', 'El correo electrónico ya está registrado en el sistema.')

    def test_puede_conservar_su_propio_correo(self):
        self.assertEqual(self.guardar(correo='ADMIN@lbwus.cl').status_code, 302)

    def test_telefono_invalido_muestra_el_error_junto_al_campo(self):
        respuesta = self.guardar(telefono='12345')
        self.assertErrorJuntoAlCampo(respuesta, 'telefono', 'Ingresa un teléfono chileno de 9 dígitos, por ejemplo 912345678 '
                                                'o +56 9 1234 5678.')
        self.assertEqual(self.admin_guardado().telefono, '')

    def test_telefono_y_direccion_son_opcionales(self):
        self.assertEqual(self.guardar(telefono='', direccion='').status_code, 302)
        admin = self.admin_guardado()
        self.assertEqual((admin.telefono, admin.direccion), ('', ''))

    def test_nombre_y_correo_son_obligatorios(self):
        respuesta = self.guardar(nombre='  ', correo='')
        self.assertErrorJuntoAlCampo(respuesta, 'nombre', 'Este campo es obligatorio.')
        self.assertErrorJuntoAlCampo(respuesta, 'correo', 'Este campo es obligatorio.')

    def test_con_errores_abre_ajustes_y_el_menu_conserva_el_nombre_guardado(self):
        html = self.guardar(nombre='Otro', telefono='1').content.decode()
        self.assertIn("const SECCION_INICIAL = 'ajustes';", html)
        self.assertIn('Revisa los campos marcados en Ajustes.', html)
        self.assertIn('<div class="sidebar-user-name">Admin</div>', html)  # no "Otro": no se guardo
        self.assertIn('value="Otro"', html)  # lo escrito no se pierde

    def test_solo_por_post(self):
        self.assertEqual(self.client.get(reverse('ajustes_admin')).status_code, 405)

    def test_sin_sesion_de_admin_no_cambia_nada(self):
        self.client.logout()
        respuesta = self.guardar()
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn(reverse('dashboard_admin'), respuesta['Location'])
        self.assertEqual(self.admin_guardado().first_name, 'Admin')

    def test_el_formulario_envia_de_verdad_con_etiquetas_asociadas(self):
        pagina = self.client.get(reverse('dashboard_admin')).content.decode()
        # La etiqueta completa: sin onsubmit que lo detenga (base_admin usa preventDefault en su buscador, eso no cuenta)
        self.assertIn(f'<form id="formAjustes" method="post" action="{reverse("ajustes_admin")}">', pagina)
        self.assertNotIn('Ajustes Guardados', pagina)
        for campo, autocompletar in (('nombre', 'given-name'), ('correo', 'email'), ('telefono', 'tel-national'),
                                     ('direccion', 'street-address')):
            with self.subTest(campo=campo):
                self.assertIn(f'<label class="form-label" for="ajustes-{campo}">', pagina)
                self.assertRegex(pagina, rf'id="ajustes-{campo}" name="{campo}"[^>]* autocomplete="{autocompletar}"')
        self.assertIn("const SECCION_INICIAL = 'resumen';", pagina)

    def assertErrorJuntoAlCampo(self, respuesta, campo, mensaje):
        """El mensaje va junto al campo, que queda marcado y apunta a el (WCAG 3.3.1)."""
        html = respuesta.content.decode()
        self.assertRegex(html, rf'id="ajustes-{campo}" name="{campo}"[^>]* aria-invalid="true" '
                               rf'aria-describedby="ajustes-{campo}-error"')
        self.assertIn(f'<p class="adm-error" id="ajustes-{campo}-error">{mensaje}</p>', html)
