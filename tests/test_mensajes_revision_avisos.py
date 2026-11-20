"""Campanita y recordatorio al lider por conversaciones reportadas pendientes (paso C1f-2b). Datos ficticios."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from mensajes import avisos_revision, revision, servicio
from mensajes.models import DecisionRetencion
from soporte.models import Ticket
from soporte.plazos import es_habil
from tests.test_apoderados import crear_agente
from tests.test_campana import avisos_de
from tests.test_paquetes import Escenario, dar_paquete

TEXTOS = {'alcance': 'Los mensajes del 28-oct.', 'fundamento': 'Posible reclamo.', 'termino': 'Al resolverse.'}


def dia_habil(desde, n):
    """El n-esimo dia habil despues de `desde`."""
    dia = desde
    while n:
        dia += timedelta(days=1)
        n -= es_habil(dia)
    return dia


class AvisosRevisionTests(Escenario):

    def setUp(self):
        self.hoy = timezone.localdate()
        self.lider = crear_agente('10000002-7', Ticket.CONDUCTA, lider=True)
        self.agente = crear_agente('10000001-9', Ticket.CONDUCTA)
        dar_paquete(self.ana, self.profe)
        self.conversacion = servicio.abrir_conversacion(self.ana, self.profe)
        self.reporte = servicio.reportar(self.profe.user, self.conversacion, 'Me incomoda.')
        self.cerrar_ticket(self.reporte)
        mail.outbox.clear()

    def cerrar_ticket(self, reporte, cerrado=None):
        Ticket.objects.filter(pk=reporte.ticket_id).update(estado=Ticket.CERRADO, cerrado=cerrado or timezone.now())

    def por_revisar(self, agente):
        return [a for a in avisos_de(soporte_id=agente.id_agente) if 'por revisar' in a.titulo]

    # --- campanita ---

    def test_el_lider_ve_el_aviso_con_el_enlace_a_la_pantalla(self):
        [aviso] = self.por_revisar(self.lider)
        self.assertEqual(aviso.titulo, '1 conversación reportada por revisar')
        self.assertEqual(aviso.url, reverse('mensajes_revision'))
        self.assertFalse(aviso.urgente)

    def test_un_agente_no_lo_ve(self):
        self.assertEqual(self.por_revisar(self.agente), [])

    def test_con_el_ticket_abierto_no_sale(self):
        Ticket.objects.update(estado=Ticket.ABIERTO, cerrado=None)
        self.assertEqual(self.por_revisar(self.lider), [])

    def test_ya_decidida_no_sale(self):
        revision.liberar(self.lider, self.conversacion)
        self.assertEqual(self.por_revisar(self.lider), [])

    def test_con_varias_va_en_plural(self):
        dar_paquete(self.ana, self.otro)
        segunda = servicio.abrir_conversacion(self.ana, self.otro)
        self.cerrar_ticket(servicio.reportar(self.otro.user, segunda, 'Tambien me escribe raro.'))
        [aviso] = self.por_revisar(self.lider)
        self.assertEqual(aviso.titulo, '2 conversaciones reportadas por revisar')

    def test_se_vuelve_urgente_tras_3_dias_habiles_esperando(self):
        self.cerrar_ticket(self.reporte, cerrado=timezone.now() - timedelta(days=10))
        [aviso] = self.por_revisar(self.lider)
        self.assertTrue(aviso.urgente)

    # --- correo ---

    def test_el_dia_que_se_cierra_no_manda_correo_y_el_primer_dia_habil_si(self):
        self.assertEqual(avisos_revision.avisar_pendientes(self.hoy), 0)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(avisos_revision.avisar_pendientes(dia_habil(self.hoy, 1)), 1)
        [correo] = mail.outbox
        self.assertEqual(correo.to, [self.lider.user.email])  # solo al lider, no al agente
        self.assertIn('Conversaciones reportadas por revisar', correo.subject)
        self.assertIn('1 conversación reportada', correo.body)
        self.assertIn('cada 3 días hábiles', correo.body)

    def test_el_correo_no_lleva_nombres_ni_el_contenido(self):
        avisos_revision.avisar_pendientes(dia_habil(self.hoy, 1))
        cuerpo = mail.outbox[0].body
        for privado in (self.ana.user.first_name, self.profe.user.first_name, self.ana.user.email, 'Me incomoda'):
            self.assertNotIn(privado, cuerpo)

    def test_despues_se_repite_cada_3_dias_habiles(self):
        enviados = [bool(avisos_revision.avisar_pendientes(dia_habil(self.hoy, n))) for n in range(1, 8)]
        self.assertEqual(enviados, [True, False, False, True, False, False, True])  # dias habiles 1, 4 y 7

    def test_ya_decidida_no_se_recuerda(self):
        revision.liberar(self.lider, self.conversacion)
        self.assertEqual(avisos_revision.avisar_pendientes(dia_habil(self.hoy, 1)), 0)
        self.assertEqual(mail.outbox, [])

    def test_una_conservada_vuelve_a_recordarse_al_vencer_su_revision(self):
        revision.conservar(self.lider, self.conversacion, DecisionRetencion.AUTORIDAD, **TEXTOS)
        revisar = self.hoy + relativedelta(months=6)
        self.assertEqual(avisos_revision.avisar_pendientes(revisar - timedelta(days=1)), 0)
        self.assertEqual(avisos_revision.avisar_pendientes(dia_habil(revisar, 1)), 1)

    # --- comando ---

    def test_el_comando_no_envia_en_dias_no_habiles(self):
        salida = StringIO()
        with patch('mensajes.management.commands.avisar_revisiones_pendientes.es_habil', return_value=False):
            call_command('avisar_revisiones_pendientes', stdout=salida)
        self.assertIn('no es día hábil', salida.getvalue())
        self.assertEqual(mail.outbox, [])

    def test_el_comando_informa_solo_la_cantidad(self):
        salida = StringIO()
        with patch('mensajes.management.commands.avisar_revisiones_pendientes.es_habil', return_value=True), \
                patch('mensajes.avisos_revision.dias_habiles_entre', return_value=1):
            call_command('avisar_revisiones_pendientes', stdout=salida)
        self.assertEqual(salida.getvalue().strip(), 'Conversaciones por revisar avisadas: 1')
        self.assertEqual(len(mail.outbox), 1)
