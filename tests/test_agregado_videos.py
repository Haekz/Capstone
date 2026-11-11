"""Agregado de videos (fase 2): se ofrece al comprar el paquete y se paga junto con él en Webpay.

El servidor calcula el precio (alumnos/paquetes.py); el navegador solo dice si lo quiere. `monto` sigue siendo
solo el de las clases (de él salen el valor por clase y el pago al profesor); los videos van en `monto_videos`.
Webpay va con mock.
"""

from unittest import mock

from django.test import TestCase
from django.urls import reverse

from alumnos import paquetes
from alumnos.models import PaqueteClases
from alumnos.webpay import registrar_respuesta
from apoderados.models import Apoderado, CompraApoderado
from tests.test_apoderados import RUT, crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_especialidad import crear_profesor
from tests.test_paquetes import RUT_ANA, Escenario

PRECIO_PROGRESO = 59000  # tarifa base de $15.000


def respuesta_webpay(paquete, monto):
    return {'response_code': 0, 'status': 'AUTHORIZED', 'buy_order': paquete.buy_order, 'amount': monto,
            'authorization_code': '1213', 'card_detail': {'card_number': '6623'}}


@mock.patch('alumnos.webpay._tx')
class AgregadoDelAlumnoTests(Escenario):

    def setUp(self):
        self.entrar(RUT_ANA)

    def comprar(self, tx, plan='progreso', **extra):
        tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        self.client.post(reverse('comprar_paquete'), {'plan': plan, 'profesor': self.profe.id_profesor, **extra})
        return PaqueteClases.objects.get(alumno=self.ana)

    def test_sin_agregado_cobra_solo_el_paquete(self, tx):
        paquete = self.comprar(tx)
        self.assertEqual(tx.return_value.create.call_args.args[2], PRECIO_PROGRESO)
        self.assertEqual((paquete.videos, paquete.monto_videos, paquete.total), (0, 0, PRECIO_PROGRESO))

    def test_con_agregado_cobra_todo_junto_y_las_clases_no_cambian(self, tx):
        for plan, videos, precio in (('flexible', 1, 5000), ('progreso', 4, 20000), ('intensivo', 6, 30000)):
            with self.subTest(plan=plan):
                PaqueteClases.objects.all().delete()
                paquete = self.comprar(tx, plan, videos='1')
                cotizacion = paquetes.Cotizacion(paquetes.POR_CODIGO[plan], self.profe.tarifa)
                self.assertEqual(tx.return_value.create.call_args.args[2], cotizacion.precio + precio)
                self.assertEqual((paquete.videos, paquete.monto_videos), (videos, precio))
                self.assertEqual((paquete.monto, paquete.precio_por_clase), (cotizacion.precio, cotizacion.precio_por_clase))

    def test_el_precio_lo_pone_el_servidor(self, tx):
        paquete = self.comprar(tx, videos='1', monto_videos='1', monto='1')
        self.assertEqual(paquete.total, PRECIO_PROGRESO + 20000)
        for otro in ('si', '4', '0', ''):
            with self.subTest(videos=otro):
                PaqueteClases.objects.all().delete()
                self.assertEqual(self.comprar(tx, videos=otro).monto_videos, 0)

    def test_se_aprueba_solo_si_transbank_cobro_el_total(self, tx):
        paquete = self.comprar(tx, videos='1')
        self.assertEqual(registrar_respuesta(respuesta_webpay(paquete, paquete.monto)), (False, paquete.buy_order))
        paquete.refresh_from_db()
        self.assertEqual(paquete.estado, PaqueteClases.ESTADO_RECHAZADA)
        PaqueteClases.objects.all().delete()
        paquete = self.comprar(tx, videos='1')
        self.assertTrue(registrar_respuesta(respuesta_webpay(paquete, paquete.total))[0])
        paquete.refresh_from_db()
        self.assertEqual(paquete.estado, PaqueteClases.ESTADO_ACTIVA)

    def test_la_confirmacion_muestra_el_agregado(self, tx):
        paquete = self.comprar(tx, videos='1')
        tx.return_value.commit.return_value = respuesta_webpay(paquete, paquete.total)
        pagina = self.client.get(reverse('confirmacion'), {'token_ws': 'tok'})
        self.assertContains(pagina, 'Agregado: 4 videos de ayuda')
        self.assertContains(pagina, '$20.000')

    def test_planes_ofrece_el_agregado_de_cada_plan(self, tx):
        pagina = self.client.get(reverse('planes'), {'profesor': self.profe.id_profesor})
        self.assertContains(pagina, 'id="pl-videos"')
        for videos, precio in ((1, '$5.000'), (4, '$20.000'), (6, '$30.000')):
            with self.subTest(videos=videos):
                self.assertContains(pagina, f'data-videos="{videos}" data-precio-videos="{precio}"')


@mock.patch('alumnos.webpay._tx')
class AgregadoDelApoderadoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.profesor = crear_profesor('44444444-4', 'profe@demo.cl', None)
        cls.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        cls.vinculo = crear_menor_vinculado(cls.apoderado)

    def test_el_apoderado_compra_el_agregado_para_su_estudiante(self, tx):
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)
        tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        self.client.post(reverse('apoderado_comprar_paquete', args=[self.vinculo.pk]),
                         {'plan': 'progreso', 'profesor': self.profesor.id_profesor, 'videos': '1'})
        paquete = PaqueteClases.objects.get(alumno=self.vinculo.alumno)
        self.assertEqual(tx.return_value.create.call_args.args[2], PRECIO_PROGRESO + 20000)
        self.assertEqual((paquete.videos, paquete.monto_videos), (4, 20000))
        self.assertTrue(CompraApoderado.objects.filter(paquete=paquete, apoderado=self.apoderado).exists())
        pagina = self.client.get(reverse('planes'), {'estudiante': self.vinculo.pk, 'profesor': self.profesor.id_profesor})
        self.assertContains(pagina, 'data-videos="4" data-precio-videos="$20.000"')
