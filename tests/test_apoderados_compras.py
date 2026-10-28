"""Fase 1c-i de menores: el apoderado contrata clases para su estudiante.

Datos ficticios; Webpay va con mock. El paquete queda a nombre del estudiante
y sigue el mismo flujo de pago; CompraApoderado registra quien lo pago. El
menor todavia no puede usarlo: las reservas por el apoderado son la 1c-ii.
"""

from datetime import time as hora
from unittest import mock

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Asignatura, Clase, PaqueteClases
from alumnos.services import MENSAJE_MENOR
from apoderados.models import Apoderado, CompraApoderado, Vinculo
from tests.test_apoderados import RUT, crear_apoderado, entrar
from tests.test_apoderados_vinculos import RUT_HERMANA, crear_menor_vinculado
from tests.test_especialidad import crear_profesor
from tests.test_filtros_clases import crear_sesion

PRECIO_PROGRESO = 59000  # tarifa base de $15.000 (tests/test_paquetes.py)


@mock.patch('alumnos.views._tx')
class CompraDelApoderadoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.profesor = crear_profesor('44444444-4', 'profe@demo.cl', None)
        cls.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        cls.vinculo = crear_menor_vinculado(cls.apoderado)

    def setUp(self):
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)

    def comprar(self, tx, vinculo=None, plan='progreso'):
        tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        url = reverse('apoderado_comprar_paquete', args=[(vinculo or self.vinculo).pk])
        return self.client.post(url, {'plan': plan, 'profesor': self.profesor.id_profesor})

    def confirmar(self, tx, paquete):
        tx.return_value.commit.return_value = {
            'response_code': 0, 'status': 'AUTHORIZED', 'buy_order': paquete.buy_order,
            'amount': paquete.monto, 'authorization_code': '1213', 'card_detail': {'card_number': '6623'}}
        return self.client.get(reverse('confirmacion'), {'token_ws': 'tok'})

    def test_planes_ofrece_contratar_para_el_estudiante(self, tx):
        respuesta = self.client.get(reverse('planes'), {'estudiante': self.vinculo.pk,
                                                        'profesor': self.profesor.id_profesor})
        self.assertContains(respuesta, reverse('apoderado_comprar_paquete', args=[self.vinculo.pk]))
        self.assertContains(respuesta, f'Contratando para {self.vinculo.alumno.user.first_name}')

    def test_el_paquete_queda_a_nombre_del_estudiante_y_se_activa_con_webpay(self, tx):
        self.assertEqual(self.comprar(tx).status_code, 200)
        self.assertEqual(tx.return_value.create.call_args[0][2], PRECIO_PROGRESO)
        paquete = PaqueteClases.objects.get()
        self.assertEqual((paquete.alumno, paquete.estado), (self.vinculo.alumno, PaqueteClases.ESTADO_PENDIENTE))
        compra = CompraApoderado.objects.get()
        self.assertEqual((compra.paquete, compra.apoderado, compra.vinculo), (paquete, self.apoderado, self.vinculo))

        self.assertContains(self.confirmar(tx, paquete), 'Volver a mi cuenta')
        paquete.refresh_from_db()
        self.assertEqual(paquete.estado, PaqueteClases.ESTADO_ACTIVA)

    def test_solo_con_vinculo_propio_verificado_y_apoderado_verificado(self, tx):
        ajeno = crear_menor_vinculado(crear_apoderado('55555555-5', Apoderado.VERIFICADO), rut=RUT_HERMANA)
        self.assertEqual(self.comprar(tx, ajeno).status_code, 404)
        for estado in (Vinculo.PENDIENTE, Vinculo.RECHAZADO):
            with self.subTest(vinculo=estado):
                Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=estado)
                self.assertEqual(self.comprar(tx).status_code, 404)
        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.VERIFICADO)
        Apoderado.objects.filter(pk=self.apoderado.pk).update(estado=Apoderado.RECHAZADO)
        self.assertEqual(self.comprar(tx).status_code, 404)

        tx.return_value.create.assert_not_called()
        self.assertFalse(PaqueteClases.objects.exists())
        respuesta = self.client.get(reverse('planes'), {'estudiante': ajeno.pk, 'profesor': self.profesor.id_profesor})
        self.assertNotContains(respuesta, 'Contratando para')

    def test_el_menor_y_los_anonimos_no_usan_la_compra_del_apoderado(self, tx):
        menor = self.vinculo.alumno
        entrar(self.client, menor.user, alumno_id=menor.id_alumno)
        self.assertEqual(self.comprar(tx).status_code, 302)
        self.client.logout()
        self.assertEqual(self.comprar(tx).status_code, 302)
        tx.return_value.create.assert_not_called()

    def test_plan_invalido_o_transbank_caido_no_crean_nada(self, tx):
        self.assertRedirects(self.comprar(tx, plan='gratis'), reverse('planes'), fetch_redirect_response=False)
        tx.return_value.create.side_effect = OSError('Transbank caido')
        self.client.post(reverse('apoderado_comprar_paquete', args=[self.vinculo.pk]),
                         {'plan': 'progreso', 'profesor': self.profesor.id_profesor})
        self.assertFalse(PaqueteClases.objects.exists())
        self.assertFalse(CompraApoderado.objects.exists())

    def test_si_falla_el_registro_del_apoderado_no_queda_el_paquete(self, tx):
        with mock.patch.object(CompraApoderado.objects, 'create', side_effect=IntegrityError('falla')):
            with self.assertRaises(IntegrityError):
                self.comprar(tx)
        self.assertFalse(PaqueteClases.objects.exists())

    def test_el_menor_aun_no_reserva_con_el_paquete_contratado(self, tx):
        self.comprar(tx)
        self.confirmar(tx, PaqueteClases.objects.get())
        clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                     modalidad='online', horario=hora(10, 0), profesor=self.profesor)
        sesion = crear_sesion(clase, dias=2)
        menor = self.vinculo.alumno
        entrar(self.client, menor.user, alumno_id=menor.id_alumno)
        respuesta = self.client.post(reverse('reservar_sesion'), {'id_sesion': sesion.pk}).json()
        self.assertEqual(respuesta, {'success': False, 'message': MENSAJE_MENOR})

    def test_el_portal_ofrece_contratar_solo_con_vinculo_verificado(self, tx):
        enlace = f"{reverse('planes')}?estudiante={self.vinculo.pk}"
        self.assertContains(self.client.get(reverse('portal_apoderado')), enlace)
        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.PENDIENTE)
        self.assertNotContains(self.client.get(reverse('portal_apoderado')), enlace)
