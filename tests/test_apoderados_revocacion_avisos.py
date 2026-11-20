"""Avisos al revocarse un vinculo (pendiente 6, decidido 02-nov). Datos ficticios."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apoderados.models import Apoderado, Vinculo
from tests.test_apoderados import RUT, crear_agente, crear_apoderado, entrar, entrar_soporte
from tests.test_apoderados_segundo_apoderado import RUT_SEGUNDO, vincular_segundo
from tests.test_apoderados_vinculos import crear_menor_vinculado, hace_anios

User = get_user_model()
CORREO_MENOR = 'menor.ficticio@demo.cl'
MOTIVO = 'Resolucion judicial ficticia 123'


class AvisosRevocacionTests(TestCase):

    def setUp(self):
        self.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.alumno = crear_menor_vinculado(self.madre).alumno
        self.padre = crear_apoderado(RUT_SEGUNDO, Apoderado.VERIFICADO)
        self.vinculo_padre = vincular_segundo(self.alumno, self.padre)
        self.menor_con(edad=15, correo=CORREO_MENOR)

    def menor_con(self, edad, correo):
        User.objects.filter(pk=self.alumno.user_id).update(fecha_nacimiento=hace_anios(edad), email=correo)

    def se_desvincula_el_padre(self):
        entrar(self.client, self.padre.user, apoderado_id=self.padre.id_apoderado)
        self.client.post(reverse('apoderado_revocar_vinculo', args=[self.vinculo_padre.pk]), {'confirmar': 'on'})

    def soporte_revoca_al_padre(self):
        entrar_soporte(self.client, crear_agente('10000002-7', lider=True))
        self.client.post(reverse('apoderados_revocar_vinculo', args=[self.vinculo_padre.pk]),
                         {'motivo': MOTIVO, 'confirmar': 'on'})

    def correos_a(self, direccion):
        return [c for c in mail.outbox if c.to == [direccion]]

    def test_si_se_desvincula_solo_avisa_a_la_madre_y_al_adolescente_pero_no_a_el(self):
        self.se_desvincula_el_padre()
        self.assertEqual(Vinculo.objects.get(pk=self.vinculo_padre.pk).estado, Vinculo.REVOCADO)
        self.assertEqual(len(self.correos_a(self.madre.user.email)), 1)
        self.assertEqual(len(self.correos_a(CORREO_MENOR)), 1)
        self.assertEqual(self.correos_a(self.padre.user.email), [])

    def test_los_avisos_a_los_demas_no_dicen_quien_ni_por_que(self):
        self.soporte_revoca_al_padre()
        for correo in self.correos_a(self.madre.user.email) + self.correos_a(CORREO_MENOR):
            for privado in (MOTIVO, self.padre.nombre, self.padre.user.rut, self.padre.user.email):
                self.assertNotIn(privado, correo.subject + correo.body)

    def test_si_lo_revoca_soporte_el_revocado_recibe_el_motivo(self):
        self.soporte_revoca_al_padre()
        [correo] = self.correos_a(self.padre.user.email)
        self.assertIn(MOTIVO, correo.body)
        self.assertIn('revocó tu vínculo', correo.body)

    def test_un_menor_de_14_no_recibe_avisos_aunque_tenga_correo(self):
        self.menor_con(edad=12, correo=CORREO_MENOR)
        self.se_desvincula_el_padre()
        self.assertEqual(self.correos_a(CORREO_MENOR), [])
        self.assertEqual(len(self.correos_a(self.madre.user.email)), 1)

    def test_un_adolescente_sin_correo_no_recibe(self):
        self.menor_con(edad=15, correo='')
        self.se_desvincula_el_padre()
        self.assertEqual([c.to for c in mail.outbox], [[self.madre.user.email]])

    def test_retirar_una_solicitud_pendiente_no_avisa_a_nadie(self):
        Vinculo.objects.filter(pk=self.vinculo_padre.pk).update(estado=Vinculo.PENDIENTE)
        self.se_desvincula_el_padre()
        self.assertEqual(mail.outbox, [])

    def test_si_soporte_revoca_una_solicitud_pendiente_solo_se_entera_quien_la_hizo_sin_ver_el_nombre(self):
        Vinculo.objects.filter(pk=self.vinculo_padre.pk).update(estado=Vinculo.PENDIENTE, por_rut=True)
        self.soporte_revoca_al_padre()
        [correo] = mail.outbox
        self.assertEqual(correo.to, [self.padre.user.email])
        self.assertNotIn(self.alumno.user.first_name, correo.subject + correo.body)
