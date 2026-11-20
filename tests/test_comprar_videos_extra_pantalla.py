"""Videos extra, paso 6c: la pantalla "comprar mas videos", para el alumno adulto y para el apoderado del menor.

Se ofrece solo lo que se puede comprar de verdad (paquete vigente, 14 dias o mas, cupo bajo el tope). El menor no ve
el formulario: compra su apoderado, y queda registrado quien pago (apoderado y vinculo), como en los paquetes.
El precio que se muestra es informativo; el que se cobra lo calcula el servidor (6b). Webpay va con mock.
"""

from datetime import timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from alumnos import paquetes, videos_extra
from alumnos.models import PaqueteClases
from alumnos.models.videos import CompraVideosExtra
from apoderados.models import Apoderado
from tests.test_apoderados import crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA, Escenario
from tests.test_ver_videos import RUT_APODERADO, RUT_MENOR, RUT_OTRO_APODERADO, RUT_OTRO_MENOR


class Base(Escenario):

    def paquete(self, alumno, dias_restantes=30, estado=PaqueteClases.ESTADO_ACTIVA):
        return PaqueteClases.objects.create(
            alumno=alumno, profesor=self.profe, plan='progreso', clases=4, tarifa=15000, monto=59000, dias=60,
            buy_order=f'PQ{PaqueteClases.objects.count():024d}', estado=estado,
            fecha_fin=timezone.now() + timedelta(days=dias_restantes))


class OfertasTests(Base):

    def test_ofrece_de_1_hasta_lo_que_le_queda_con_su_precio(self):
        paquete = self.paquete(self.ana)
        [oferta] = videos_extra.ofertas(self.ana.pk)
        self.assertEqual(oferta['paquete'], paquete)
        self.assertEqual(oferta['opciones'], [(n, paquetes.precio_videos_extra(n)) for n in range(1, 7)])
        self.assertEqual(oferta['opciones'][2], (3, 13500))  # la promocion

    def test_descuenta_lo_ya_comprado(self):
        paquete = self.paquete(self.ana)
        CompraVideosExtra.objects.create(paquete=paquete, cantidad=4, monto=18500, buy_order='VX' + '1' * 24,
                                         estado=CompraVideosExtra.ESTADO_ACTIVA)
        [oferta] = videos_extra.ofertas(self.ana.pk)
        self.assertEqual([n for n, _ in oferta['opciones']], [1, 2])

    def test_no_ofrece_lo_que_no_se_puede_comprar(self):
        self.paquete(self.ana, dias_restantes=10)  # menos de 14 dias
        self.paquete(self.ana, dias_restantes=-1)  # vencido
        self.paquete(self.ana, estado=PaqueteClases.ESTADO_PENDIENTE)
        self.paquete(self.beto)  # de otro alumno
        self.assertEqual(videos_extra.ofertas(self.ana.pk), [])
        tope = self.paquete(self.ana)
        CompraVideosExtra.objects.create(paquete=tope, cantidad=6, monto=27000, buy_order='VX' + '2' * 24,
                                         estado=CompraVideosExtra.ESTADO_ACTIVA)
        self.assertEqual(videos_extra.ofertas(self.ana.pk), [])


