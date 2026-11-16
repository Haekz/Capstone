"""Portal de soporte, detalle del ticket: la estructura de la copia (hilo + ficha lateral) con la logica real. Datos ficticios."""
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from soporte.models import Ticket
from tests.test_apoderados import entrar_soporte
from tests.test_escalamientos import DESCRIPCION, Escenario


class DetalleComoLaCopiaTests(Escenario):

    def pagina(self):
        entrar_soporte(self.client, self.agente)
        return self.client.get(reverse('soporte_reporte', args=[self.ticket.pk])).content.decode()

    def test_cabecera_mensaje_y_ficha(self):
        html = self.pagina()
        self.assertIn('<a class="sop-volver" href="' + reverse('panel_soporte') + '">', html)
        self.assertIn('<h2 class="sop-detalle-titulo">Cobro doble</h2>', html)
        self.assertIn('<li class="sop-chip sop-chip--estado">Abierto</li>', html)
        self.assertIn('<span>Lo que nos contó</span>', html)
        self.assertIn(DESCRIPCION, html)
        self.assertIn('<h3 class="sop-ficha-titulo">Detalles</h3>', html)
        self.assertIn('<dt>Abierto por</dt>', html)
        self.assertIn('<dt>Asignado a</dt><dd>' + self.agente.nombre, html)

    def test_el_avatar_lleva_la_inicial_de_quien_escribio(self):
        inicial = self.ticket.autor.first_name[:1].upper()
        self.assertIn(f'<span class="sop-avatar" aria-hidden="true">{inicial}</span>', self.pagina())

    def test_el_vence_trae_su_datetime_para_el_plazo_en_palabras(self):
        iso = timezone.localtime(self.ticket.vence).strftime('%Y-%m-%dT%H:%M')
        self.assertIn(f'<time class="sop-vence" datetime="{iso}">', self.pagina())

    def test_sin_respuestas_y_con_respuesta_de_soporte(self):
        self.assertIn('<li class="sop-sin-respuestas">Todavía no hay respuestas.</li>', self.pagina())
        self.client.post(reverse('soporte_reporte', args=[self.ticket.pk]), {'texto': 'Ya lo estamos revisando.'})
        html = self.pagina()
        self.assertIn('<ol class="sop-respuestas">', html)
        self.assertIn('Ya lo estamos revisando.', html)
        self.assertIn(f'{self.agente.user.first_name} (soporte)', html)
        self.assertNotIn('sop-sin-respuestas', html)

    def test_la_ficha_de_escalar_solo_con_el_ticket_abierto(self):
        self.assertIn('<div class="panel sop-ficha sop-ficha--escalar">', self.pagina())
        self.assertIn(f'<a class="sop-btn" href="{reverse("soporte_escalar", args=[self.ticket.pk])}">', self.pagina())
        Ticket.objects.filter(pk=self.ticket.pk).update(estado=Ticket.CERRADO)
        self.assertNotIn('sop-ficha--escalar', self.pagina())


class ConversacionDelUsuarioSigueIgualTests(SimpleTestCase):
    """_conversacion.html lo comparte mi_ticket: la rama nueva es solo para soporte."""

    def test_sin_soporte_ve_no_hay_clases_de_soporte(self):
        html = render_to_string('soporte/_conversacion.html', {'mensajes': [], 'soporte_ve': False})
        self.assertIn('<li>Todavía no hay respuestas.</li>', html)
        self.assertNotIn('sop-', html)
