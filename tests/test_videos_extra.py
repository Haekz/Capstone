"""Videos extra, paso 6a: el modelo de la compra y sus reglas (todavia sin pagar con Webpay).

Politica (seccion 12), decidido 09-nov: despues de contratar se pueden comprar videos extra a $5.000 cada uno o 3 por
$13.500, maximo 6 por paquete, solo si al paquete le quedan 14 dias o mas. Puede comprarlos cualquier paquete vigente
(haya o no contratado el agregado al inicio). El profesor tiene 14 dias desde cada compra para compartirlos.
Una compra pendiente (Webpay sin confirmar) ya cuenta para el tope: evita pasarse comprando dos veces seguidas.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import timezone

from alumnos import paquetes, videos_extra
from alumnos.models import PaqueteClases
from alumnos.models.videos import CompraVideosExtra
from tests.test_paquetes import Escenario


class ReglasVideosExtraTests(SimpleTestCase):

    def test_constantes_de_la_politica(self):
        self.assertEqual((paquetes.DIAS_ENTREGA_EXTRA, paquetes.MIN_DIAS_PARA_EXTRA), (14, 14))


class VideosExtraTests(Escenario):

    def paquete(self, dias_restantes=30, videos=0, estado=PaqueteClases.ESTADO_ACTIVA, alumno=None):
        return PaqueteClases.objects.create(
            alumno=alumno or self.ana, profesor=self.profe, plan='progreso', clases=4, tarifa=15000, monto=59000,
            videos=videos, monto_videos=videos * paquetes.PRECIO_VIDEO, dias=60,
            buy_order=f'PQ{PaqueteClases.objects.count():024d}', estado=estado,
            fecha_fin=timezone.now() + timedelta(days=dias_restantes))

    def comprar(self, paquete, cantidad, estado=CompraVideosExtra.ESTADO_ACTIVA):
        return CompraVideosExtra.objects.create(
            paquete=paquete, cantidad=cantidad, monto=paquetes.precio_videos_extra(cantidad),
            buy_order=f'VX{CompraVideosExtra.objects.count():024d}', estado=estado)

    def test_cualquier_paquete_vigente_con_14_dias_o_mas_puede_comprar(self):
        for videos in (0, 4):  # con o sin el agregado del inicio
            with self.subTest(videos=videos):
                self.assertEqual(videos_extra.validar(self.paquete(videos=videos), 3), 13500)

    def test_con_menos_de_14_dias_no(self):
        with self.assertRaisesMessage(ValidationError, '14 días'):
            videos_extra.validar(self.paquete(dias_restantes=13), 1)
        self.assertEqual(videos_extra.validar(self.paquete(dias_restantes=15), 1), 5000)

    def test_paquete_vencido_pendiente_o_rechazado_no(self):
        for paquete in (self.paquete(dias_restantes=-1), self.paquete(estado=PaqueteClases.ESTADO_PENDIENTE),
                        self.paquete(estado=PaqueteClases.ESTADO_RECHAZADA)):
            with self.subTest(estado=paquete.estado), self.assertRaisesMessage(ValidationError, 'vigente'):
                videos_extra.validar(paquete, 1)

    def test_maximo_6_por_paquete_contando_lo_ya_comprado(self):
        paquete = self.paquete()
        self.comprar(paquete, 4)
        self.assertEqual(videos_extra.disponibles(paquete), 2)
        self.assertEqual(videos_extra.validar(paquete, 2), 10000)
        with self.assertRaisesMessage(ValidationError, 'máximo 6'):
            videos_extra.validar(paquete, 3)

    def test_una_compra_pendiente_ya_cuenta_pero_una_rechazada_no(self):
        paquete = self.paquete()
        self.comprar(paquete, 3, estado=CompraVideosExtra.ESTADO_PENDIENTE)
        self.comprar(paquete, 3, estado=CompraVideosExtra.ESTADO_RECHAZADA)
        self.assertEqual(videos_extra.disponibles(paquete), 3)

    def test_la_cantidad_debe_ser_valida(self):
        for cantidad in (0, 7, -1):
            with self.subTest(cantidad=cantidad), self.assertRaises(ValidationError):
                videos_extra.validar(self.paquete(), cantidad)

    def test_cada_compra_entrega_14_dias_despues_de_pagarse(self):
        compra = self.comprar(self.paquete(), 1)
        self.assertIsNone(compra.fecha_limite)  # sin pago confirmado no hay plazo
        pagada = timezone.now() - timedelta(days=2)
        compra.fecha_pago = pagada
        self.assertEqual(compra.fecha_limite, pagada + timedelta(days=14))
