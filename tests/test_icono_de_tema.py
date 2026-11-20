"""Icono del boton de tema: en todos los portales muestra a que modo se pasa al hacer clic (luna en claro, sol en oscuro).

El admin, la moderacion de resenas, soporte y el docente comparten base_admin.html y mostraban el modo actual: al reves
que el portal del alumno y el sitio publico.
"""

from django.test import SimpleTestCase

from tests.css_vars import leer

BASE_ADMIN = 'admin_portal/templates/admin_portal/base_admin.html'
BASE_ALUMNO = 'alumnos/templates/alumnos/base_alumno.html'
LUNA_EN_CLARO = "isLight ? 'bi bi-moon-stars-fill' : 'bi bi-sun-fill'"


class IconoDeTemaTests(SimpleTestCase):

    def test_la_base_admin_muestra_luna_en_claro_y_sol_en_oscuro(self):
        fuente = leer(BASE_ADMIN)
        self.assertIn(LUNA_EN_CLARO, fuente)
        self.assertNotIn("isLight ? 'bi bi-sun-fill'", fuente)  # la forma anterior, al reves

    def test_se_pinta_en_un_solo_lugar(self):
        """Al hacer clic y al cargar la pagina el icono sale de la misma funcion."""
        self.assertEqual(leer(BASE_ADMIN).count(LUNA_EN_CLARO), 1)

    def test_el_alumno_sigue_la_misma_convencion(self):
        """Oscuro muestra el sol, claro la luna: la referencia con la que se alinean los demas."""
        fuente = leer(BASE_ALUMNO)
        self.assertIn("themeIcon.className = 'bi bi-sun-fill'", fuente)
        self.assertIn("themeIcon.className = 'bi bi-moon-stars-fill'", fuente)
