"""Limites de las solicitudes de vinculo con el RUT del menor (decidido 02-nov). Datos ficticios."""

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apoderados.forms import VincularEstudianteForm
from apoderados.models import Apoderado, Vinculo
from tests.test_apoderados import RUT, crear_apoderado, entrar
from tests.test_apoderados_segundo_apoderado import RUT_SEGUNDO, vincular_segundo
from tests.test_apoderados_vincular import RUT_INEXISTENTE, crear_alumno, datos_vinculo
from tests.test_apoderados_vinculos import RUT_NINO, crear_menor_vinculado

LIMITE = VincularEstudianteForm.LIMITE_SIN_RESULTADO


class LimitesTests(TestCase):

    def setUp(self):
        cache.clear()
        self.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.alumno = crear_menor_vinculado(self.madre).alumno
        self.padre = crear_apoderado(RUT_SEGUNDO, Apoderado.VERIFICADO)
        entrar(self.client, self.padre.user, apoderado_id=self.padre.id_apoderado)
        self.url = reverse('apoderado_vincular_estudiante')

    def tearDown(self):
        cache.clear()

    def solicitar(self, rut=RUT_NINO):
        return self.client.post(self.url, datos_vinculo(rut=rut))

    def pidio_al_menor(self):
        return Vinculo.objects.filter(apoderado=self.padre, alumno=self.alumno).exists()

    def test_tras_5_busquedas_sin_resultado_se_bloquea_incluso_con_un_rut_correcto(self):
        for _ in range(LIMITE):
            self.assertContains(self.solicitar(RUT_INEXISTENTE), VincularEstudianteForm.SIN_COINCIDENCIA)
        self.assertContains(self.solicitar(), 'Hiciste varios intentos sin resultado')
        self.assertFalse(self.pidio_al_menor())

    def test_con_menos_de_5_todavia_puede(self):
        for _ in range(LIMITE - 1):
            self.solicitar(RUT_INEXISTENTE)
        self.assertRedirects(self.solicitar(), reverse('portal_apoderado'))

    def test_el_limite_es_de_cada_apoderado(self):
        for _ in range(LIMITE):
            self.solicitar(RUT_INEXISTENTE)
        otro = crear_apoderado('77777777-7', Apoderado.VERIFICADO)
        entrar(self.client, otro.user, apoderado_id=otro.id_apoderado)
        self.assertRedirects(self.solicitar(), reverse('portal_apoderado'))

    def test_un_rut_mal_escrito_no_cuenta_como_intento(self):
        for _ in range(LIMITE + 1):
            self.solicitar('abc')
        self.assertRedirects(self.solicitar(), reverse('portal_apoderado'))

    def test_no_mas_de_3_solicitudes_pendientes_a_la_vez(self):
        for numero in range(VincularEstudianteForm.LIMITE_PENDIENTES):
            vincular_segundo(crear_alumno(f'9000000{numero}-0', 10), self.padre, estado=Vinculo.PENDIENTE, por_rut=True)
        self.assertContains(self.solicitar(), 'solicitudes esperando verificación')
        self.assertFalse(self.pidio_al_menor())

    def test_las_pendientes_de_menores_que_registro_el_mismo_no_cuentan(self):
        for numero in range(VincularEstudianteForm.LIMITE_PENDIENTES):
            vincular_segundo(crear_alumno(f'9000000{numero}-0', 10), self.padre, estado=Vinculo.PENDIENTE)
        self.assertRedirects(self.solicitar(), reverse('portal_apoderado'))
