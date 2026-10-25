"""El precio que se muestra de cada plan es el que el servidor cobra.

PRECIOS_PLANES_OFICIALES manda (es lo que se envia a Transbank); la pantalla
solo lo refleja. Si alguien cambia uno sin el otro, estos tests fallan.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Alumno
from alumnos.views import PRECIOS_PLANES_OFICIALES, _clp

User = get_user_model()


class PreciosPlanesTests(TestCase):

    def assertMuestraPreciosOficiales(self, respuesta, clase_precio):
        for precio in PRECIOS_PLANES_OFICIALES.values():
            self.assertContains(respuesta, f'<span class="{clase_precio}">{_clp(precio)}</span>')

    def test_pagina_publica_de_planes(self):
        self.assertMuestraPreciosOficiales(self.client.get(reverse('planes')), 'plan-price')

    def test_portal_del_alumno(self):
        user = User.objects.create_user('11111111-1', rut='11111111-1',
                                        password='Clave12345!', rol='alumno')
        Alumno.objects.create(user=user, nivel_educacion='media')
        self.client.post(reverse('login'), {'username': '11111111-1', 'password': 'Clave12345!'})
        r = self.client.get(reverse('alumno_pag1'))
        self.assertMuestraPreciosOficiales(r, 'pp-price')
        for plan_id, precio in PRECIOS_PLANES_OFICIALES.items():  # el boton del carrito tambien
            self.assertContains(r, f"agregarPlanPortal('{plan_id}', ")
            self.assertContains(r, f"'{_clp(precio)}')")
