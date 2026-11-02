"""Aviso al apoderado ya vinculado cuando otra persona pide vincularse (opcion A, 02-nov). Datos ficticios."""

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apoderados.models import Apoderado, Vinculo
from soporte.models import Ticket
from tests.test_apoderados import RUT, crear_agente, crear_apoderado, entrar, entrar_soporte
from tests.test_apoderados_segundo_apoderado import RUT_SEGUNDO, vincular_segundo
from tests.test_apoderados_vincular import RUT_ADULTO, datos_vinculo
from tests.test_apoderados_vinculos import crear_menor_vinculado

RUT_TERCERO = '77777777-7'


class AvisoAlApoderadoVinculadoTests(TestCase):

    def setUp(self):
        self.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo_madre = crear_menor_vinculado(self.madre)
        self.nombre_menor = self.vinculo_madre.alumno.user.first_name
        self.padre = crear_apoderado(RUT_SEGUNDO, Apoderado.VERIFICADO)
        entrar(self.client, self.padre.user, apoderado_id=self.padre.id_apoderado)
        self.url = reverse('apoderado_vincular_estudiante')
        mail.outbox.clear()

    def test_el_apoderado_vinculado_recibe_un_aviso_sin_datos_de_quien_pidio(self):
        self.client.post(self.url, datos_vinculo())
        [correo] = mail.outbox
        self.assertEqual(correo.to, [self.madre.user.email])
        self.assertIn(self.nombre_menor, correo.subject + correo.body)
        for privado in (self.padre.nombre, self.padre.user.rut, self.padre.user.email):
            self.assertNotIn(privado, correo.subject + correo.body)

    def test_es_un_aviso_no_un_veto(self):
        self.client.post(self.url, datos_vinculo())
        self.vinculo_madre.refresh_from_db()
        self.assertEqual(self.vinculo_madre.estado, Vinculo.VERIFICADO)
        self.assertTrue(Vinculo.objects.filter(apoderado=self.padre, estado=Vinculo.PENDIENTE).exists())
        self.assertNotIn('responde', mail.outbox[0].body.lower())  # no pide confirmacion ni ofrece vetar

    def test_cada_apoderado_vinculado_recibe_el_suyo_sin_ver_al_otro(self):
        tercero = crear_apoderado(RUT_TERCERO, Apoderado.VERIFICADO)
        vincular_segundo(self.vinculo_madre.alumno, tercero)
        mail.outbox.clear()
        self.client.post(self.url, datos_vinculo())
        self.assertEqual(sorted(c.to[0] for c in mail.outbox), sorted([self.madre.user.email, tercero.user.email]))
        for correo in mail.outbox:
            self.assertEqual(len(correo.to), 1)
            self.assertNotIn(tercero.user.email if correo.to[0] == self.madre.user.email else self.madre.user.email,
                             correo.body)

    def test_quien_pide_no_recibe_el_aviso(self):
        self.client.post(self.url, datos_vinculo())
        self.assertNotIn(self.padre.user.email, [c.to[0] for c in mail.outbox])

    def test_si_no_hay_apoderados_verificados_no_se_envia_nada(self):
        Vinculo.objects.filter(pk=self.vinculo_madre.pk).update(estado=Vinculo.PENDIENTE)
        self.client.post(self.url, datos_vinculo())
        self.assertEqual(mail.outbox, [])

    def test_una_solicitud_que_falla_no_avisa_a_nadie(self):
        self.client.post(self.url, datos_vinculo(rut=RUT_ADULTO))  # no existe: respuesta neutra
        self.client.post(self.url, datos_vinculo(acepta_declaracion=''))
        self.assertEqual(mail.outbox, [])

    def test_soporte_ve_que_se_pidio_con_el_rut(self):
        agente = crear_agente('10000001-9', Ticket.APODERADOS)
        self.client.post(self.url, datos_vinculo())
        entrar_soporte(self.client, agente)
        respuesta = self.client.get(reverse('apoderados_revision'))
        self.assertContains(respuesta, 'Pedido con el RUT')
        self.assertContains(respuesta, 'verifica con especial cuidado')
