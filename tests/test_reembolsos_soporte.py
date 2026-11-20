"""Soporte y el reembolso automatico por Transbank (alumnos/views_soporte_videos.py + alumnos/reembolsos.py).

Al registrar una devolucion se intenta devolver por Transbank; si no se puede, queda a mano como siempre y soporte ve por
que y puede reintentar. Transbank se simula con un mock: nada sale a la red.
"""

from unittest.mock import MagicMock, patch

from django.urls import reverse

from alumnos.models.videos import DevolucionVideos
from soporte.models import Ticket
from soporte.tickets import abrir_reporte
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_entrega_videos_extra import Base
from tests.test_soporte_videos import RUT_AGENTE, RUT_OTRO_AGENTE

ANULADA = {'type': 'NULLIFIED', 'authorization_code': '1234', 'response_code': 0}


class SoporteReembolsoTests(Base):

    def setUp(self):
        super().setUp()
        self.agente = crear_agente(RUT_AGENTE, Ticket.VIDEOS)
        self.ticket = abrir_reporte(self.ana.user, Ticket.VIDEOS, 'Faltan videos', 'No me los compartio.')
        self.paquete_ana = self.paquete(videos=4)  # agregado de $20.000
        self.paquete_ana.token_ws = 'TOKEN-PAQUETE'
        self.paquete_ana.save(update_fields=['token_ws'])
        self.tx = MagicMock()
        self.tx.refund.return_value = ANULADA
        patcher = patch('alumnos.reembolsos.webpay._tx', return_value=self.tx)
        patcher.start()
        self.addCleanup(patcher.stop)
        entrar_soporte(self.client, self.agente)

    def pagina(self):
        return self.client.get(reverse('soporte_reporte', args=[self.ticket.pk]))

    def registrar(self, cantidad='2'):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('soporte_devolver_videos', args=[self.ticket.pk]),
                                    {'paquete': self.paquete_ana.pk, 'cantidad': cantidad})

    def reintentar(self, devolucion):
        return self.client.post(reverse('soporte_reintentar_reembolso', args=[self.ticket.pk, devolucion.pk]))

    def textos(self):
        return [mensaje.texto for mensaje in self.ticket.mensajes.order_by('id')]

    def test_si_transbank_devuelve_queda_devuelta_y_se_le_cuenta_al_alumno(self):
        self.registrar('2')
        self.tx.refund.assert_called_once_with('TOKEN-PAQUETE', 10000)
        self.assertIsNotNone(DevolucionVideos.objects.get().devuelta)
        aprobado, devuelto = self.textos()
        self.assertIn('Aprobamos devolverte $10.000', aprobado)
        self.assertIn('Ya te devolvimos $10.000', devuelto)
        self.assertIn('mismo medio de pago', devuelto)

    def test_el_aviso_al_alumno_de_que_soporte_transfiere_no_miente_si_ya_se_devolvio(self):
        self.registrar('2')
        aprobado, _ = self.textos()
        self.assertNotIn('Soporte te hará llegar el dinero', aprobado)

    def test_si_transbank_rechaza_sigue_a_mano_y_soporte_ve_por_que(self):
        self.tx.refund.side_effect = Exception('Periodo de anulacion excedido')
        self.registrar('2')
        devolucion = DevolucionVideos.objects.get()
        self.assertIsNone(devolucion.devuelta)
        aprobado, pendiente = self.textos()
        self.assertIn('Aprobamos devolverte $10.000', aprobado)
        self.assertIn('Soporte te hará llegar el dinero', pendiente)  # lo de siempre
        pagina = self.pagina()
        self.assertContains(pagina, 'Periodo de anulacion excedido')
        self.assertContains(pagina, reverse('soporte_reintentar_reembolso', args=[self.ticket.pk, devolucion.pk]))
        self.assertContains(pagina, reverse('soporte_pedir_aprobacion', args=[self.ticket.pk, devolucion.pk]))
        # a mano solo despues de que el admin apruebe: ver tests/test_aprobacion_devolucion.py
        self.assertNotContains(pagina, reverse('soporte_devolucion_hecha', args=[self.ticket.pk, devolucion.pk]))

    def test_reintentar_por_transbank_la_deja_devuelta_y_avisa_al_alumno(self):
        self.tx.refund.side_effect = Exception('Error del autorizador')
        self.registrar('2')
        devolucion = DevolucionVideos.objects.get()
        self.tx.refund.side_effect = None
        respuesta = self.reintentar(devolucion)
        self.assertRedirects(respuesta, reverse('soporte_reporte', args=[self.ticket.pk]), fetch_redirect_response=False)
        devolucion.refresh_from_db()
        self.assertIsNotNone(devolucion.devuelta)
        self.assertIn('Ya te devolvimos $10.000', self.textos()[-1])

    def test_si_el_reintento_tambien_falla_no_se_le_escribe_al_alumno(self):
        self.tx.refund.side_effect = Exception('Error del autorizador')
        self.registrar('2')
        self.reintentar(DevolucionVideos.objects.get())
        self.assertEqual(len(self.textos()), 2)  # solo "aprobamos" y "soporte te hara llegar": el reintento no agrega

    def test_no_se_reintenta_lo_ya_devuelto(self):
        self.registrar('2')  # sale por Transbank
        self.assertEqual(self.reintentar(DevolucionVideos.objects.get()).status_code, 404)
        self.assertEqual(self.tx.refund.call_count, 1)

    def test_solo_el_agente_asignado_reintenta(self):
        self.tx.refund.side_effect = Exception('Error del autorizador')
        self.registrar('2')
        entrar_soporte(self.client, crear_agente(RUT_OTRO_AGENTE, Ticket.VIDEOS))
        self.tx.refund.side_effect = None
        self.assertEqual(self.reintentar(DevolucionVideos.objects.get()).status_code, 404)
        self.assertIsNone(DevolucionVideos.objects.get().devuelta)

    def test_a_mano_el_panel_dice_cuanto_falta_si_transbank_devolvio_solo_una_parte(self):
        devolucion = DevolucionVideos.objects.create(paquete=self.paquete_ana, cantidad=2, monto=10000,
                                                     ticket=self.ticket, registrada_por=self.agente.user)
        devolucion.reembolsos.create(token_ws='TOKEN-PAQUETE', monto=4000, confirmado=devolucion.creada)
        self.assertContains(self.pagina(), 'Faltan $6.000 por devolver')