class PantallaDelAlumnoTests(Base):

    def pagina(self):
        return self.client.get(reverse('alumno_pag1'))

    def test_el_adulto_ve_el_formulario_con_los_precios(self):
        paquete = self.paquete(self.ana)
        self.entrar(RUT_ANA)
        pagina = self.pagina()
        self.assertContains(pagina, f'action="{reverse("comprar_videos_extra")}"')
        self.assertContains(pagina, f'name="paquete" value="{paquete.pk}"')
        self.assertContains(pagina, '3 videos')
        self.assertContains(pagina, '$13.500')

    def test_sin_nada_que_comprar_no_hay_formulario(self):
        self.paquete(self.ana, dias_restantes=5)
        self.entrar(RUT_ANA)
        self.assertNotContains(self.pagina(), reverse('comprar_videos_extra'))

    def test_el_menor_no_ve_el_formulario(self):
        apoderado = crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO)
        menor = crear_menor_vinculado(apoderado, rut=RUT_MENOR).alumno
        self.paquete(menor)
        entrar(self.client, menor.user, alumno_id=menor.id_alumno)
        self.assertNotContains(self.pagina(), reverse('comprar_videos_extra'))

    @mock.patch('alumnos.webpay._tx')
    def test_si_la_compra_no_procede_vuelve_a_la_pestana_de_videos_con_el_motivo(self, tx):
        paquete = self.paquete(self.ana, dias_restantes=5)
        self.entrar(RUT_ANA)
        respuesta = self.client.post(reverse('comprar_videos_extra'), {'paquete': paquete.pk, 'cantidad': '1'}, follow=True)
        self.assertRedirects(respuesta, reverse('alumno_pag1') + '?pestana=videos')
        self.assertContains(respuesta, '14 días')  # el motivo se ve en la pantalla
        tx.return_value.create.assert_not_called()


@mock.patch('alumnos.webpay._tx')
class PantallaDelApoderadoTests(Base):

    def setUp(self):
        self.apoderado = crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, rut=RUT_MENOR)
        self.menor = self.vinculo.alumno
        self.paquete_menor = self.paquete(self.menor)
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)

    def url(self, vinculo=None):
        return reverse('apoderado_comprar_videos_extra', args=[(vinculo or self.vinculo).pk])

    def comprar(self, tx, cantidad='3', paquete=None, vinculo=None, follow=False):
        tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        return self.client.post(self.url(vinculo), {'paquete': (paquete or self.paquete_menor).pk, 'cantidad': cantidad},
                                follow=follow)

    def test_la_pagina_de_clases_trae_el_formulario(self, tx):
        pagina = self.client.get(reverse('apoderado_clases_estudiante', args=[self.vinculo.pk]))
        self.assertContains(pagina, f'action="{self.url()}"')
        self.assertContains(pagina, '$13.500')

    def test_compra_para_su_estudiante_y_queda_quien_pago(self, tx):
        respuesta = self.comprar(tx)
        self.assertContains(respuesta, 'https://webpay.test/')
        self.assertEqual(tx.return_value.create.call_args.args[2], 13500)
        compra = CompraVideosExtra.objects.get()
        self.assertEqual((compra.paquete, compra.apoderado, compra.vinculo),
                         (self.paquete_menor, self.apoderado, self.vinculo))

    def test_el_paquete_debe_ser_del_estudiante_de_ese_vinculo(self, tx):
        otro = self.paquete(self.ana)
        self.assertEqual(self.comprar(tx, paquete=otro).status_code, 404)
        self.assertEqual(CompraVideosExtra.objects.count(), 0)

    def test_no_se_compra_con_el_vinculo_de_otro_apoderado(self, tx):
        ajeno = crear_menor_vinculado(crear_apoderado(RUT_OTRO_APODERADO, Apoderado.VERIFICADO), rut=RUT_OTRO_MENOR)
        self.assertEqual(self.comprar(tx, vinculo=ajeno, paquete=self.paquete(ajeno.alumno)).status_code, 404)
        self.assertEqual(CompraVideosExtra.objects.count(), 0)
        tx.return_value.create.assert_not_called()

    def test_si_no_procede_vuelve_a_su_pagina_con_el_motivo(self, tx):
        corto = self.paquete(self.menor, dias_restantes=5)
        respuesta = self.comprar(tx, paquete=corto, follow=True)
        self.assertRedirects(respuesta, reverse('apoderado_clases_estudiante', args=[self.vinculo.pk]))
        self.assertContains(respuesta, '14 días')
        self.assertEqual(CompraVideosExtra.objects.count(), 0)

    def test_solo_por_post(self, tx):
        self.assertEqual(self.client.get(self.url()).status_code, 405)
