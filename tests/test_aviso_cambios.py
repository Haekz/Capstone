"""Avisos de cancelacion y cambio de horario (21-nov, etapa 4). Datos ficticios.

Cuando actua un apoderado, avisan todos los apoderados verificados del menor. Cuando actua el alumno adulto, se le
confirma a el (sobre todo el costo si faltaban menos de 4 h). Antes salia un correo de texto («Clases de Ana») solo
al apoderado y sin campanita; ahora es el mismo diseño que la reserva. El profesor ya recibia los suyos.
"""

import re

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.exceptions import InscripcionError
from alumnos.models import Asignatura, Clase
from alumnos.services import InscripcionService
from apoderados.forms import VERSION_DECLARACION_VINCULO
from apoderados.models import Apoderado, CompraApoderado, Vinculo
from notificaciones.models import Notificacion
from tests.test_apoderados import RUT, crear_apoderado
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_cancelar_4_horas import EN_2_HORAS
from tests.test_especialidad import crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import Escenario, dar_paquete


class AvisosDeCambiosDelApoderadoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.profesor = crear_profesor('44444444-4', 'profe@demo.cl', None)
        cls.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                         modalidad='online', profesor=cls.profesor)
        cls.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        cls.vinculo_madre = crear_menor_vinculado(cls.madre)
        cls.menor = cls.vinculo_madre.alumno
        cls.padre = crear_apoderado('55555555-5', Apoderado.VERIFICADO)
        cls.vinculo_padre = Vinculo.objects.create(
            apoderado=cls.padre, alumno=cls.menor, parentesco='padre', estado=Vinculo.VERIFICADO,
            version_declaracion=VERSION_DECLARACION_VINCULO, declaracion_aceptada=timezone.now())
        paquete = dar_paquete(cls.menor, cls.profesor)
        CompraApoderado.objects.create(paquete=paquete, apoderado=cls.madre, vinculo=cls.vinculo_madre)

    def reservar(self, dias=3):
        """Reserva sin ejecutar los avisos de reserva (on_commit no corre en TestCase): el buzon queda limpio."""
        return InscripcionService.inscribir_alumno_en_sesion(
            self.menor, crear_sesion(self.clase, dias=dias).pk, vinculo=self.vinculo_madre)

    def cancelar(self, inscripcion):
        with self.captureOnCommitCallbacks(execute=True):
            return InscripcionService.cancelar_inscripcion(self.menor, inscripcion.pk, vinculo=self.vinculo_madre)

    def reagendar(self, inscripcion, dias=4):
        nueva = crear_sesion(self.clase, dias=dias)
        with self.captureOnCommitCallbacks(execute=True):
            return InscripcionService.reprogramar_inscripcion(self.menor, inscripcion.pk, nueva.pk,
                                                              vinculo=self.vinculo_madre)

    def correos_a_apoderados(self):
        return [m for m in mail.outbox if m.to[0] in (self.madre.user.email, self.padre.user.email)]

    def test_cancelar_avisa_a_cada_apoderado_con_campanita_y_correo_con_diseno(self):
        inscripcion = self.reservar()
        self.cancelar(inscripcion)
        correos = self.correos_a_apoderados()
        self.assertEqual(sorted(m.to[0] for m in correos), sorted([self.madre.user.email, self.padre.user.email]))
        for apoderado, vinculo in ((self.madre, self.vinculo_madre), (self.padre, self.vinculo_padre)):
            [correo] = [m for m in correos if m.to == [apoderado.user.email]]
            [aviso] = Notificacion.objects.filter(usuario=apoderado.user)
            with self.subTest(apoderado=apoderado.user.email):
                self.assertEqual(correo.subject, 'Clase cancelada - LBWUS')
                self.assertIn('(Álgebra)', correo.body)
                self.assertIn('fue cancelada.', correo.body)
                self.assertIn(f'La canceló {self.madre.nombre}.', correo.body)  # el otro apoderado sabe quién fue
                self.assertNotIn('se descontó', correo.body)  # faltaban 3 dias: no cuesta
                self.assertTrue(correo.alternatives)  # y trae el diseño
                self.assertEqual(aviso.enlace, reverse('apoderado_clases_estudiante', args=[vinculo.pk]))
        self.assertFalse(Notificacion.objects.filter(usuario=self.menor.user).exists())
        self.assertNotIn(self.menor.user.email, [d for m in mail.outbox for d in m.to])

    def test_cancelar_con_menos_de_4_horas_dice_que_la_clase_se_descuenta(self):
        self.cancelar(self.reservar(dias=EN_2_HORAS))
        for correo in self.correos_a_apoderados():
            self.assertIn('Faltaban menos de 4 horas: la clase se descontó del paquete.', correo.body)

    def test_reagendar_dice_de_cuando_a_cuando_y_lleva_a_la_pagina_de_la_clase(self):
        inscripcion = self.reservar()
        self.reagendar(inscripcion)
        ruta = reverse('detalle_clase', args=[inscripcion.pk])
        correos = self.correos_a_apoderados()
        self.assertEqual(len(correos), 2)
        for correo in correos:
            self.assertEqual(correo.subject, 'Clase reagendada - LBWUS')
            self.assertRegex(correo.body, r'pasó del \d\d/\d\d/\d{4} a las \d\d:\d\d al \d\d/\d\d/\d{4} a las \d\d:\d\d\.')
            self.assertIn(f'La movió {self.madre.nombre}.', correo.body)
            self.assertRegex(correo.alternatives[0][0], rf'href="[^"]*{re.escape(ruta)}"')
        self.assertEqual({a.enlace for a in Notificacion.objects.filter(usuario__in=[self.madre.user, self.padre.user])},
                         {ruta})

    def test_ya_no_sale_el_correo_de_texto_viejo(self):
        inscripcion = self.reservar()
        self.reagendar(inscripcion)
        self.cancelar(inscripcion)
        for correo in self.correos_a_apoderados():
            self.assertFalse(correo.subject.startswith('Clases de'), correo.subject)
            self.assertTrue(correo.alternatives, correo.subject)  # todos con diseño
        self.assertEqual(len(self.correos_a_apoderados()), 4)  # 2 cambios x 2 apoderados

    def test_nadie_recibe_rut_correo_ni_telefono_del_profesional(self):
        inscripcion = self.reservar()
        self.reagendar(inscripcion)
        self.cancelar(inscripcion)
        for dato in (self.profesor.user.rut, self.profesor.user.email, self.profesor.user.telefono):
            self.assertTrue(dato)  # existe: si estuviera vacio la prueba no probaria nada
            for correo in self.correos_a_apoderados():
                with self.subTest(dato=dato, asunto=correo.subject):
                    self.assertNotIn(dato, correo.body)
                    self.assertNotIn(dato, correo.alternatives[0][0])

    def test_si_la_cancelacion_falla_no_sale_ningun_aviso_mas(self):
        inscripcion = self.reservar()
        self.cancelar(inscripcion)
        avisos = len(mail.outbox)
        with self.assertRaises(InscripcionError):  # ya esta cancelada
            self.cancelar(inscripcion)
        self.assertEqual(len(mail.outbox), avisos)


class AvisosDeCambiosDelAlumnoTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)

    def correos_a(self, user):
        return [m for m in mail.outbox if m.to == [user.email]]

    def reservar(self, dias=3):
        return InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=dias).pk)

    def cancelar(self, inscripcion):
        with self.captureOnCommitCallbacks(execute=True):
            InscripcionService.cancelar_inscripcion(self.ana, inscripcion.pk)

    def test_al_reagendar_el_alumno_adulto_recibe_la_confirmacion_y_el_profesor_el_aviso(self):
        inscripcion = self.reservar()
        nueva = crear_sesion(self.clase, dias=4)
        with self.captureOnCommitCallbacks(execute=True):
            InscripcionService.reprogramar_inscripcion(self.ana, inscripcion.pk, nueva.pk)
        ruta = reverse('detalle_clase', args=[inscripcion.pk])
        [correo] = self.correos_a(self.ana.user)
        [aviso] = Notificacion.objects.filter(usuario=self.ana.user)
        self.assertEqual(correo.subject, 'Clase reagendada - LBWUS')
        self.assertRegex(aviso.texto, r'^Tu clase \(Algebra\) con Profe pasó del .+ al .+\.$')
        self.assertNotIn('La movió', aviso.texto)  # lo hizo el mismo: no hace falta decirlo
        self.assertEqual(aviso.enlace, ruta)
        self.assertIn(ruta, correo.alternatives[0][0])
        [del_profesor] = self.correos_a(self.profe.user)  # y el profesor sigue recibiendo el suyo
        self.assertEqual(del_profesor.subject, 'Clase reagendada - LBWUS')
        self.assertIn(ruta, del_profesor.alternatives[0][0])

    def test_al_cancelar_el_alumno_adulto_recibe_la_confirmacion_sin_costo_si_faltaban_4_horas_o_mas(self):
        inscripcion = self.reservar()
        self.cancelar(inscripcion)
        [correo] = self.correos_a(self.ana.user)
        [aviso] = Notificacion.objects.filter(usuario=self.ana.user)
        self.assertEqual(correo.subject, 'Clase cancelada - LBWUS')
        self.assertRegex(aviso.texto, r'^Tu clase \(Algebra\) con Profe del .+ fue cancelada\.$')  # sin aviso de costo
        self.assertTrue(correo.alternatives)
        [del_profesor] = self.correos_a(self.profe.user)
        self.assertNotIn(reverse('detalle_clase', args=[inscripcion.pk]), del_profesor.alternatives[0][0])  # va a su agenda

    def test_cancelar_con_menos_de_4_horas_le_dice_al_alumno_que_la_clase_se_descuenta(self):
        self.cancelar(self.reservar(dias=EN_2_HORAS))
        [correo] = self.correos_a(self.ana.user)
        self.assertIn('Faltaban menos de 4 horas: la clase se descontó del paquete.', correo.body)
