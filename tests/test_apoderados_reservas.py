"""El apoderado reserva, cancela y reprograma por su estudiante.

Datos ficticios. Solo un apoderado con vinculo verificado actua por el menor;
el menor no reserva, cancela ni reprograma por su cuenta, entra a la sala solo
en clases pagadas por su apoderado y cada cambio se avisa por correo a todos
sus apoderados verificados.
"""

from datetime import time as hora
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.exceptions import InscripcionError
from alumnos.models import Asignatura, Clase, Genero, Inscripcion
from alumnos.services import MENSAJE_MENOR, InscripcionService
from apoderados.forms import VERSION_DECLARACION_VINCULO
from apoderados.models import Apoderado, CompraApoderado, Vinculo
from tests.test_apoderados import RUT, crear_apoderado, entrar
from tests.test_apoderados_vinculos import RUT_HERMANA, crear_menor_vinculado
from tests.test_especialidad import crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import dar_paquete
from tests.test_progreso_alumno import crear_alumno


class ReservasDelApoderadoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.profesor = crear_profesor('44444444-4', 'profe@demo.cl', None)
        cls.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                         modalidad='online', horario=hora(10, 0), profesor=cls.profesor)
        cls.sesion, cls.otra_sesion = crear_sesion(cls.clase, dias=2), crear_sesion(cls.clase, dias=3)
        cls.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        cls.vinculo = crear_menor_vinculado(cls.madre)
        cls.menor = cls.vinculo.alumno
        cls.padre = crear_apoderado('55555555-5', Apoderado.VERIFICADO)
        Vinculo.objects.create(apoderado=cls.padre, alumno=cls.menor, parentesco='padre', estado=Vinculo.VERIFICADO,
                               version_declaracion=VERSION_DECLARACION_VINCULO, declaracion_aceptada=timezone.now())
        cls.paquete = dar_paquete(cls.menor, cls.profesor)
        CompraApoderado.objects.create(paquete=cls.paquete, apoderado=cls.madre, vinculo=cls.vinculo)

    def setUp(self):
        entrar(self.client, self.madre.user, apoderado_id=self.madre.id_apoderado)

    def url(self, nombre, *args, vinculo=None):
        return reverse(nombre, args=[(vinculo or self.vinculo).pk, *args])

    def reservar(self, sesion=None, vinculo=None):
        return self.client.post(self.url('apoderado_reservar_clase', vinculo=vinculo),
                                {'id_sesion': (sesion or self.sesion).pk})

    def reserva(self):
        return Inscripcion.objects.get(alumno=self.menor)

    def test_reserva_y_avisa_por_separado_a_cada_apoderado(self):
        self.assertRedirects(self.reservar(), self.url('apoderado_clases_estudiante'))
        reserva = self.reserva()
        self.assertEqual((reserva.sesion, reserva.paquete, reserva.estado),
                         (self.sesion, self.paquete, Inscripcion.ESTADO_CONFIRMADA))
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([self.madre.user.email, self.padre.user.email]))
        self.assertTrue(all(len(m.to) == 1 for m in mail.outbox))  # nadie ve el correo del otro
        self.assertIn('reservó una clase para', mail.outbox[0].body)
        self.assertIn('Álgebra', mail.outbox[0].body)

    def test_reprograma_y_cancela(self):
        self.reservar()
        self.client.post(self.url('apoderado_reprogramar_clase', self.reserva().pk), {'id_sesion': self.otra_sesion.pk})
        self.assertEqual(self.reserva().sesion, self.otra_sesion)
        self.client.post(self.url('apoderado_cancelar_clase', self.reserva().pk))
        self.assertEqual(self.reserva().estado, Inscripcion.ESTADO_CANCELADA)
        self.assertEqual(len(mail.outbox), 6)  # 3 cambios x 2 apoderados

    def test_la_pantalla_muestra_paquete_sesiones_y_reservas(self):
        respuesta = self.client.get(self.url('apoderado_clases_estudiante'))
        self.assertContains(respuesta, 'Paquetes vigentes')
        self.assertContains(respuesta, f'value="{self.sesion.pk}"')
        self.reservar()
        respuesta = self.client.get(self.url('apoderado_clases_estudiante'))
        self.assertContains(respuesta, self.url('apoderado_cancelar_clase', self.reserva().pk))

    def test_el_menor_no_reserva_cancela_ni_reprograma_por_su_cuenta(self):
        self.reservar()
        reserva = self.reserva()
        entrar(self.client, self.menor.user, alumno_id=self.menor.id_alumno)
        respuesta = self.client.post(reverse('reservar_sesion'), {'id_sesion': self.otra_sesion.pk}).json()
        self.assertEqual(respuesta, {'success': False, 'message': MENSAJE_MENOR})
        self.client.post(reverse('reprogramar_inscripcion', args=[reserva.pk]), {'id_sesion': self.otra_sesion.pk})
        self.client.post(reverse('cancelar_inscripcion', args=[reserva.pk]))
        reserva.refresh_from_db()
        self.assertEqual((reserva.sesion, reserva.estado), (self.sesion, Inscripcion.ESTADO_CONFIRMADA))
        self.assertNotContains(self.client.get(reverse('alumno_pag1')), reverse('cancelar_inscripcion', args=[reserva.pk]))

    def test_solo_con_un_vinculo_que_autoriza(self):
        ajeno = crear_menor_vinculado(crear_apoderado('66666666-6', Apoderado.VERIFICADO), rut=RUT_HERMANA)
        self.assertEqual(self.reservar(vinculo=ajeno).status_code, 404)
        self.assertEqual(self.client.get(self.url('apoderado_clases_estudiante', vinculo=ajeno)).status_code, 404)
        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.PENDIENTE)
        self.assertEqual(self.reservar().status_code, 404)
        self.assertFalse(Inscripcion.objects.exists())

    def test_el_servicio_rechaza_un_vinculo_de_otro_estudiante(self):
        ajeno = crear_menor_vinculado(self.madre, rut=RUT_HERMANA)
        with self.assertRaisesMessage(InscripcionError, MENSAJE_MENOR):
            InscripcionService.inscribir_alumno_en_sesion(self.menor, self.sesion.pk, vinculo=ajeno)

    def test_no_toca_reservas_de_otros_alumnos(self):
        adulta = crear_alumno('33333333-3', 'Ana', Genero.objects.create(descripcion='Otro'))
        ajena = Inscripcion.objects.create(alumno=adulta, clase=self.clase, sesion=self.sesion,
                                           paquete=dar_paquete(adulta, self.profesor))
        self.client.post(self.url('apoderado_cancelar_clase', ajena.pk))
        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, Inscripcion.ESTADO_CONFIRMADA)

    def test_si_falla_el_correo_la_reserva_queda(self):
        with mock.patch('alumnos.correo.send_mail', side_effect=OSError('sin servidor')):
            self.reservar()
        self.assertEqual(self.reserva().estado, Inscripcion.ESTADO_CONFIRMADA)

    def test_sala_virtual_solo_en_clases_pagadas_por_un_apoderado_vigente(self):
        self.reservar()
        sala = reverse('sala_virtual', args=[self.clase.id_clase])
        entrar(self.client, self.menor.user, alumno_id=self.menor.id_alumno)
        self.assertEqual(self.client.get(sala).status_code, 200)

        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.RECHAZADO)  # revocado (1d)
        self.assertEqual(self.client.get(sala).status_code, 403)

        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.VERIFICADO)
        Apoderado.objects.filter(pk=self.madre.pk).update(estado=Apoderado.RECHAZADO)  # quien pago
        self.assertEqual(self.client.get(sala).status_code, 403)

        Apoderado.objects.filter(pk=self.madre.pk).update(estado=Apoderado.VERIFICADO)
        CompraApoderado.objects.all().delete()  # paquete que no pago un apoderado
        self.assertEqual(self.client.get(sala).status_code, 403)
