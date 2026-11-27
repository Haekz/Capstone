"""Bloque de reseñas rediseñado: orden, filtro por estrellas y páginas (los arma resenas_pulido.js con lo que ya trae la
página). Perfil del profesor (portal del alumno) y Mis reseñas (portal docente). Datos ficticios.
"""

import re

from django.urls import reverse

from alumnos.roles import ALUMNO, PROFESOR
from tests.css_vars import leer
from tests.test_resenas import BaseResenas, entrar

CSS = 'resenas/static/resenas/resenas_pulido.css'


class BloqueDeResenasTests(BaseResenas):

    def setUp(self):
        self.resena(self.insc_paquete, puntaje=4, comentario='Muy clara')
        self.resena(self.insc_bea, puntaje=2, comentario='Llegó tarde')

    def paginas(self):
        entrar(self.client, self.ana, ALUMNO)
        perfil = self.client.get(reverse('perfil_profesor', args=[self.profesor.id_profesor]))
        self.client.logout()
        entrar(self.client, self.profesor, PROFESOR)
        return {'perfil': perfil, 'mis_resenas': self.client.get(reverse('resenas_profesor'))}

    def test_trae_la_barra_las_paginas_y_el_puntaje_de_cada_resena(self):
        for nombre, r in self.paginas().items():
            with self.subTest(pagina=nombre):
                self.assertContains(r, '<div class="resenas-barra" hidden>')  # oculta: la muestra el JS
                self.assertContains(r, '<nav class="resenas-paginas" aria-label="Páginas de reseñas" hidden></nav>')
                self.assertContains(r, 'data-puntaje="4"')
                self.assertContains(r, 'data-puntaje="2"')
                self.assertContains(r, 'resenas/resenas_pulido.css')
                self.assertContains(r, 'resenas/resenas_pulido.js')

    def test_los_tres_modos_de_orden_son_los_que_entiende_el_js(self):
        r = self.paginas()['perfil']
        for valor in ('recientes', 'mejores', 'peores'):
            self.assertContains(r, f'<option value="{valor}">')

    def test_sin_reseñas_no_hay_barra_ni_paginas(self):
        entrar(self.client, self.otro_profesor, PROFESOR)
        r = self.client.get(reverse('resenas_profesor'))
        self.assertContains(r, 'resenas-vacio')
        self.assertNotContains(r, 'resenas-barra')
        self.assertNotContains(r, 'resenas-paginas')

    def test_el_contenedor_mr_es_solo_de_mis_resenas(self):
        paginas = self.paginas()
        self.assertContains(paginas['mis_resenas'], 'class="perfil-prof mr"')
        self.assertNotContains(paginas['perfil'], 'perfil-prof mr')

    def test_el_css_no_trae_selectores_de_lo_que_no_existe_en_este_proyecto(self):
        css = re.sub(r'/\*.*?\*/', '', leer(CSS), flags=re.S)  # solo las reglas: la cabecera nombra lo que se omitio
        self.assertEqual(re.findall(r'\.pf(?:-[\w-]*)?(?![\w-])', css), [])  # rediseño del perfil: otra etapa
        self.assertNotIn('#portal-docente', css)  # ese id no existe: el modo noche del panel es body:not(.light-mode)
        self.assertIn('body:not(.light-mode) .mr .resenas .resena__avatar', css)
