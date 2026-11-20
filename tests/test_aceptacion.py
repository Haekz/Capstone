"""Aceptacion de Terminos y Privacidad al comprar un paquete (alumnos/aceptacion.py).

Sin la casilla marcada no se cobra ni se crea el paquete; con ella se guarda quien acepto, que version y cuando; y no
se vuelve a pedir hasta que cambien los textos. El control es uno solo (`iniciar_compra_paquete`) y cubre al alumno y
al apoderado. Webpay va con mock.
"""

from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from alumnos import aceptacion
from alumnos.models import AceptacionLegal, PaqueteClases
from apoderados.models import Apoderado
from tests.test_apoderados import RUT, crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_especialidad import crear_profesor
from tests.test_paquetes import RUT_ANA, RUT_BETO, Escenario

CASILLA = {aceptacion.CAMPO: '1'}


@patch('alumnos.webpay._tx')
class AlumnoAceptaAlComprarTests(Escenario):

    def setUp(self):
        AceptacionLegal.objects.all().delete()  # el Escenario ya las da por aceptadas; aqui nadie acepto todavia
        self.entrar(RUT_ANA)

    def comprar(self, mock_tx, **extra):
        mock_tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        return self.client.post(reverse('comprar_paquete'), {
            'plan': 'progreso', 'profesor': self.profe.id_profesor, **extra})

    def test_sin_aceptar_no_se_cobra_ni_se_crea_el_paquete(self, mock_tx):
        respuesta = self.comprar(mock_tx)
        self.assertRedirects(respuesta, reverse('planes'), fetch_redirect_response=False)
        mock_tx.return_value.create.assert_not_called()
        self.assertFalse(PaqueteClases.objects.exists())
        self.assertFalse(AceptacionLegal.objects.exists())
        self.assertIn('aceptar los Términos', ' '.join(str(m) for m in get_messages(respuesta.wsgi_request)))

    def test_solo_cuenta_la_casilla_marcada(self, mock_tx):
        for valor in ('0', '', 'on', 'true'):
            with self.subTest(valor=valor):
                self.comprar(mock_tx, **{aceptacion.CAMPO: valor})
        mock_tx.return_value.create.assert_not_called()
        self.assertFalse(AceptacionLegal.objects.exists())

    def test_con_la_casilla_se_cobra_y_queda_la_prueba(self, mock_tx):
        self.assertEqual(self.comprar(mock_tx, **CASILLA).status_code, 200)
        mock_tx.return_value.create.assert_called_once()
        self.assertEqual(PaqueteClases.objects.count(), 1)
        aceptada = AceptacionLegal.objects.get()
        self.assertEqual((aceptada.user, aceptada.version), (self.ana.user, aceptacion.VERSION))
        self.assertIsNotNone(aceptada.aceptada)

    def test_quien_ya_acepto_no_vuelve_a_marcarla(self, mock_tx):
        self.comprar(mock_tx, **CASILLA)
        self.assertEqual(self.comprar(mock_tx).status_code, 200)  # segunda compra, sin casilla
        self.assertEqual(PaqueteClases.objects.count(), 2)
        self.assertEqual(AceptacionLegal.objects.count(), 1)  # y no se duplica la prueba

    def test_si_cambian_los_textos_se_pide_aceptar_de_nuevo(self, mock_tx):
        self.comprar(mock_tx, **CASILLA)
        with patch('alumnos.aceptacion.VERSION', '1 de enero de 2027'):
            self.assertEqual(self.comprar(mock_tx).status_code, 302)
            self.assertEqual(PaqueteClases.objects.count(), 1)
            self.assertEqual(self.comprar(mock_tx, **CASILLA).status_code, 200)
        self.assertEqual(AceptacionLegal.objects.count(), 2)  # una por version: queda el historial

    def test_cada_persona_acepta_por_si_misma(self, mock_tx):
        self.comprar(mock_tx, **CASILLA)  # Ana acepta
        self.entrar(RUT_BETO)
        self.assertEqual(self.comprar(mock_tx).status_code, 302)  # a Beto no le sirve lo de Ana

    def planes(self):
        return self.client.get(reverse('planes'), {'profesor': self.profe.id_profesor})

    def test_planes_muestra_la_casilla_con_los_enlaces_hasta_que_acepta(self, mock_tx):
        respuesta = self.planes()
        self.assertContains(respuesta, f'name="{aceptacion.CAMPO}"', count=3)  # una por plan
        self.assertContains(respuesta, f'href="{reverse("terminos")}"', count=3)
        self.assertContains(respuesta, f'href="{reverse("privacidad")}"', count=3)
        self.comprar(mock_tx, **CASILLA)
        self.assertNotContains(self.planes(), f'name="{aceptacion.CAMPO}"')

    def test_las_paginas_legales_muestran_la_version_que_se_acepta(self, mock_tx):
        for nombre in ('terminos', 'privacidad'):
            with self.subTest(pagina=nombre):
                self.assertContains(self.client.get(reverse(nombre)), aceptacion.VERSION)


@patch('alumnos.webpay._tx')
class ApoderadoAceptaAlComprarTests(TestCase):
    """Mismo control para el apoderado: el que paga es quien acepta."""

    @classmethod
    def setUpTestData(cls):
        cls.profesor = crear_profesor('44444444-4', 'profe@demo.cl', None)
        cls.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        cls.vinculo = crear_menor_vinculado(cls.apoderado)

    def setUp(self):
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)

    def comprar(self, mock_tx, **extra):
        mock_tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        return self.client.post(reverse('apoderado_comprar_paquete', args=[self.vinculo.pk]), {
            'plan': 'progreso', 'profesor': self.profesor.id_profesor, **extra})

    def test_sin_aceptar_no_se_cobra(self, mock_tx):
        self.assertEqual(self.comprar(mock_tx).status_code, 302)
        mock_tx.return_value.create.assert_not_called()
        self.assertFalse(PaqueteClases.objects.exists())

    def test_con_la_casilla_acepta_el_apoderado_y_no_el_estudiante(self, mock_tx):
        self.assertEqual(self.comprar(mock_tx, **CASILLA).status_code, 200)
        self.assertEqual(AceptacionLegal.objects.get().user, self.apoderado.user)
        self.assertEqual(PaqueteClases.objects.get().alumno, self.vinculo.alumno)

    def test_planes_le_muestra_la_casilla_al_apoderado(self, mock_tx):
        respuesta = self.client.get(reverse('planes'), {'estudiante': self.vinculo.pk,
                                                        'profesor': self.profesor.id_profesor})
        self.assertContains(respuesta, f'name="{aceptacion.CAMPO}"', count=3)
