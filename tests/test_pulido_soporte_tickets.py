"""Portal de soporte, Mis tickets: la estructura que lee mejoras_soporte.js (banner, tabla, fechas, botones). Datos ficticios."""
import re

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apoderados.models import Apoderado
from soporte.models import Ticket
from soporte.tickets import abrir_ticket
from tests.test_apoderados import RUT, crear_agente, crear_apoderado, entrar_soporte


class MisTicketsTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('88888888-8', Ticket.APODERADOS, Ticket.TITULOS)
        entrar_soporte(self.client, self.agente)

    def pagina(self):
        return self.client.get(reverse('panel_soporte')).content.decode()

    def abrir_uno(self):
        abrir_ticket(Ticket.APODERADOS, apoderado=crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE))
        return Ticket.objects.get()

    def test_el_banner_trae_los_elementos_que_rellena_el_js(self):
        html = self.pagina()
        for id_ in ('sop-hoy', 'sop-saludo', 'sop-resumen', 'sop-siguiente', 'sop-cifras', 'sop-n-abiertos', 'sop-n-pronto',
                    'sop-n-vencidos', 'sop-c-pronto', 'sop-c-vencidos', 'sop-filtro', 'sop-sin-resultados'):
            with self.subTest(id=id_):
                self.assertIn(f'id="{id_}"', html)
        # Lo que el JS muestra al calcular va oculto de partida: sin JS no queda un banner a medias
        self.assertRegex(html, r'id="sop-siguiente"[^>]*\bhidden\b')
        self.assertRegex(html, r'id="sop-cifras"[^>]*\bhidden\b')

    def test_la_fila_lleva_numero_asunto_fechas_y_botones(self):
        ticket = self.abrir_uno()
        html = self.pagina()
        revisar = reverse('apoderados_revision')  # un ticket de apoderados se revisa en la pantalla de verificacion
        self.assertIn(f'<a class="sop-ticket" href="{revisar}">', html)
        self.assertIn(f'<span class="sop-ticket-num">#{ticket.pk}</span>', html)
        self.assertIn(f'<span class="sop-ticket-asunto">{ticket.asunto}</span>', html)
        self.assertIn(f'<a class="sop-btn sop-btn--primario" href="{revisar}">Revisar</a>', html)
        self.assertIn(f'href="{reverse("soporte_escalar", args=[ticket.pk])}" aria-label="Escalar el ticket #{ticket.pk}">Escalar</a>', html)

    def test_el_datetime_de_vence_es_la_hora_que_se_ve(self):
        """El JS arma 'Vence mañana, 23:59' desde este atributo: si difiriera de lo escrito, el plazo en palabras mentiria."""
        ticket = self.abrir_uno()
        iso = timezone.localtime(ticket.vence).strftime('%Y-%m-%dT%H:%M')
        visible = timezone.localtime(ticket.vence).strftime('%d-%m-%Y %H:%M')
        self.assertIn(f'<time class="sop-vence" datetime="{iso}">{visible}</time>', self.pagina())

    def test_la_cuenta_y_el_estado_vacio(self):
        html = self.pagina()
        self.assertIn('Tickets abiertos <span class="sop-cuenta">0</span>', html)
        self.assertIn('<td colspan="5">No tienes tickets abiertos.</td>', html)
        self.abrir_uno()
        self.assertIn('Tickets abiertos <span class="sop-cuenta">1</span>', self.pagina())

    def test_el_atrasado_se_conserva_aunque_el_js_tambien_lo_diga(self):
        """La copia no lo muestra (su demo no tiene atrasados): se deja, la informacion no se pierde."""
        self.abrir_uno()
        Ticket.objects.update(vence=timezone.now() - timezone.timedelta(days=1))
        self.assertIn('<span class="badge">Atrasado</span>', self.pagina())
