"""Contactanos lo atiende soporte (H14, D5: el admin no atiende casos, solo ve metricas).

Cada mensaje del formulario publico es un ticket de la categoria Contacto. El visitante no tiene
cuenta: el agente le responde por correo, con el texto, y el ticket se cierra. Datos ficticios.
"""

from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from admin_portal.models import MensajeContacto
from soporte.correo import avisar_atrasados
from soporte.models import Ticket
from soporte.plazos import vencimiento
from soporte.tickets import abrir_contacto
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_campana import avisos_de

MENSAJE_VISITANTE = 'Visita http://sitio-raro.example para tu premio'


def contactar(nombre='Ana Ficticia', correo='ana@example.com', mensaje=MENSAJE_VISITANTE):
    return abrir_contacto(MensajeContacto(nombre=nombre, correo=correo, mensaje=mensaje))


class LlegaASoporteTests(TestCase):

    def setUp(self):
        cache.clear()  # el tope por IP del formulario vive en la cache compartida

    def test_el_formulario_abre_un_ticket_asignado_con_plazo_de_5_dias_habiles(self):
        agente = crear_agente('10000001-9', Ticket.CONTACTO)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('contactos'), {'nombre': 'Ana Ficticia', 'correo': 'ana@example.com',
                                                   'mensaje': '¿Tienen clases de física?'})
        ticket = Ticket.objects.get()
        self.assertEqual((ticket.categoria, ticket.asignado, ticket.asunto),
                         (Ticket.CONTACTO, agente, 'Mensaje de Ana Ficticia'))
        self.assertEqual(ticket.vence, vencimiento(ticket.creado, 5))
        self.assertEqual(mail.outbox[0].to, [agente.user.email])  # aviso de asignacion, como cualquier ticket

    def test_contacto_no_es_una_categoria_que_abra_un_usuario(self):
        self.assertNotIn(Ticket.CONTACTO, Ticket.DE_USUARIOS)

    def test_el_admin_ya_no_tiene_bandeja_de_contacto(self):
        with self.assertRaises(NoReverseMatch):
            reverse('contactos_adm')
        self.assertEqual(self.client.get('/admin_portal/contactos_adm').status_code, 404)


class PantallaDelAgenteTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.CONTACTO)
        self.ticket = contactar(nombre='<script>alert(1)</script>')
        self.url = reverse('soporte_reporte', args=[self.ticket.pk])

    def test_lo_ve_desde_su_panel_con_el_mensaje_y_escapado(self):
        entrar_soporte(self.client, self.agente)
        self.assertContains(self.client.get(reverse('panel_soporte')), self.url)
        pagina = self.client.get(self.url)
        self.assertContains(pagina, MENSAJE_VISITANTE)
        self.assertContains(pagina, 'ana@example.com')
        self.assertContains(pagina, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(pagina, '<script>alert(1)</script>')

    def test_otro_agente_no_lo_ve_y_un_anonimo_tampoco(self):
        entrar_soporte(self.client, crear_agente('10000002-7', Ticket.CONTACTO))
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.logout()
        self.assertNotContains(self.client.get(self.url), MENSAJE_VISITANTE, status_code=302)

    def test_la_campana_lo_abre_en_su_conversacion(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(vence=timezone.now() - timedelta(hours=1))
        [aviso] = avisos_de(soporte_id=self.agente.id_agente)
        self.assertEqual(aviso.url, self.url)
        self.assertIn('Mensaje de', aviso.detalle)


class RespuestaAlVisitanteTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.CONTACTO)
        self.ticket = contactar()
        self.url = reverse('soporte_reporte', args=[self.ticket.pk])
        entrar_soporte(self.client, self.agente)
        mail.outbox.clear()  # el aviso de asignacion

    def enviar(self, **datos):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, datos)

    def test_le_llega_la_respuesta_por_correo_y_el_ticket_se_cierra(self):
        respuesta = self.enviar(texto="Sí, tenemos física. Escríbenos por 'Planes'.")
        self.assertRedirects(respuesta, reverse('panel_soporte'), fetch_redirect_response=False)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.CERRADO)
        self.assertIsNotNone(self.ticket.respondido)  # cumple el plazo
        correo, = mail.outbox
        self.assertEqual(correo.to, ['ana@example.com'])
        self.assertIn("Sí, tenemos física. Escríbenos por 'Planes'.", correo.body)  # texto plano, sin &#x27;
        self.assertIn('Hola Ana Ficticia', correo.body)

    def test_el_correo_no_repite_lo_que_escribio_el_visitante(self):
        """El correo no esta verificado: citarlo dejaria mandar cualquier texto a un tercero."""
        self.enviar(texto='Gracias por escribir.')
        self.assertNotIn('sitio-raro', mail.outbox[0].body)

    def test_cerrar_sin_responder_no_manda_correo(self):
        self.enviar(sin_respuesta='on')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.CERRADO)
        self.assertIsNotNone(self.ticket.respondido)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(self.ticket.mensajes.exists())

    def test_hay_que_elegir_responder_o_cerrar_sin_responder(self):
        for datos in ({'texto': ''}, {'texto': 'Hola', 'sin_respuesta': 'on'}):  # nada, o las dos
            with self.subTest(datos=datos):
                pagina = self.enviar(**datos)
                self.assertContains(pagina, 'solo una de las dos')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.ABIERTO)
        self.assertEqual(mail.outbox, [])

    def test_responde_solo_el_agente_asignado(self):
        entrar_soporte(self.client, crear_agente('10000003-5', lider=True))
        self.enviar(texto='Respuesta del líder')
        self.assertFalse(self.ticket.mensajes.exists())
        self.assertEqual(mail.outbox, [])


class AtrasoTests(TestCase):

    def test_atrasado_avisa_al_equipo_pero_no_se_disculpa_con_el_visitante(self):
        """La disculpa manda a revisar la cuenta, y el visitante no tiene."""
        agente = crear_agente('10000001-9', Ticket.CONTACTO)
        ticket = contactar()
        Ticket.objects.filter(pk=ticket.pk).update(vence=timezone.now() - timedelta(days=10))
        mail.outbox.clear()
        with mock.patch('soporte.correo._toca_avisar', return_value=True):  # sin depender del dia
            self.assertEqual(avisar_atrasados(timezone.localdate()), 1)
        self.assertEqual([correo.to for correo in mail.outbox], [[agente.user.email]])
