"""Portal del alumno sobre base_alumno: el marco (menu, barra, tema, hamburguesa) vive en una sola base.

Datos ficticios. Se vigila que el portal herede de la base y que el JS del marco no se duplique: un segundo
`const toggleTheme` o dos oyentes en la hamburguesa romperian el tema y el menu movil sin dar error visible.
"""

from django.urls import reverse

from tests.test_paquetes import RUT_ANA, Escenario


class BaseAlumnoTests(Escenario):

    def setUp(self):
        super().setUp()
        self.entrar(RUT_ANA)
        self.respuesta = self.client.get(reverse('alumno_pag1'))
        self.html = self.respuesta.content.decode()

    def test_el_portal_hereda_del_marco(self):
        self.assertTemplateUsed(self.respuesta, 'alumnos/base_alumno.html')
        self.assertTemplateUsed(self.respuesta, 'alumnos/Alumno_pag1.html')

    def test_el_js_del_marco_esta_una_sola_vez(self):
        self.assertEqual(self.html.count('function toggleTheme()'), 1)
        self.assertEqual(self.html.count("hamburgerBtn.addEventListener('click'"), 1)
        self.assertEqual(self.html.count('window.closeSidebar = closeSidebar'), 1)
        self.assertNotIn('const toggleTheme', self.html)  # la version vieja de la pagina

    def test_el_marco_trae_el_menu_la_barra_y_un_solo_main(self):
        self.assertEqual(self.html.count('<aside class="sidebar-menu"'), 1)
        self.assertEqual(self.html.count('id="portal-navbar"'), 1)
        self.assertEqual(self.html.count('<main'), 1)
