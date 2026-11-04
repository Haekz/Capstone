"""El apoderado rechazado puede intentarlo de nuevo (decidido 03-nov, antes pendiente E). Datos ficticios.

Al decidir, soporte borra el documento: si rechazan, el apoderado sube otro y vuelve a la cola de revision. El rechazo
queda en su historial. Un vinculo revocado por soporte sigue siendo caso de contacto, no de reintento.
"""

from django.test import TestCase
from django.urls import reverse

from apoderados.models import Apoderado, Documento, RevisionIdentidad, Vinculo
from soporte.models import Ticket
from tests.test_apoderados import RUT, adjuntar, crear_agente, crear_apoderado, entrar, imagen
from tests.test_apoderados_vencidos import abiertos
from tests.test_apoderados_vinculos import crear_menor_vinculado


def subir_carnet(cliente):
    return cliente.post(reverse('apoderado_subir_carnet'),
                        {'carnet_frente': imagen('f.jpg'), 'carnet_reverso': imagen('r.jpg')})


class IdentidadRechazadaTests(TestCase):

    def setUp(self):
        crear_agente('10000001-9', Ticket.APODERADOS)
        self.apoderado = crear_apoderado(RUT, Apoderado.RECHAZADO)
        RevisionIdentidad.objects.create(apoderado=self.apoderado, decision=RevisionIdentidad.RECHAZAR,
                                         canal=RevisionIdentidad.DOCUMENTO_SUBIDO, observacion='La foto no se lee.')
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)

    def test_el_portal_muestra_el_motivo_y_ofrece_subir_el_carnet_de_nuevo(self):
        portal = self.client.get(reverse('portal_apoderado'))
        self.assertContains(portal, 'La foto no se lee.')
        self.assertContains(portal, 'Soporte rechazó la verificación de tu identidad y borró las fotos')
        self.assertContains(portal, reverse('apoderado_subir_carnet'))
        self.assertContains(portal, 'Subir carnet de nuevo')

    def test_la_pantalla_de_subida_habla_de_reintento_y_no_de_vencimiento(self):
        pantalla = self.client.get(reverse('apoderado_subir_carnet'))
        self.assertContains(pantalla, 'Soporte rechazó la verificación de tu identidad')
        self.assertNotContains(pantalla, 'o nunca las subiste')

    def test_al_subirlo_vuelve_a_revision_con_ticket_nuevo_y_conserva_el_rechazo(self):
        respuesta = subir_carnet(self.client)
        self.assertRedirects(respuesta, reverse('portal_apoderado'), fetch_redirect_response=False)
        self.apoderado.refresh_from_db()
        self.assertEqual(self.apoderado.estado, Apoderado.REVISION_PENDIENTE)
        self.assertTrue(self.apoderado.documentos_completos)
        self.assertTrue(abiertos(apoderado=self.apoderado).exists())
        self.assertEqual(self.apoderado.revisiones.count(), 1)  # el rechazo anterior queda en el historial

    def test_se_puede_reintentar_tras_otro_rechazo(self):
        for _ in range(2):
            subir_carnet(self.client)
            self.apoderado.documentos.all().delete()  # lo que hace soporte al rechazar
            Apoderado.objects.filter(pk=self.apoderado.pk).update(estado=Apoderado.RECHAZADO)
        self.assertEqual(subir_carnet(self.client).status_code, 302)
        self.apoderado.refresh_from_db()
        self.assertEqual(self.apoderado.estado, Apoderado.REVISION_PENDIENTE)

    def test_con_el_carnet_ya_completo_no_hay_nada_que_reintentar(self):
        for tipo in Documento.CARNET:
            adjuntar(tipo, apoderado=self.apoderado)
        self.assertEqual(self.client.get(reverse('apoderado_subir_carnet')).status_code, 404)

    def test_correo_sin_confirmar_no_puede_subir_carnet(self):
        Apoderado.objects.filter(pk=self.apoderado.pk).update(estado=Apoderado.CORREO_PENDIENTE)
        self.assertEqual(self.client.get(reverse('apoderado_subir_carnet')).status_code, 404)


class VinculoRechazadoTests(TestCase):

    def setUp(self):
        crear_agente('10000001-9', Ticket.APODERADOS)
        self.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, estado=Vinculo.RECHAZADO)
        self.url = reverse('apoderado_subir_documento_vinculo', args=[self.vinculo.pk])
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)

    def test_el_portal_ofrece_subir_otro_documento_y_sigue_ofreciendo_volver_a_pedir(self):
        portal = self.client.get(reverse('portal_apoderado'))
        self.assertContains(portal, self.url)
        self.assertContains(portal, 'Subir otro documento')
        self.assertContains(portal, 'Soporte rechazó el vínculo y borró el documento')
        self.assertContains(portal, 'Volver a pedir el vínculo')

    def test_la_pantalla_de_subida_habla_de_reintento(self):
        pantalla = self.client.get(self.url)
        self.assertContains(pantalla, 'Soporte rechazó el vínculo')
        self.assertNotContains(pantalla, 'o nunca lo subiste')

    def test_al_subirlo_vuelve_a_pendiente_con_ticket_nuevo(self):
        respuesta = self.client.post(self.url, {'documento': imagen()})
        self.assertRedirects(respuesta, reverse('portal_apoderado'), fetch_redirect_response=False)
        self.vinculo.refresh_from_db()
        self.assertEqual(self.vinculo.estado, Vinculo.PENDIENTE)
        self.assertTrue(self.vinculo.documentos_completos)
        self.assertTrue(abiertos(vinculo=self.vinculo).exists())

    def test_con_la_identidad_rechazada_queda_pendiente_pero_sin_ticket_hasta_verificarse(self):
        Apoderado.objects.filter(pk=self.apoderado.pk).update(estado=Apoderado.RECHAZADO)
        self.client.post(self.url, {'documento': imagen()})
        self.vinculo.refresh_from_db()
        self.assertEqual(self.vinculo.estado, Vinculo.PENDIENTE)
        self.assertFalse(abiertos(vinculo=self.vinculo).exists())  # nunca un ticket de un apoderado sin verificar

    def test_el_revocado_por_soporte_y_el_ajeno_siguen_sin_poder(self):
        revocado = crear_menor_vinculado(self.apoderado, rut='16161616-1', estado=Vinculo.REVOCADO)
        ajeno = crear_menor_vinculado(crear_apoderado('15151515-1', Apoderado.VERIFICADO), rut='17171717-1',
                                      estado=Vinculo.RECHAZADO)
        for nombre, vinculo in (('revocado', revocado), ('ajeno', ajeno)):
            with self.subTest(vinculo=nombre):
                self.assertEqual(self.client.get(reverse('apoderado_subir_documento_vinculo', args=[vinculo.pk])
                                                 ).status_code, 404)
