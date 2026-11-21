"""La ficha y el menu de la barra de soporte salen de `agente`: toda pantalla de soporte debe pasarselo a la plantilla.

«Escalar» lo olvidaba: le mostraba al lider el menu y la ficha de un agente («Soporte», sin cargo, sin
Conversaciones reportadas ni Requerimientos de autoridad). Datos ficticios.
"""

import re

from django.test import TestCase
from django.urls import reverse

from soporte.models import Ticket
from soporte.tickets import abrir_reporte
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_soporte_reportes import crear_alumno_adulto

OPCIONES_DEL_LIDER = ('Conversaciones reportadas', 'Requerimientos de autoridad')


class VerificacionesDelMenuTests(TestCase):
    """Apoderados y Documentos de profesores salian a todo soporte: un agente de Pagos veia dos pantallas que siempre
    estaban vacias. Ahora el agente las ve solo si atiende ese tema; el lider las ve siempre, pero como control
    (historial, vinculos con «Revocar», quien abrio cada documento), bajo «Supervisión». Datos ficticios."""

    def menu(self, agente):
        """(grupos del menu, enlaces de revision que salen) en el panel de ese agente."""
        entrar_soporte(self.client, agente)
        html = self.client.get(reverse('panel_soporte')).content.decode()
        grupos = re.findall(r'<span class="nav-label">([^<]+)</span>', html)
        return grupos, {nombre for nombre in ('apoderados', 'titulos') if f'id="nav-{nombre}"' in html}

    def test_un_agente_de_otro_tema_no_ve_ni_el_grupo_ni_los_enlaces(self):
        for rut, tema in (('10000001-6', Ticket.PAGOS), ('10000003-2', Ticket.CLASES), ('10000005-9', Ticket.TECNICO)):
            with self.subTest(tema=tema):
                self.assertEqual(self.menu(crear_agente(rut, tema)), (['Tickets'], set()))

    def test_un_agente_de_apoderados_ve_solo_apoderados(self):
        agente = crear_agente('10000002-4', Ticket.APODERADOS)
        self.assertEqual(self.menu(agente), (['Tickets', 'Verificaciones'], {'apoderados'}))

    def test_un_agente_de_titulos_o_de_especializaciones_ve_solo_documentos(self):
        for rut, tema in (('10000004-0', Ticket.TITULOS), ('10000006-7', Ticket.ESPECIALIZACIONES)):
            with self.subTest(tema=tema):
                self.assertEqual(self.menu(crear_agente(rut, tema)), (['Tickets', 'Verificaciones'], {'titulos'}))

    def test_un_agente_con_ambos_temas_ve_las_dos_pantallas(self):
        agente = crear_agente('10000008-3', Ticket.APODERADOS, Ticket.TITULOS)
        self.assertEqual(self.menu(agente), (['Tickets', 'Verificaciones'], {'apoderados', 'titulos'}))

    def test_el_lider_las_ve_siempre_pero_bajo_supervision(self):
        lider = crear_agente('10000010-5', Ticket.PAGOS, lider=True)  # no atiende ni apoderados ni titulos
        self.assertEqual(self.menu(lider), (['Tickets', 'Supervisión', 'Privacidad y legal'], {'apoderados', 'titulos'}))

    def test_quitarle_el_menu_no_quita_el_acceso_a_las_vistas_que_ya_filtran_por_ticket(self):
        """Es solo el menu: la pantalla sigue abierta (vacia) si alguien entra por un enlace guardado."""
        entrar_soporte(self.client, crear_agente('10000012-1', Ticket.PAGOS))
        for ruta in ('apoderados_revision', 'titulos_adm'):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(reverse(ruta)).status_code, 200)


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
