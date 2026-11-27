"""Catalogo de clases del panel del alumno, por paginas (con 18.000 clases tardaba 12 s y pesaba 20 MB)."""

import re

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from alumnos.models import Asignatura, Clase
from alumnos.views import CLASES_POR_PAGINA
from tests.test_paquetes import RUT_ANA, Escenario


class CatalogoPaginadoTests(Escenario):
    """Escenario trae 2 clases habilitadas (una de cada profesor); se suman las que haga falta."""

    def setUp(self):
        self.entrar(RUT_ANA)

    def crear_clases(self, cantidad, profesor=None):
        asignatura = Asignatura.objects.first()
        Clase.objects.bulk_create(
            [Clase(asignatura=asignatura, modalidad='online', profesor=profesor or self.profe) for _ in range(cantidad)])

    def portal(self, **params):
        respuesta = self.client.get(reverse('alumno_pag1'), params)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def ids(self, respuesta):
        return [c.id_clase for c in respuesta.context['clases_disponibles']]

    def test_con_pocas_clases_se_ven_todas_y_no_hay_botones(self):
        r = self.portal()
        self.assertEqual(len(self.ids(r)), 2)
        self.assertEqual(r.context['total_clases_catalogo'], 2)
        self.assertNotContains(r, 'catalog-pagination"')

    def test_muestra_una_pagina_y_el_total_real(self):
        self.crear_clases(38)  # 40 en total
        r = self.portal()
        self.assertEqual(len(self.ids(r)), CLASES_POR_PAGINA)
        self.assertEqual(r.context['total_clases_catalogo'], 40)
        self.assertContains(r, 'Página 1 de 4')
        self.assertNotContains(r, 'rel="prev"')
        self.assertContains(r, 'rel="next"')

    def test_las_paginas_cubren_todo_sin_repetir_ni_saltarse_clases(self):
        self.crear_clases(38)
        vistas = [i for pagina in (1, 2, 3, 4) for i in self.ids(self.portal(pagina=pagina))]
        self.assertEqual(len(vistas), 40)
        self.assertEqual(len(set(vistas)), 40)
        self.assertEqual(set(vistas), set(Clase.objects.values_list('id_clase', flat=True)))

    def test_una_pagina_invalida_no_falla(self):
        """Una pagina que no existe da la ultima; una que no es un numero, la primera."""
        self.crear_clases(38)
        ultima = self.ids(self.portal(pagina=4))
        self.assertEqual(self.ids(self.portal(pagina=99)), ultima)
        self.assertEqual(self.ids(self.portal(pagina='abc')), self.ids(self.portal(pagina=1)))

    def test_al_cambiar_de_pagina_se_conservan_los_filtros(self):
        self.crear_clases(30, profesor=self.otro)  # 31 del profesor "otro"
        r = self.portal(profesor=self.otro.pk, pagina=2)
        enlaces = re.findall(r'href="(\?[^"]*pagina=\d+)"', r.content.decode())
        self.assertTrue(enlaces)
        for enlace in enlaces:
            self.assertIn(f'profesor={self.otro.pk}', enlace)
        self.assertEqual({c.profesor_id for c in r.context['clases_disponibles']}, {self.otro.pk})

    def test_el_portal_vuelve_solo_al_catalogo_si_se_cambio_de_pagina(self):
        self.crear_clases(30)
        marca = 'vuelve al catalogo tras filtrar o cambiar de pagina'  # el comentario que solo va con el salto
        self.assertNotContains(self.portal(), marca)
        self.assertContains(self.portal(pagina=2), marca)
        self.assertTrue(self.portal(pagina=2).context['en_catalogo'])
        self.assertFalse(self.portal(pagina=2).context['hay_filtros'])  # no es un filtro: no aparece "Limpiar filtros"

    def test_las_consultas_no_crecen_con_la_cantidad_de_clases(self):
        def consultas():
            with CaptureQueriesContext(connection) as c:
                self.portal()
            return len(c)

        antes = consultas()
        self.crear_clases(200)
        self.assertEqual(consultas(), antes)
