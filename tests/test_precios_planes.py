"""El precio que se muestra de cada paquete es el que el servidor cobra.

alumnos/paquetes.py manda: la pagina lo muestra y comprar_paquete se lo envia a
Transbank. Si alguien cambia uno sin el otro, estos tests fallan.
"""

from unittest.mock import patch

from django.urls import reverse

from alumnos import paquetes
from alumnos.templatetags.dinero import clp
from tests.test_paquetes import RUT_ANA, Escenario


@patch('alumnos.webpay._tx')
class PreciosPlanesTests(Escenario):

    def test_lo_que_muestra_la_pagina_es_lo_que_se_cobra(self, mock_tx):
        mock_tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        self.entrar(RUT_ANA)
        for profesor in (self.profe, self.otro):  # mismo precio con todos
            pagina = self.client.get(reverse('planes'), {'profesor': profesor.id_profesor})
            for plan in paquetes.PLANES:
                with self.subTest(profesor=profesor.nombre, plan=plan.codigo):
                    self.assertContains(pagina, f'<span class="plan-price">{clp(paquetes.precio(plan))}</span>')
                    self.client.post(reverse('comprar_paquete'),
                                     {'plan': plan.codigo, 'profesor': profesor.id_profesor})
                    self.assertEqual(mock_tx.return_value.create.call_args[0][2], paquetes.precio(plan))

    def test_el_portal_ya_no_ofrece_precios_viejos(self, mock_tx):
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('alumno_pag1'))
        for texto in ('$89.990', '$139.990', '$189.990', 'agregarPlanPortal'):
            self.assertNotContains(r, texto)
