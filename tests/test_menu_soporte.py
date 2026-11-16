"""La ficha y el menu de la barra de soporte salen de `agente`: toda pantalla de soporte debe pasarselo a la plantilla.

«Escalar» lo olvidaba: le mostraba al lider el menu y la ficha de un agente («Soporte», sin cargo, sin
Conversaciones reportadas ni Requerimientos de autoridad). Datos ficticios.
"""

from django.test import TestCase
from django.urls import reverse

from soporte.models import Ticket
from soporte.tickets import abrir_reporte
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_soporte_reportes import crear_alumno_adulto

OPCIONES_DEL_LIDER = ('Conversaciones reportadas', 'Requerimientos de autoridad')


class MenuDeSoporteTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.PAGOS)
        self.lider = crear_agente('10000003-5', Ticket.APODERADOS, lider=True)  # no atiende Pagos
        self.ticket = abrir_reporte(crear_alumno_adulto().user, Ticket.PAGOS, 'Cobro doble', 'Detalle privado.')

    def pantallas(self, agente):
        """Las pantallas de soporte con barra lateral que puede abrir ese agente."""
        pantallas = [reverse('panel_soporte'), reverse('soporte_reporte', args=[self.ticket.pk]),
                     reverse('soporte_escalar', args=[self.ticket.pk]), reverse('apoderados_revision'),
                     reverse('titulos_adm')]
        if agente.es_lider:  # estas dos son solo del lider
            pantallas += [reverse('mensajes_revision'), reverse('requerimientos')]
        return pantallas

    def test_el_lider_ve_su_ficha_y_su_menu_completo_en_todas_las_pantallas(self):
        entrar_soporte(self.client, self.lider)
        for url in self.pantallas(self.lider):
            with self.subTest(url=url):
                pagina = self.client.get(url)
                self.assertContains(pagina, self.lider.nombre)  # su ficha, no el «Soporte» de relleno
                self.assertContains(pagina, 'Líder de soporte')
                for opcion in OPCIONES_DEL_LIDER:
                    self.assertContains(pagina, opcion)

    def test_el_agente_ve_su_ficha_y_no_las_opciones_del_lider_en_todas_las_pantallas(self):
        entrar_soporte(self.client, self.agente)
        for url in self.pantallas(self.agente):
            with self.subTest(url=url):
                pagina = self.client.get(url)
                self.assertContains(pagina, self.agente.nombre)
                self.assertContains(pagina, 'Agente de soporte')
                for opcion in OPCIONES_DEL_LIDER:
                    self.assertNotContains(pagina, opcion)
