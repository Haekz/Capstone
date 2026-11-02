"""Un segundo apoderado se vincula a un menor ya registrado (decidido 02-nov, opcion A). Datos ficticios."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apoderados.forms import VERSION_DECLARACION_VINCULO
from apoderados.models import Apoderado, Vinculo
from tests.test_apoderados import RUT, crear_apoderado, entrar
from tests.test_apoderados_vinculos import CLAVE_NINO, crear_menor_vinculado

User = get_user_model()
RUT_SEGUNDO = '33333333-3'
NUEVA = 'Koala-Celeste-2026'


def vincular_segundo(alumno, apoderado, estado=Vinculo.VERIFICADO, parentesco='padre', **extra):
    return Vinculo.objects.create(apoderado=apoderado, alumno=alumno, parentesco=parentesco, estado=estado,
                                  version_declaracion=VERSION_DECLARACION_VINCULO,
                                  declaracion_aceptada=timezone.now(), **extra)


class ClaveSoloDeQuienCreoLaCuentaTests(TestCase):
    """La contrasena del menor no la cambia un segundo apoderado."""

    def setUp(self):
        self.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo_madre = crear_menor_vinculado(self.madre)
        self.padre = crear_apoderado(RUT_SEGUNDO, Apoderado.VERIFICADO)
        self.vinculo_padre = vincular_segundo(self.vinculo_madre.alumno, self.padre)
        self.alumno_user = self.vinculo_madre.alumno.user

    def entrar_como(self, apoderado):
        entrar(self.client, apoderado.user, apoderado_id=apoderado.id_apoderado)

    def cambiar(self, vinculo):
        return self.client.post(reverse('apoderado_clave_estudiante', args=[vinculo.pk]),
                                {'new_password1': NUEVA, 'new_password2': NUEVA})

    def clave_vigente(self):
        return User.objects.get(pk=self.alumno_user.pk).check_password(CLAVE_NINO)

    def test_el_segundo_apoderado_no_puede_cambiarla_aunque_su_vinculo_este_verificado(self):
        self.entrar_como(self.padre)
        self.assertEqual(self.cambiar(self.vinculo_padre).status_code, 404)
        self.assertTrue(self.clave_vigente())

    def test_tampoco_con_el_vinculo_pendiente(self):
        Vinculo.objects.filter(pk=self.vinculo_padre.pk).update(estado=Vinculo.PENDIENTE)
        self.entrar_como(self.padre)
        self.assertEqual(self.cambiar(self.vinculo_padre).status_code, 404)
        self.assertTrue(self.clave_vigente())

    def test_quien_creo_la_cuenta_sigue_pudiendo(self):
        self.entrar_como(self.madre)
        self.assertRedirects(self.cambiar(self.vinculo_madre), reverse('portal_apoderado'))
        self.assertFalse(self.clave_vigente())

    def test_el_portal_ofrece_cambiarla_solo_a_quien_creo_la_cuenta(self):
        enlace_madre = reverse('apoderado_clave_estudiante', args=[self.vinculo_madre.pk])
        enlace_padre = reverse('apoderado_clave_estudiante', args=[self.vinculo_padre.pk])
        self.entrar_como(self.madre)
        self.assertContains(self.client.get(reverse('portal_apoderado')), enlace_madre)
        self.entrar_como(self.padre)
        self.assertNotContains(self.client.get(reverse('portal_apoderado')), enlace_padre)

    def test_si_se_revoca_el_primer_vinculo_el_segundo_sigue_sin_poder(self):
        # Decision conservadora: la clave solo la define quien creo la cuenta. Si ya no esta, la maneja soporte.
        Vinculo.objects.filter(pk=self.vinculo_madre.pk).update(estado=Vinculo.REVOCADO)
        self.entrar_como(self.padre)
        self.assertEqual(self.cambiar(self.vinculo_padre).status_code, 404)
