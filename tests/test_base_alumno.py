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

    def test_el_portal_abre_la_vista_que_pide_el_hash(self):
        # El menu de otras paginas del portal (Notificaciones) llega con #view-... (o #tab-..., Mis videos: B5);
        # solo valen las vistas con boton.
        self.assertEqual(self.html.count('window.location.hash.slice(1)'), 1)
        self.assertIn("(b.dataset.tab || b.dataset.view) === vista", self.html)

    def test_fuera_del_portal_el_menu_lleva_al_portal_con_su_vista(self):
        # Rama del marco para paginas sin vistas: sin ella los botones del menu no harian nada.
        self.assertIn('const irAlPortal', self.html)
        self.assertIn(f'window.location.href = "{reverse("alumno_pag1")}#" + vista', self.html)
        self.assertIn('window.switchView = irAlPortal', self.html)  # la ficha del alumno la llama con onclick

    def test_el_boton_dashboard_del_menu_viene_activo_en_el_portal(self):
        self.assertIn('sidebar-view-btn active" data-view="view-dashboard"', self.html)
