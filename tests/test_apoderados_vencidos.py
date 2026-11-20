"""Paso 5c: documentos que vencen sin revisar.

Datos ficticios. Al vencer se borran, se cierra el ticket (sin documentos no hay nada
que revisar) y se avisa al apoderado; desde su portal los vuelve a subir y se abre un
ticket nuevo. Nunca se abre un ticket sin documentos.
"""

import io
from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apoderados.models import Apoderado, Documento, Vinculo
from soporte.models import Ticket
from soporte.tickets import abrir_ticket
from tests.test_apoderados import RUT, adjuntar, crear_agente, crear_apoderado, entrar, imagen
from tests.test_apoderados_vinculos import crear_menor_vinculado


def vencer():
    Documento.objects.update(subido=timezone.now() - timedelta(days=31))
    call_command('borrar_documentos_vencidos', stdout=io.StringIO())


def abiertos(**revisado):
    return Ticket.objects.filter(estado=Ticket.ABIERTO, **revisado)


class CarnetVencidoTests(TestCase):

    def setUp(self):
        crear_agente('10000001-9', Ticket.APODERADOS)
        self.apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        for tipo in Documento.CARNET:
            adjuntar(tipo, apoderado=self.apoderado)
        abrir_ticket(Ticket.APODERADOS, apoderado=self.apoderado)
        self.viejo = Ticket.objects.get()
        mail.outbox.clear()
        vencer()
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)

    def test_al_vencer_se_cierra_el_ticket_y_se_avisa_al_apoderado(self):
        self.viejo.refresh_from_db()
        self.assertEqual(self.viejo.estado, Ticket.CERRADO)
        self.assertFalse(Documento.objects.exists())
        correo, = mail.outbox
        self.assertEqual(correo.to, [self.apoderado.user.email])
        self.assertIn('Vuelve a subir tus documentos', correo.subject)
        self.apoderado.refresh_from_db()
        self.assertEqual(self.apoderado.estado, Apoderado.REVISION_PENDIENTE)  # el atraso no lo rechaza

    def test_lo_vuelve_a_subir_desde_el_portal_y_se_abre_un_ticket_nuevo(self):
        self.assertContains(self.client.get(reverse('portal_apoderado')), reverse('apoderado_subir_carnet'))
        respuesta = self.client.post(reverse('apoderado_subir_carnet'),
                                     {'carnet_frente': imagen('f.jpg'), 'carnet_reverso': imagen('r.jpg')})
        self.assertRedirects(respuesta, reverse('portal_apoderado'), fetch_redirect_response=False)
        self.assertTrue(self.apoderado.documentos_completos)
        nuevo, = abiertos(apoderado=self.apoderado)
        self.assertNotEqual(nuevo.pk, self.viejo.pk)

    def test_con_el_carnet_completo_no_se_vuelve_a_subir(self):
        for tipo in Documento.CARNET:
            adjuntar(tipo, apoderado=self.apoderado)
        self.assertEqual(self.client.get(reverse('apoderado_subir_carnet')).status_code, 404)

    def test_confirmar_el_correo_sin_carnet_no_abre_ticket(self):
        sin_carnet = crear_apoderado('15151515-1')  # correo por confirmar y carnet ya vencido
        sin_carnet.confirmar_correo()
        self.assertEqual(sin_carnet.estado, Apoderado.REVISION_PENDIENTE)
        self.assertFalse(abiertos(apoderado=sin_carnet).exists())


