"""Transbank listo para produccion: falla ruidosa, token y autorizacion guardados, revision de pagos pendientes.

Cuando llegue la cuenta real, pasar a cobros reales debe ser solo cargar las cuatro variables de entorno.
Ninguna prueba llama a Transbank: va todo con mock.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import PaqueteClases
from alumnos.webpay import _tx
from lbwus.credenciales_transbank import validar_produccion
from tests.test_paquetes import RUT_ANA, Escenario

LIVE = dict(TRANSBANK_PRODUCCION_HABILITADA=True, TRANSBANK_ENVIRONMENT='LIVE',
            TRANSBANK_COMMERCE_CODE='597012345678', TRANSBANK_API_KEY='llave-de-prueba')


class ProduccionIncompletaTests(SimpleTestCase):
    """Riesgo: activar produccion a medias y seguir aceptando tarjetas de prueba como pagos reales."""

    def test_sin_produccion_habilitada_no_se_exige_nada(self):
        validar_produccion(False, 'TEST', '', '')  # no debe fallar

    def test_produccion_completa_no_falla(self):
        validar_produccion(True, 'LIVE', '597012345678', 'llave')

    def test_falta_cada_dato_y_el_error_dice_cual(self):
        casos = (('TRANSBANK_ENVIRONMENT=LIVE', ('TEST', 'cc', 'llave')),
                 ('TRANSBANK_ENVIRONMENT=LIVE', ('live', 'cc', 'llave')),  # el ambiente se normaliza en settings
                 ('TRANSBANK_COMMERCE_CODE', ('LIVE', '', 'llave')),
                 ('TRANSBANK_API_KEY', ('LIVE', 'cc', '')))
        for faltante, (ambiente, codigo, llave) in casos:
            with self.subTest(faltante=faltante, ambiente=ambiente):
                with self.assertRaisesMessage(ImproperlyConfigured, faltante):
                    validar_produccion(True, ambiente, codigo, llave)

    def test_el_pago_tampoco_cae_en_silencio_a_integracion(self):
        with self.settings(**{**LIVE, 'TRANSBANK_API_KEY': ''}):
            with self.assertRaisesMessage(ImproperlyConfigured, 'TRANSBANK_API_KEY'):
                _tx()


@patch('alumnos.webpay._tx')
class AutorizacionYTokenTests(Escenario):

    def comprar(self, mock_tx):
        self.entrar(RUT_ANA)
        mock_tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok-123'}
        self.client.post(reverse('comprar_paquete'), {'plan': 'progreso', 'profesor': self.profe.id_profesor})
        return PaqueteClases.objects.get()

    def volver(self, mock_tx, paquete, **extra):
        mock_tx.return_value.commit.return_value = {
            'response_code': 0, 'status': 'AUTHORIZED', 'amount': paquete.monto, 'buy_order': paquete.buy_order,
            'authorization_code': '1213', 'transaction_date': '2026-11-08T03:00:00.000Z', **extra}
        self.client.post(reverse('confirmacion'), {'token_ws': 'tok-123'})
        paquete.refresh_from_db()
        return paquete

    def test_al_iniciar_se_guarda_el_token_para_poder_consultarlo_despues(self, mock_tx):
        self.assertEqual(self.comprar(mock_tx).token_ws, 'tok-123')

    def test_al_aprobar_se_guardan_codigo_y_fecha_de_transbank_y_nada_de_la_tarjeta(self, mock_tx):
        paquete = self.volver(mock_tx, self.comprar(mock_tx), card_detail={'card_number': '6623'})
        self.assertEqual(paquete.estado, PaqueteClases.ESTADO_ACTIVA)
        self.assertEqual(paquete.codigo_autorizacion, '1213')
        self.assertEqual(paquete.fecha_pago.isoformat(), '2026-11-08T03:00:00+00:00')
        self.assertNotIn('6623', repr(paquete.__dict__))

    def test_un_retorno_repetido_no_pisa_los_datos_del_primero(self, mock_tx):
        paquete = self.volver(mock_tx, self.comprar(mock_tx))
        paquete = self.volver(mock_tx, paquete, authorization_code='9999', transaction_date='2030-01-01T00:00:00Z')
        self.assertEqual(paquete.codigo_autorizacion, '1213')
        self.assertEqual(paquete.fecha_pago.year, 2026)

    def test_un_pago_rechazado_no_guarda_autorizacion(self, mock_tx):
        paquete = self.volver(mock_tx, self.comprar(mock_tx), response_code=-1, status='FAILED')
        self.assertEqual((paquete.estado, paquete.codigo_autorizacion, paquete.fecha_pago),
                         (PaqueteClases.ESTADO_RECHAZADA, '', None))


@patch('alumnos.webpay._tx')
class RevisarPagosPendientesTests(Escenario):

    def pendiente(self, horas=2, token='tok-1', buy_order='PQ-ORDEN-1', monto=None):
        paquete = PaqueteClases.objects.create(
            alumno=self.ana, profesor=self.profe, plan='progreso', clases=4, tarifa=15000,
            monto=monto or 59000, dias=30, buy_order=buy_order, token_ws=token)
        PaqueteClases.objects.filter(pk=paquete.pk).update(creada=timezone.now() - timedelta(hours=horas))
        return paquete

    def revisar(self, mock_tx, respuesta=None, error=None):
        if error:
            mock_tx.return_value.status.side_effect = error
        else:
            mock_tx.return_value.status.return_value = respuesta
        salida = StringIO()
        call_command('revisar_pagos_pendientes', stdout=salida)
        return salida.getvalue()

    def estado(self, paquete):
        paquete.refresh_from_db()
        return paquete.estado

    def autorizado(self, paquete, **extra):
        return {'response_code': 0, 'status': 'AUTHORIZED', 'amount': paquete.monto, 'buy_order': paquete.buy_order,
                'authorization_code': '555', 'transaction_date': '2026-11-08T03:00:00.000Z', **extra}

    def test_pagado_que_no_volvio_se_activa_con_su_autorizacion(self, mock_tx):
        paquete = self.pendiente()
        salida = self.revisar(mock_tx, self.autorizado(paquete))
        self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_ACTIVA)
        self.assertEqual(paquete.codigo_autorizacion, '555')
        self.assertEqual(self.ana.paquetes.vigentes().count(), 1)
        self.assertIn('1 activados, 0 rechazados, 0 sin respuesta', salida)
        mock_tx.return_value.status.assert_called_once_with('tok-1')

    def test_abandonado_o_fallido_queda_rechazado(self, mock_tx):
        for estado, codigo in (('INITIALIZED', None), ('FAILED', -1), ('REVERSED', 0)):
            with self.subTest(estado=estado):
                PaqueteClases.objects.all().delete()
                paquete = self.pendiente()
                self.revisar(mock_tx, {'status': estado, 'response_code': codigo, 'amount': 59000,
                                       'buy_order': paquete.buy_order})
                self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_RECHAZADA)
                self.assertEqual(self.ana.paquetes.vigentes().count(), 0)

    def test_monto_distinto_se_rechaza_aunque_transbank_diga_autorizado(self, mock_tx):
        paquete = self.pendiente()
        self.revisar(mock_tx, self.autorizado(paquete, amount=1000))
        self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_RECHAZADA)

    def test_un_pago_reciente_no_se_toca_porque_el_alumno_puede_estar_pagando(self, mock_tx):
        paquete = self.pendiente(horas=0)
        self.revisar(mock_tx, self.autorizado(paquete))
        mock_tx.return_value.status.assert_not_called()
        self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_PENDIENTE)

    def test_si_transbank_no_responde_sigue_pendiente_y_se_informa(self, mock_tx):
        paquete = self.pendiente()
        salida = self.revisar(mock_tx, error=Exception('Transbank caido'))
        self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_PENDIENTE)
        self.assertIn('1 sin respuesta', salida)

    def test_si_la_respuesta_es_de_otra_orden_no_se_decide_nada(self, mock_tx):
        paquete = self.pendiente()
        self.revisar(mock_tx, {**self.autorizado(paquete), 'buy_order': 'PQ-AJENA'})
        self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_PENDIENTE)

    def test_sin_token_no_se_puede_consultar_y_queda_para_soporte(self, mock_tx):
        paquete = self.pendiente(token='')
        self.revisar(mock_tx, self.autorizado(paquete))
        mock_tx.return_value.status.assert_not_called()
        self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_PENDIENTE)

    def test_correrlo_dos_veces_no_cambia_lo_ya_resuelto(self, mock_tx):
        paquete = self.pendiente()
        self.revisar(mock_tx, self.autorizado(paquete))
        fin = PaqueteClases.objects.get(pk=paquete.pk).fecha_fin
        self.revisar(mock_tx, self.autorizado(paquete, authorization_code='999'))
        paquete.refresh_from_db()
        self.assertEqual((paquete.codigo_autorizacion, paquete.fecha_fin), ('555', fin))
