"""Volver a pedir el vinculo tras un rechazo o tras desvincularse uno mismo (pendiente 5, decidido 02-nov)."""

from django.test import TestCase
from django.urls import reverse

from apoderados.models import Apoderado, Revocacion, Vinculo
from soporte.models import Ticket
from tests.test_apoderados import RUT, crear_agente, crear_apoderado, entrar, entrar_soporte
from tests.test_apoderados_segundo_apoderado import NUEVA, RUT_SEGUNDO, vincular_segundo
from tests.test_apoderados_vincular import datos_vinculo
from tests.test_apoderados_vinculos import crear_menor_vinculado


class VolverAPedirTests(TestCase):

    def setUp(self):
        self.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo_madre = crear_menor_vinculado(self.madre)
        self.alumno = self.vinculo_madre.alumno
        self.padre = crear_apoderado(RUT_SEGUNDO, Apoderado.VERIFICADO)
        self.vinculo = vincular_segundo(self.alumno, self.padre)

    def entrar_como(self, apoderado):
        entrar(self.client, apoderado.user, apoderado_id=apoderado.id_apoderado)

    def desvincularse(self, apoderado, vinculo):
        self.entrar_como(apoderado)
        self.client.post(reverse('apoderado_revocar_vinculo', args=[vinculo.pk]), {'confirmar': 'on'})

    def revoca_soporte(self, vinculo):
        entrar_soporte(self.client, crear_agente('10000002-7', lider=True))
        self.client.post(reverse('apoderados_revocar_vinculo', args=[vinculo.pk]),
                         {'motivo': 'Motivo ficticio', 'confirmar': 'on'})

    def pedir(self, apoderado):
        self.entrar_como(apoderado)
        return self.client.post(reverse('apoderado_vincular_estudiante'), datos_vinculo())

    def recargar(self, vinculo):
        return Vinculo.objects.get(pk=vinculo.pk)

    def test_un_rechazado_puede_volver_a_pedirlo_con_documento_y_ticket_nuevos(self):
        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.RECHAZADO)
        self.assertRedirects(self.pedir(self.padre), reverse('portal_apoderado'))
        vinculo = self.recargar(self.vinculo)  # mismo vinculo: conserva su historial
        self.assertEqual((vinculo.estado, vinculo.por_rut), (Vinculo.PENDIENTE, True))
        self.assertTrue(vinculo.documentos_completos)
        self.assertEqual(vinculo.tickets.filter(estado=Ticket.ABIERTO).count(), 1)
        self.assertEqual(Vinculo.objects.filter(apoderado=self.padre).count(), 1)

    def test_quien_se_desvinculo_solo_puede_volver_y_se_conservan_sus_revocaciones(self):
        self.desvincularse(self.padre, self.vinculo)
        self.assertRedirects(self.pedir(self.padre), reverse('portal_apoderado'))
        self.assertEqual(self.recargar(self.vinculo).estado, Vinculo.PENDIENTE)
        self.assertEqual(Revocacion.objects.filter(vinculo=self.vinculo).count(), 1)
        self.desvincularse(self.padre, self.vinculo)  # se puede revocar otra vez
        self.assertEqual(Revocacion.objects.filter(vinculo=self.vinculo).count(), 2)
        self.assertEqual(self.recargar(self.vinculo).revocacion, Revocacion.objects.latest('pk'))

    def test_si_lo_revoco_soporte_no_puede_volver_por_su_cuenta(self):
        self.revoca_soporte(self.vinculo)
        respuesta = self.pedir(self.padre)
        self.assertContains(respuesta, 'escríbenos desde la página de contacto')
        self.assertEqual(self.recargar(self.vinculo).estado, Vinculo.REVOCADO)

    def test_con_el_vinculo_vigente_no_lo_pide_de_nuevo(self):
        self.assertContains(self.pedir(self.padre), 'Ya tienes un vínculo')

    def test_el_portal_ofrece_volver_solo_cuando_corresponde(self):
        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.RECHAZADO)
        self.entrar_como(self.padre)
        self.assertContains(self.client.get(reverse('portal_apoderado')), 'Volver a pedir el vínculo')
        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.VERIFICADO)
        self.revoca_soporte(self.vinculo)
        self.entrar_como(self.padre)
        respuesta = self.client.get(reverse('portal_apoderado'))
        self.assertNotContains(respuesta, 'Volver a pedir el vínculo')
        self.assertContains(respuesta, 'Para volver a vincularte, escríbenos')

    def test_quien_creo_la_cuenta_y_vuelve_no_recupera_la_contrasena_del_menor(self):
        self.desvincularse(self.madre, self.vinculo_madre)
        self.pedir(self.madre)
        vinculo = self.recargar(self.vinculo_madre)
        self.assertFalse(vinculo.apoderado_define_clave)
        respuesta = self.client.post(reverse('apoderado_clave_estudiante', args=[vinculo.pk]),
                                     {'new_password1': NUEVA, 'new_password2': NUEVA})
        self.assertEqual(respuesta.status_code, 404)
