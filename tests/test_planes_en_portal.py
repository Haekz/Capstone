"""Planes dentro de cada portal: el alumno, el docente y el apoderado la ven con el menu del suyo; quien no ha entrado,
con el diseno publico. Datos ficticios.
"""

import pathlib
import re

from django.conf import settings
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
        self.assertEqual(sin_definir(HOJAS + PLANTILLAS, definidas_en=[*CSS_ADMIN, CSS_PORTAL, *HOJAS]), {})


def _leer(ruta):
    return re.sub(r'/\*.*?\*/', '', (pathlib.Path(settings.BASE_DIR) / ruta).read_text(encoding='utf-8'), flags=re.S)


def _luminancia(hexa):
    canales = [int(hexa.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(a, b):
    claro, oscuro = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


class ContrasteDeLaCasillaEnLaTarjetaOscuraTests(SimpleTestCase):
    """20-nov: los enlaces de Terminos usaban --primary sobre la tarjeta destacada (3,1:1; 2,7:1 en modo oscuro). WCAG
    2.2 AA pide 4,5:1 al texto y 3:1 al foco. Los colores se leen de los CSS: si alguien los cambia, la prueba lo ve."""

    PLANES = _leer(HOJAS[0])
    # --secondary y --accent: el sitio publico y el portal (base_alumno) definen los suyos.
    VARIABLES = _leer('alumnos/static/alumnos/css/styles/01_base.css') + _leer(
        'alumnos/static/alumnos/css/alumn_1/01_base.css') + _leer('alumnos/static/alumnos/css/alumn_1/10_ex_inline.css')
    ENLACE = '.plan-card.featured .pl-acepta a'
    FOCO = '.plan-card.featured .pl-acepta :is(a, input):focus-visible'

    def selectores_y_cuerpo(self, selector):
        for selectores, cuerpo in re.findall(r'([^{}]+)\{([^{}]*)\}', self.PLANES):
            lista = [s.strip() for s in re.split(r',(?![^()]*\))', selectores)]  # sin cortar :is(a, input)
            if selector in lista:
                return lista, cuerpo
        self.fail(f'planes.css no tiene la regla {selector}')

    def propiedad(self, selector, nombre):
        return re.search(rf'(?<![-\w]){nombre}\s*:\s*([^;]+);', self.selectores_y_cuerpo(selector)[1]).group(1).strip()

    def variables(self, nombre):
        valores = set(re.findall(rf'--{nombre}\s*:\s*(#[0-9a-fA-F]{{6}})\s*;', self.VARIABLES))
        self.assertTrue(valores, f'--{nombre} sin definir')
        return valores

    def fondos(self):
        return self.variables('secondary') | {self.propiedad('body.dark-mode .plan-card.featured', 'background')}

    def test_los_enlaces_se_leen_en_modo_claro_y_oscuro(self):
        color = self.propiedad(self.ENLACE, 'color')
        for fondo in self.fondos():
            with self.subTest(fondo=fondo):
                self.assertGreaterEqual(_contraste(color, fondo), 4.5)

    def test_el_foco_se_ve_en_modo_claro_y_oscuro(self):
        self.assertEqual(self.propiedad(self.FOCO, 'outline'), '2px solid var(--accent)')
        for acento in self.variables('accent'):
            for fondo in self.fondos():
                with self.subTest(acento=acento, fondo=fondo):
                    self.assertGreaterEqual(_contraste(acento, fondo), 3)

    def test_las_reglas_del_portal_no_le_ganan(self):
        """13_pulido.css pinta enlaces y foco con #portal-alumno: sin el ID, la tarjeta volveria a sus colores."""
        for selector in (self.ENLACE, self.FOCO):
            with self.subTest(selector=selector):
                self.assertIn(f'#portal-alumno {selector}', self.selectores_y_cuerpo(selector)[0])


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

    def test_el_apoderado_la_ve_en_su_portal_con_el_hero_oscuro(self):
        apoderado = crear_apoderado('44444444-4', Apoderado.VERIFICADO)
        entrar(self.client, apoderado, APODERADO)
        r = self.client.get(reverse('planes'))
        self.assertTemplateUsed(r, 'apoderados/base_apoderado.html')
        self.assertTemplateNotUsed(r, 'user_profesor/base_docente.html')
        self.assertContains(r, 'Portal apoderado')
        self.assertContains(r, 'class="apo-planes"')  # los ajustes de 16_portal_apoderado.css cuelgan de aqui
        self.assertContains(r, 'sv-eyebrow')  # conserva el hero oscuro de su diseño
        self.assertContains(r, '<h2>Elige cuántas clases quieres</h2>')  # h2: el h1 es el de la barra

    def test_el_marco_del_apoderado_no_llega_a_otros_ni_a_visitantes(self):
        for rol, quien in ((ALUMNO, self.ana), (PROFESOR, self.profesor), (None, None)):
            with self.subTest(rol=rol):
                if rol:
                    entrar(self.client, quien, rol)
                r = self.client.get(reverse('planes'))
                self.assertTemplateNotUsed(r, 'apoderados/base_apoderado.html')
                self.assertNotContains(r, 'apo-planes')
                self.client.logout()

    def test_quien_no_ha_entrado_ve_el_diseno_publico(self):
        r = self.client.get(reverse('planes'))
        self.assertTemplateNotUsed(r, 'alumnos/base_alumno.html')
        self.assertContains(r, 'sv-eyebrow')
        self.assertContains(r, 'Elige cuántas clases quieres')
