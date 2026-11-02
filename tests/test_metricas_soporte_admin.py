"""P13: el admin ve cifras de soporte (cuantos y en cuanto tiempo), nunca el contenido."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from admin_portal.metricas import soporte
from soporte.models import Ticket
from tests.test_retiros import crear_admin, entrar_admin


class SoporteEnCifrasTests(TestCase):

    def setUp(self):
        self.autor = get_user_model().objects.create_user('11111111-1', rut='11111111-1', password='x', rol='alumno')
        self.ahora = timezone.now()

    def ticket(self, categoria, horas_plazo=48, respondido_en=None, cerrado_en=None, titulo=''):
        """Ticket de usuario creado hace 3 dias; respondido/cerrado N horas despues de creado."""
        creado = self.ahora - timedelta(days=3)
        ticket = Ticket.objects.create(categoria=categoria, autor=self.autor, titulo=titulo,
                                       vence=creado + timedelta(hours=horas_plazo))
        cambios = {'creado': creado}  # creado es auto_now_add: se fija despues
        if respondido_en is not None:
            cambios['respondido'] = creado + timedelta(hours=respondido_en)
        if cerrado_en is not None:
            cambios.update(estado=Ticket.CERRADO, cerrado=creado + timedelta(hours=cerrado_en))
        Ticket.objects.filter(pk=ticket.pk).update(**cambios)

    def fila(self, cifras, nombre):
        return next(c for c in cifras['por_categoria'] if c['nombre'] == nombre)

    def test_sin_tickets(self):
        cifras = soporte(self.ahora)
        self.assertEqual((cifras['abiertos'], cifras['atrasados']), (0, 0))
        self.assertIsNone(cifras['horas_respuesta'])
        self.assertIsNone(cifras['dias_cierre'])
        self.assertEqual(len(cifras['por_categoria']), len(Ticket.CATEGORIAS))

    def test_cuenta_por_categoria_con_la_regla_de_atraso_de_soporte(self):
        self.ticket(Ticket.PAGOS)                          # plazo vencido sin respuesta: atrasado
        self.ticket(Ticket.PAGOS, respondido_en=60)        # vencido pero respondido: no atrasado
        self.ticket(Ticket.CLASES, horas_plazo=24 * 5)     # aun en plazo
        self.ticket(Ticket.TECNICO, cerrado_en=10)
        cifras = soporte(self.ahora)
        self.assertEqual((cifras['abiertos'], cifras['atrasados']), (3, 1))
        nombre_pagos = dict(Ticket.CATEGORIAS)[Ticket.PAGOS]
        self.assertEqual(self.fila(cifras, nombre_pagos), {'nombre': nombre_pagos, 'abiertos': 2,
                                                           'atrasados': 1, 'cerrados': 0})
        self.assertEqual(self.fila(cifras, dict(Ticket.CATEGORIAS)[Ticket.TECNICO])['cerrados'], 1)

    def test_tiempos_promedio(self):
        self.ticket(Ticket.PAGOS, respondido_en=2, cerrado_en=24)
        self.ticket(Ticket.CLASES, respondido_en=4, cerrado_en=48)
        cifras = soporte(self.ahora)
        self.assertEqual(cifras['horas_respuesta'], '3,0')
        self.assertEqual(cifras['dias_cierre'], '1,5')

    def test_el_panel_muestra_cifras_y_no_el_contenido(self):
        self.ticket(Ticket.PAGOS, titulo='Me cobraron dos veces')
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)
        respuesta = self.client.get(reverse('dashboard_admin'))
        self.assertContains(respuesta, 'Soporte en cifras')
        self.assertContains(respuesta, '1 abierto ·')
        self.assertContains(respuesta, '1 atrasado ·')
        self.assertNotContains(respuesta, 'Me cobraron dos veces')
