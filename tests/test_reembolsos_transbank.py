"""Reembolso automatico por Transbank de una devolucion de videos (alumnos/reembolsos.py).

Transbank se simula con un mock de ``webpay._tx().refund``: aqui no sale nada a la red. Reglas de Transbank:
transbankdevelopers.cl/documentacion/webpay-plus (reversa o anulacion, 90 dias, parcial segun tarjeta).
"""

from unittest.mock import MagicMock, patch

from alumnos import devoluciones_videos, reembolsos
from alumnos.models.videos import DevolucionVideos, ReembolsoTransbank
from soporte.models import Ticket
from soporte.tickets import abrir_reporte
from tests.test_apoderados import crear_agente
from tests.test_entrega_videos_extra import Base
from tests.test_soporte_videos import RUT_AGENTE

ANULADA = {'type': 'NULLIFIED', 'authorization_code': '1234', 'response_code': 0, 'balance': 0,
           'nullified_amount': 0, 'authorization_date': '2026-11-13T10:00:00.000Z'}
REVERSADA = {'type': 'REVERSED'}  # una reversa solo trae el tipo


class ReembolsoTests(Base):

    def setUp(self):
        super().setUp()
        self.agente = crear_agente(RUT_AGENTE, Ticket.VIDEOS)
        self.ticket = abrir_reporte(self.ana.user, Ticket.VIDEOS, 'Faltan videos', 'No me los compartio.')
        self.paquete_ana = self.paquete(videos=4)  # agregado de $20.000, $5.000 cada uno
        self.paquete_ana.token_ws = 'TOKEN-PAQUETE'
        self.paquete_ana.save(update_fields=['token_ws'])
        self.tx = MagicMock()
        self.tx.refund.return_value = ANULADA
        patcher = patch('alumnos.reembolsos.webpay._tx', return_value=self.tx)
        patcher.start()
        self.addCleanup(patcher.stop)

    def devolucion(self, cantidad=2, paquete=None):
        return devoluciones_videos.registrar(self.ticket, (paquete or self.paquete_ana).pk, cantidad, self.agente.user)

    def test_devuelve_por_transbank_el_monto_del_servidor_y_queda_devuelta(self):
        devolucion = self.devolucion(2)
        self.assertTrue(reembolsos.intentar(devolucion))
        self.tx.refund.assert_called_once_with('TOKEN-PAQUETE', 10000)
        devolucion.refresh_from_db()
        self.assertIsNotNone(devolucion.devuelta)
        self.assertEqual(devolucion.error_reembolso, '')
        [reembolso] = devolucion.reembolsos.all()
        self.assertEqual((reembolso.token_ws, reembolso.monto, reembolso.tipo, reembolso.codigo_autorizacion),
                         ('TOKEN-PAQUETE', 10000, 'NULLIFIED', '1234'))
        self.assertIsNotNone(reembolso.confirmado)

    def test_una_reversa_no_trae_codigo_y_tambien_cuenta(self):
        self.tx.refund.return_value = REVERSADA
        devolucion = self.devolucion(1)
        self.assertTrue(reembolsos.intentar(devolucion))
        [reembolso] = devolucion.reembolsos.all()
        self.assertEqual((reembolso.tipo, reembolso.codigo_autorizacion), ('REVERSED', ''))

    def test_si_transbank_rechaza_queda_por_devolver_a_mano_con_el_motivo(self):
        self.tx.refund.side_effect = Exception('Periodo de anulacion excedido')
        devolucion = self.devolucion(2)
        self.assertFalse(reembolsos.intentar(devolucion))
        devolucion.refresh_from_db()
        self.assertIsNone(devolucion.devuelta)
        self.assertIn('Periodo de anulacion excedido', devolucion.error_reembolso)
        self.assertFalse(devolucion.reembolsos.exists())  # no queda un reembolso fantasma que bloquee el reintento
        self.assertEqual(devolucion.por_devolver, 10000)

    def test_una_anulacion_con_response_code_distinto_de_cero_es_un_rechazo(self):
        self.tx.refund.return_value = {**ANULADA, 'response_code': 311}
        devolucion = self.devolucion(1)
        self.assertFalse(reembolsos.intentar(devolucion))
        self.assertIsNone(DevolucionVideos.objects.get(pk=devolucion.pk).devuelta)

    def test_despues_de_un_rechazo_se_puede_reintentar(self):
        self.tx.refund.side_effect = Exception('Error del autorizador')
        devolucion = self.devolucion(2)
        reembolsos.intentar(devolucion)
        self.tx.refund.side_effect = None
        self.assertTrue(reembolsos.intentar(devolucion))
        devolucion.refresh_from_db()
        self.assertEqual(devolucion.error_reembolso, '')

    def test_nunca_devuelve_dos_veces_lo_mismo(self):
        devolucion = self.devolucion(2)
        reembolsos.intentar(devolucion)
        self.assertFalse(reembolsos.intentar(devolucion))
        self.assertEqual(self.tx.refund.call_count, 1)

    def test_un_reembolso_en_curso_o_caido_a_medias_bloquea_el_reintento(self):
        devolucion = self.devolucion(2)
        ReembolsoTransbank.objects.create(devolucion=devolucion, token_ws='TOKEN-PAQUETE', monto=10000)  # sin confirmar
        self.assertFalse(reembolsos.intentar(devolucion))
        self.tx.refund.assert_not_called()
        self.assertIn('en curso', DevolucionVideos.objects.get(pk=devolucion.pk).error_reembolso)

    def test_sin_token_o_sin_monto_pagado_no_hay_reembolso_automatico(self):
        otro = self.paquete(videos=2)  # sin token_ws: es anterior al token o se pago de otra forma
        devolucion = self.devolucion(1, paquete=otro)
        self.assertFalse(reembolsos.intentar(devolucion))
        self.tx.refund.assert_not_called()
        self.assertTrue(DevolucionVideos.objects.get(pk=devolucion.pk).error_reembolso)

    def test_reparte_entre_el_agregado_y_los_extra_cada_uno_en_su_transaccion(self):
        paquete = self.paquete(videos=1)  # $5.000 en la transaccion del paquete
        paquete.token_ws = 'TOKEN-P2'
        paquete.save(update_fields=['token_ws'])
        extra = self.extra(paquete, 3)  # $13.500 en su propia transaccion
        extra.token_ws = 'TOKEN-EXTRA'
        extra.save(update_fields=['token_ws'])
        devolucion = self.devolucion(4, paquete=paquete)  # 4 x (18.500 // 4): todo lo pagado en videos
        self.assertEqual(devolucion.monto, 18500)
        self.assertTrue(reembolsos.intentar(devolucion))
        pedidos = {llamada.args[0]: llamada.args[1] for llamada in self.tx.refund.call_args_list}
        self.assertEqual(pedidos, {'TOKEN-EXTRA': 13500, 'TOKEN-P2': 5000})

    def test_si_una_parte_falla_las_confirmadas_se_conservan_y_falta_el_resto(self):
        paquete = self.paquete(videos=1)
        paquete.token_ws = 'TOKEN-P2'
        paquete.save(update_fields=['token_ws'])
        extra = self.extra(paquete, 3)
        extra.token_ws = 'TOKEN-EXTRA'
        extra.save(update_fields=['token_ws'])
        devolucion = self.devolucion(4, paquete=paquete)
        self.tx.refund.side_effect = [ANULADA, Exception('Monto a anular excede el saldo')]
        self.assertFalse(reembolsos.intentar(devolucion))
        devolucion.refresh_from_db()
        self.assertIsNone(devolucion.devuelta)
        self.assertEqual(devolucion.reembolsos.count(), 1)
        self.assertEqual(devolucion.por_devolver, devolucion.monto - devolucion.reembolsos.get().monto)

    def test_no_devuelve_mas_de_lo_que_se_pago_en_cada_transaccion(self):
        primera = self.devolucion(2)
        reembolsos.intentar(primera)
        segunda = self.devolucion(2)  # el agregado era de 4 videos ($20.000): quedan $10.000 en esa transaccion
        self.assertTrue(reembolsos.intentar(segunda))
        otra = devoluciones_videos.sin_entregar(self.paquete_ana)
        self.assertEqual(otra, 0)  # ya no queda nada por entregar ni por devolver
