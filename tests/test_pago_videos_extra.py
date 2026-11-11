"""Videos extra, paso 6b: pagar la compra con Webpay (iniciar, confirmar y revisar los pendientes).

Mismas garantias que la compra del paquete: el precio lo calcula el servidor, solo se aprueba si Transbank cobro
exactamente ese monto, y repetir la respuesta no cambia lo ya resuelto. Ademas: el paquete debe ser de quien compra
y el menor no compra solo (lo hace su apoderado, paso 6c). Webpay va con mock.
"""

from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from alumnos import paquetes
from alumnos.models import PaqueteClases
from alumnos.models.videos import CompraVideosExtra
from alumnos.webpay import registrar_respuesta
from apoderados.models import Apoderado
from tests.test_apoderados import crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA, Escenario
from tests.test_ver_videos import RUT_APODERADO, RUT_MENOR


def respuesta_webpay(compra, monto=None):
    return {'response_code': 0, 'status': 'AUTHORIZED', 'buy_order': compra.buy_order,
            'amount': compra.monto if monto is None else monto, 'authorization_code': '1213',
            'card_detail': {'card_number': '6623'}}


@mock.patch('alumnos.webpay._tx')
class PagoVideosExtraTests(Escenario):

    def setUp(self):
        self.entrar(RUT_ANA)
        self.paquete = self.crear_paquete(self.ana)

    def crear_paquete(self, alumno, dias_restantes=30):
        return PaqueteClases.objects.create(
            alumno=alumno, profesor=self.profe, plan='progreso', clases=4, tarifa=15000, monto=59000, dias=60,
            buy_order=f'PQ{PaqueteClases.objects.count():024d}', estado=PaqueteClases.ESTADO_ACTIVA,
            fecha_fin=timezone.now() + timedelta(days=dias_restantes))

    def comprar(self, tx, cantidad='3', paquete=None, **extra):
        tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        return self.client.post(reverse('comprar_videos_extra'),
                                {'paquete': (paquete or self.paquete).pk, 'cantidad': cantidad, **extra})

    def compras(self):
        return CompraVideosExtra.objects.all()

    # --- iniciar el pago ---
    def test_cobra_el_precio_del_servidor_y_deja_la_compra_pendiente(self, tx):
        for cantidad, precio in ((1, 5000), (3, 13500), (4, 18500)):
            with self.subTest(cantidad=cantidad):
                self.compras().delete()
                respuesta = self.comprar(tx, str(cantidad))
                self.assertContains(respuesta, 'https://webpay.test/')  # lo manda a Webpay
                self.assertEqual(tx.return_value.create.call_args.args[2], precio)
                [compra] = self.compras()
                self.assertEqual((compra.cantidad, compra.monto, compra.estado, compra.token_ws),
                                 (cantidad, precio, CompraVideosExtra.ESTADO_PENDIENTE, 'tok'))
                self.assertTrue(compra.buy_order.startswith('VX') and len(compra.buy_order) == 26)

    def test_el_navegador_no_pone_el_precio(self, tx):
        self.comprar(tx, '3', monto='1', monto_videos='1')
        self.assertEqual(self.compras().get().monto, 13500)

    def test_un_paquete_ajeno_es_404_y_no_se_cobra(self, tx):
        ajeno = self.crear_paquete(self.beto)
        self.assertEqual(self.comprar(tx, '1', paquete=ajeno).status_code, 404)
        self.assertEqual(self.compras().count(), 0)
        tx.return_value.create.assert_not_called()

    def test_si_no_cumple_las_reglas_no_se_cobra(self, tx):
        corto = self.crear_paquete(self.ana, dias_restantes=10)  # menos de 14 dias
        self.comprar(tx, '1', paquete=corto)
        for cantidad in ('0', '7', '-1', 'tres', ''):
            self.comprar(tx, cantidad)
        self.assertEqual(self.compras().count(), 0)
        tx.return_value.create.assert_not_called()

    def test_una_compra_pendiente_ya_cuenta_para_el_tope(self, tx):
        self.comprar(tx, '4')
        self.comprar(tx, '3')  # 4 + 3 pasa de 6: no se cobra
        self.assertEqual([c.cantidad for c in self.compras()], [4])
        self.assertEqual(tx.return_value.create.call_count, 1)

    def test_si_transbank_falla_no_queda_compra(self, tx):
        tx.return_value.create.side_effect = RuntimeError('caido')
        self.client.post(reverse('comprar_videos_extra'), {'paquete': self.paquete.pk, 'cantidad': '1'})
        self.assertEqual(self.compras().count(), 0)

    def test_solo_por_post(self, tx):
        self.assertEqual(self.client.get(reverse('comprar_videos_extra')).status_code, 405)

    def test_el_menor_no_compra_solo(self, tx):
        apoderado = crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO)
        menor = crear_menor_vinculado(apoderado, rut=RUT_MENOR).alumno
        entrar(self.client, menor.user, alumno_id=menor.id_alumno)
        self.comprar(tx, '1', paquete=self.crear_paquete(menor))
        self.assertEqual(self.compras().count(), 0)
        tx.return_value.create.assert_not_called()

    # --- confirmar el pago ---
    def pendiente(self, tx, cantidad='3'):
        self.comprar(tx, cantidad)
        return self.compras().get()

    def test_se_activa_solo_si_transbank_cobro_el_monto_exacto(self, tx):
        compra = self.pendiente(tx)
        self.assertEqual(registrar_respuesta(respuesta_webpay(compra, monto=compra.monto - 1)),
                         (False, compra.buy_order))
        compra.refresh_from_db()
        self.assertEqual(compra.estado, CompraVideosExtra.ESTADO_RECHAZADA)

    def test_aprobada_queda_activa_con_su_plazo_de_14_dias(self, tx):
        compra = self.pendiente(tx)
        self.assertTrue(registrar_respuesta(respuesta_webpay(compra))[0])
        compra.refresh_from_db()
        self.assertEqual((compra.estado, compra.codigo_autorizacion), (CompraVideosExtra.ESTADO_ACTIVA, '1213'))
        self.assertIsNotNone(compra.fecha_pago)
        self.assertEqual(compra.fecha_limite, compra.fecha_pago + timedelta(days=paquetes.DIAS_ENTREGA_EXTRA))

    def test_repetir_la_respuesta_no_cambia_lo_ya_resuelto(self, tx):
        compra = self.pendiente(tx)
        registrar_respuesta(respuesta_webpay(compra))
        compra.refresh_from_db()
        primera = (compra.fecha_pago, compra.codigo_autorizacion)
        registrar_respuesta({**respuesta_webpay(compra), 'authorization_code': '9999'})
        registrar_respuesta({**respuesta_webpay(compra), 'response_code': -1})  # un rechazo tardio no la anula
        compra.refresh_from_db()
        self.assertEqual((compra.fecha_pago, compra.codigo_autorizacion), primera)
        self.assertEqual(compra.estado, CompraVideosExtra.ESTADO_ACTIVA)

    def test_una_respuesta_de_otra_orden_no_toca_nada(self, tx):
        compra = self.pendiente(tx)
        registrar_respuesta({**respuesta_webpay(compra), 'buy_order': 'VX' + 'f' * 24})
        compra.refresh_from_db()
        self.assertEqual(compra.estado, CompraVideosExtra.ESTADO_PENDIENTE)

    def test_la_confirmacion_muestra_los_videos_extra(self, tx):
        compra = self.pendiente(tx)
        tx.return_value.commit.return_value = respuesta_webpay(compra)
        pagina = self.client.get(reverse('confirmacion'), {'token_ws': 'tok'})
        self.assertContains(pagina, 'Videos extra: 3 videos de apoyo')
        self.assertContains(pagina, '$13.500')

    # --- pagos que no volvieron ---
    def revisar(self):
        salida = StringIO()
        call_command('revisar_pagos_pendientes', stdout=salida)
        return salida.getvalue()

    def test_la_tarea_diaria_activa_la_compra_pagada_que_no_volvio(self, tx):
        compra = self.pendiente(tx)
        CompraVideosExtra.objects.filter(pk=compra.pk).update(creada=timezone.now() - timedelta(hours=2))
        tx.return_value.status.return_value = respuesta_webpay(compra)
        self.assertIn('1 activados', self.revisar())
        compra.refresh_from_db()
        self.assertEqual(compra.estado, CompraVideosExtra.ESTADO_ACTIVA)

    def test_la_tarea_diaria_rechaza_la_abandonada_y_respeta_a_la_reciente(self, tx):
        vieja = self.pendiente(tx, '1')
        CompraVideosExtra.objects.filter(pk=vieja.pk).update(creada=timezone.now() - timedelta(hours=2))
        reciente = self.pendiente_nueva(tx)
        tx.return_value.status.return_value = {**respuesta_webpay(vieja), 'response_code': -1, 'status': 'FAILED'}
        self.assertIn('1 rechazados', self.revisar())
        vieja.refresh_from_db()
        reciente.refresh_from_db()
        self.assertEqual((vieja.estado, reciente.estado),
                         (CompraVideosExtra.ESTADO_RECHAZADA, CompraVideosExtra.ESTADO_PENDIENTE))

    def pendiente_nueva(self, tx):
        tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok2'}
        self.client.post(reverse('comprar_videos_extra'), {'paquete': self.paquete.pk, 'cantidad': '1'})
        return self.compras().exclude(token_ws='tok').get()