class DocumentoVinculoVencidoTests(TestCase):

    def setUp(self):
        crear_agente('10000001-9', Ticket.APODERADOS)
        self.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, estado=Vinculo.PENDIENTE)
        adjuntar(Documento.CERTIFICADO, vinculo=self.vinculo)
        self.vinculo.abrir_ticket_si_revisable()
        mail.outbox.clear()
        vencer()
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)
        self.url = reverse('apoderado_subir_documento_vinculo', args=[self.vinculo.pk])

    def test_al_vencer_se_cierra_y_se_vuelve_a_subir_desde_el_portal(self):
        self.assertFalse(abiertos().exists())
        self.assertEqual([c.to for c in mail.outbox], [[self.apoderado.user.email]])
        self.assertContains(self.client.get(reverse('portal_apoderado')), self.url)

        self.client.post(self.url, {'documento': imagen()})

        self.assertTrue(self.vinculo.documentos_completos)
        self.assertTrue(abiertos(vinculo=self.vinculo).exists())

    def test_sin_documento_no_se_abre_el_ticket_del_vinculo(self):
        self.vinculo.abrir_ticket_si_revisable()
        self.assertFalse(abiertos(vinculo=self.vinculo).exists())

    def test_solo_vinculos_propios_y_pendientes(self):
        ajeno = crear_menor_vinculado(crear_apoderado('15151515-1', Apoderado.VERIFICADO), rut='16161616-1',
                                      estado=Vinculo.PENDIENTE)
        verificado = crear_menor_vinculado(self.apoderado, rut='17171717-1')
        for vinculo in (ajeno, verificado):
            with self.subTest(vinculo=vinculo.estado):
                url = reverse('apoderado_subir_documento_vinculo', args=[vinculo.pk])
                self.assertEqual(self.client.get(url).status_code, 404)


class RegistradoAntesDeLosDocumentosTests(TestCase):
    """Fase 2a empezó a pedir carnet y documento del vínculo. Quien se registró antes quedó en revisión sin
    documentos y sin ticket: nunca los subió, así que no se le puede decir que "vencieron"."""

    def setUp(self):
        crear_agente('10000001-9', Ticket.APODERADOS)

    def entrar_como(self, apoderado):
        entrar(self.client, apoderado.user, apoderado_id=apoderado.id_apoderado)

    def test_el_apoderado_en_revision_sin_carnet_ve_el_aviso_y_lo_sube(self):
        apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        self.assertFalse(Documento.objects.exists() or Ticket.objects.exists())
        self.entrar_como(apoderado)

        portal = self.client.get(reverse('portal_apoderado'))
        self.assertContains(portal, 'o nunca las subiste, o vencieron sin revisión')
        self.assertContains(portal, reverse('apoderado_subir_carnet'))
        pantalla = self.client.get(reverse('apoderado_subir_carnet'))
        self.assertContains(pantalla, 'Sube tu carnet')
        self.assertContains(pantalla, 'o nunca las subiste')

        respuesta = self.client.post(reverse('apoderado_subir_carnet'),
                                     {'carnet_frente': imagen('f.jpg'), 'carnet_reverso': imagen('r.jpg')})
        self.assertRedirects(respuesta, reverse('portal_apoderado'), fetch_redirect_response=False)
        self.assertTrue(apoderado.documentos_completos)
        self.assertTrue(abiertos(apoderado=apoderado).exists())  # recién ahí hay algo que revisar

    def test_a_quien_ya_esta_verificado_no_se_le_pide_el_carnet(self):
        apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.entrar_como(apoderado)
        self.assertNotContains(self.client.get(reverse('portal_apoderado')), reverse('apoderado_subir_carnet'))
        self.assertEqual(self.client.get(reverse('apoderado_subir_carnet')).status_code, 404)

    def test_el_vinculo_pendiente_sin_documento_se_puede_completar(self):
        apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        vinculo = crear_menor_vinculado(apoderado, estado=Vinculo.PENDIENTE)
        self.entrar_como(apoderado)
        url = reverse('apoderado_subir_documento_vinculo', args=[vinculo.pk])

        self.assertContains(self.client.get(reverse('portal_apoderado')), 'o nunca lo subiste, o venció sin revisión')
        self.assertContains(self.client.get(url), 'o nunca lo subiste')
        self.client.post(url, {'documento': imagen()})
        self.assertTrue(vinculo.documentos_completos)
        self.assertTrue(abiertos(vinculo=vinculo).exists())
