"""Planes dentro de cada portal: el alumno y el docente la ven con su menu; el apoderado y quien no ha entrado, con el
diseno publico. Datos ficticios.
"""

from django.test import SimpleTestCase
from django.urls import reverse

from alumnos.roles import ALUMNO, APODERADO, PROFESOR
from apoderados.models import Apoderado
from tests.css_vars import sin_definir
from tests.test_apoderados import crear_apoderado
from tests.test_panel_docente_layout import CSS_ADMIN, CSS_PORTAL
from tests.test_portal_alumno_variables import PAGINA_ALUMNO
from tests.test_resenas import BaseResenas, entrar

HOJAS = ['alumnos/static/alumnos/css/planes.css']
PLANTILLAS = ['alumnos/templates/alumnos/planes.html']


class VariablesCssDePlanesTests(SimpleTestCase):
    """Una variable sin definir no da error: el borde o el fondo desaparecen. Cada portal hace su puente."""

    def test_en_el_portal_del_alumno(self):
        self.assertEqual(sin_definir(HOJAS + PLANTILLAS, definidas_en=PAGINA_ALUMNO + HOJAS), {})

    def test_en_el_portal_del_docente(self):
        self.assertEqual(sin_definir(HOJAS + PLANTILLAS, definidas_en=[CSS_ADMIN, CSS_PORTAL, *HOJAS]), {})


class PlanesEnElPortalTests(BaseResenas):

    CIERRE_DEL_MODAL = "getElementById('close-modal-btn')"

    def test_el_modal_de_bienvenida_se_puede_cerrar_en_cada_marco(self):
        """Su script iba en extra_js, que solo existe en la base publica: en los portales el modal no se cerraba."""
        apoderado = crear_apoderado('44444444-4', Apoderado.VERIFICADO)
        for rol, quien in ((ALUMNO, self.ana), (PROFESOR, self.profesor), (APODERADO, apoderado), (None, None)):
            with self.subTest(rol=rol):
                if rol:
                    entrar(self.client, quien, rol)
                self.assertContains(self.client.get(reverse('planes')), self.CIERRE_DEL_MODAL)
                self.client.logout()

    def test_el_alumno_la_ve_en_su_portal_con_paquetes_marcado(self):
        entrar(self.client, self.ana, ALUMNO)
        r = self.client.get(reverse('planes'))
        self.assertTemplateUsed(r, 'alumnos/base_alumno.html')
        self.assertContains(r, '<h1 id="portal-title">Planes y precios</h1>')
        self.assertContains(r, "paquetes: 'view-plans'")  # el JS marca Mis Paquetes...
        self.assertContains(r, "}['paquetes']")  # ...porque la vista pidio esa seccion
        self.assertEqual(r.content.decode().count('<h1'), 1)
        self.assertNotContains(r, 'sv-eyebrow')  # sin el hero del sitio publico

    def test_el_docente_la_ve_en_su_portal(self):
        entrar(self.client, self.profesor, PROFESOR)
        r = self.client.get(reverse('planes'))
        self.assertTemplateUsed(r, 'user_profesor/base_docente.html')
        self.assertContains(r, 'portal_docente.css')
        self.assertContains(r, 'pl-intro--portal')
        self.assertNotContains(r, 'sv-eyebrow')

    def test_el_apoderado_sigue_en_el_diseno_publico(self):
        apoderado = crear_apoderado('44444444-4', Apoderado.VERIFICADO)
        entrar(self.client, apoderado, APODERADO)
        r = self.client.get(reverse('planes'))
        self.assertTemplateNotUsed(r, 'alumnos/base_alumno.html')
        self.assertTemplateNotUsed(r, 'user_profesor/base_docente.html')
        self.assertContains(r, 'sv-eyebrow')

    def test_quien_no_ha_entrado_ve_el_diseno_publico(self):
        r = self.client.get(reverse('planes'))
        self.assertTemplateNotUsed(r, 'alumnos/base_alumno.html')
        self.assertContains(r, 'sv-eyebrow')
        self.assertContains(r, 'Elige cuántas clases quieres')
