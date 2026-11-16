"""Portal de soporte (lider), Tickets: los paneles del lider con la estructura de la copia y la logica real. Datos ficticios."""
from django.urls import reverse

from apoderados.models import Apoderado
from soporte.models import Ticket
from soporte.tickets import abrir_ticket
from tests.test_apoderados import RUT, crear_apoderado, entrar_soporte
from tests.test_escalamientos import Escenario


class TicketsDelLiderTests(Escenario):

    def pagina(self, quien):
        entrar_soporte(self.client, quien)
        return self.client.get(reverse('panel_soporte')).content.decode()

    def test_el_lider_ve_sus_tickets_los_del_equipo_el_equipo_y_las_asignaciones(self):
        html = self.pagina(self.lider)
        self.assertIn('sop-tabla-tickets sop-tabla-tickets--mios', html)
        self.assertIn('sop-tabla-tickets sop-tabla-tickets--equipo', html)
        self.assertIn('Todos los tickets abiertos <span class="sop-cuenta">1</span>', html)
        self.assertIn('<ul class="sop-equipo">', html)
        self.assertIn('<details class="panel sop-registro">', html)
        self.assertIn('aria-label="Estado de los tickets del equipo"', html)
        self.assertIn('Abiertos en el equipo', html)
        self.assertIn('<div class="sop-filtro-agentes" role="group" aria-label="Filtrar por agente" hidden></div>', html)

    def test_la_fila_del_equipo_trae_enlace_escalar_asignado_y_reasignar(self):
        html = self.pagina(self.lider)
        self.assertIn(f'<a class="sop-ticket" href="{reverse("soporte_reporte", args=[self.ticket.pk])}">', html)
        self.assertIn(f'<a class="sop-ticket-escalar" href="{reverse("soporte_escalar", args=[self.ticket.pk])}"', html)
        self.assertIn(f'<span class="sop-persona-nombre">{self.agente.nombre}</span>', html)
        self.assertIn(f'<form method="post" action="{reverse("soporte_reasignar", args=[self.ticket.pk])}" class="sop-reasignar">', html)
        self.assertIn(f'aria-label="Agente para el ticket #{self.ticket.pk}"', html)

    def test_el_equipo_muestra_cargo_carga_y_categorias_de_cada_agente(self):
        html = self.pagina(self.lider)
        self.assertEqual(html.count('<li class="sop-agente">'), 2)
        self.assertIn(f'<strong>{self.agente.nombre}</strong>', html)
        self.assertIn('<strong class="sop-carga-n">1</strong>', html)
        self.assertIn(f'aria-label="Categorías que atiende {self.agente.nombre}"', html)
        self.assertIn('<span class="badge">Pagos y retiros</span>', html)

    def test_un_ticket_sin_pagina_de_detalle_muestra_su_asunto_sin_enlace(self):
        abrir_ticket(Ticket.APODERADOS, apoderado=crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE))
        otro = Ticket.objects.exclude(pk=self.ticket.pk).get()
        html = self.pagina(self.lider)
        self.assertIn('Todos los tickets abiertos <span class="sop-cuenta">2</span>', html)
        self.assertNotIn(f'href="{reverse("soporte_reporte", args=[otro.pk])}"', html)  # exacto: escalar y reasignar comparten el prefijo
        self.assertIn(f'href="{reverse("soporte_escalar", args=[otro.pk])}"', html)
        self.assertIn(f'<span class="sop-ticket-num">#{otro.pk}</span>', html)

    def test_las_asignaciones_van_en_un_registro_plegado(self):
        html = self.pagina(self.lider)
        self.assertIn('<span class="sop-registro-nota">últimas 50</span>', html)
        self.assertIn(f'#{self.ticket.pk} <small>Pagos y retiros</small>', html)
        self.assertIn('Automática', html)

    def test_el_agente_no_ve_nada_del_lider(self):
        html = self.pagina(self.agente)
        for rastro in ('sop-tabla-tickets--equipo', 'sop-equipo', 'sop-registro', 'sop-reasignar', 'Todos los tickets abiertos',
                       'Abiertos en el equipo', 'sop-tabla-tickets--mios', 'sop-filtro-agentes'):
            with self.subTest(rastro=rastro):
                self.assertNotIn(rastro, html)
        self.assertIn('aria-label="Estado de tus tickets"', html)
        self.assertIn('Tickets abiertos <span class="sop-cuenta">1</span>', html)

    def test_sin_ids_repetidos_en_las_dos_tablas(self):
        html = self.pagina(self.lider)
        self.assertEqual(html.count('id="sop-filtro"'), 0)
        self.assertEqual(html.count('id="sop-sin-resultados"'), 0)
        self.assertEqual(html.count('class="sop-sin-resultados"'), 2)
