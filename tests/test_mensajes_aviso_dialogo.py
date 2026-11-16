"""Aviso legal de los mensajes (E5): el apoderado y el profesor lo leen en una ventana que abre el boton "?"; el alumno,
desplegado en su pagina. Es el mismo texto legal: si alguien lo corrige en un solo lado, estas pruebas fallan. Datos ficticios.
"""

import re

from django.template import Context, Template
from django.test import SimpleTestCase
from django.urls import reverse

from alumnos.roles import APODERADO, PROFESOR
from apoderados.models import Apoderado
from tests.test_apoderados import crear_apoderado
from tests.test_resenas import BaseResenas, entrar


def _items(html):
    """El texto de cada punto de la lista, sin etiquetas, en minusculas y sin ':' (el desplegable los pone, la ventana no)."""
    puntos = re.findall(r'<li\b.*?</li>', html, re.S)
    return [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', p).replace(':', '')).strip().lower() for p in puntos]


def _pintar(plantilla):
    return Template('{% load mensajes_tags %}' + plantilla).render(Context({}))


class MismoTextoLegalTests(SimpleTestCase):

    def test_la_ventana_dice_lo_mismo_que_el_desplegable_en_cada_rol(self):
        for rol in ('apoderado', 'profesor'):
            with self.subTest(rol=rol):
                desplegable = _items(_pintar(f"{{% aviso_mensajes '{rol}' %}}"))
                ventana = _items(_pintar(f"{{% dialogo_aviso_mensajes '{rol}' %}}"))
                self.assertEqual(len(desplegable), 6)
                self.assertEqual(ventana, desplegable)

    def test_los_plazos_salen_de_las_constantes(self):
        from mensajes import retencion, revision
        for rol in ('apoderado', 'profesor'):
            with self.subTest(rol=rol):
                ventana = _pintar(f"{{% dialogo_aviso_mensajes '{rol}' %}}")
                self.assertIn(f'{retencion.DIAS_SIN_ACTIVIDAD} d\u00edas sin mensajes', ventana)
                self.assertIn(f'cada {revision.MESES_REVISION} meses', ventana)

    def test_el_boton_de_cierre_usa_la_clase_de_cada_portal(self):
        # el profesor trae su propio boton (.di-pie .prof-form-btn en su hoja); el apoderado, el principal del portal
        self.assertIn('class="prof-form-btn prof-btn-auto di-ok"', _pintar("{% dialogo_aviso_mensajes 'profesor' %}"))
        self.assertIn('class="btn-principal di-ok"', _pintar("{% dialogo_aviso_mensajes 'apoderado' %}"))

    def test_alumno_y_profesor_conservan_su_aviso_desplegable(self):
        for rol in ('alumno', 'profesor'):
            with self.subTest(rol=rol):
                aviso = _pintar(f"{{% aviso_mensajes '{rol}' %}}")
                self.assertIn('<details class="aviso-mensajes" open', aviso)
                self.assertNotIn('dialogo-mensajes', aviso)


class AvisoEnElBuzonTests(BaseResenas):

    def test_el_profesor_lo_abre_con_el_boton_y_no_lo_ve_desplegado(self):
        entrar(self.client, self.profesor, PROFESOR)
        html = self.client.get(reverse('panel_profesor')).content.decode()
        self.assertIn('class="btn-ayuda-mensajes"', html)
        self.assertIn('aria-controls="dialogo-mensajes"', html)
        self.assertIn('<dialog class="dialogo-info" id="dialogo-mensajes"', html)
        self.assertNotIn('aviso-mensajes', html)
        self.assertEqual(html.count('id="dialogo-mensajes"'), 1)  # una sola ventana, la del botón

    def test_el_apoderado_lo_abre_con_el_boton_y_no_lo_ve_desplegado(self):
        apoderado = crear_apoderado('44444444-4', Apoderado.VERIFICADO)
        entrar(self.client, apoderado, APODERADO)
        r = self.client.get(reverse('mensajes_apoderado'))
        self.assertContains(r, 'class="btn-ayuda-mensajes"')
        self.assertContains(r, 'aria-controls="dialogo-mensajes"')
        self.assertContains(r, '<dialog class="dialogo-info" id="dialogo-mensajes"')
        self.assertNotContains(r, 'aviso-mensajes')
