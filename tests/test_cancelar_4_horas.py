"""Regla de las 4 horas (paso A2, decidido 02-nov).

Con 4 h o mas, cancelar o reagendar es directo y la clase vuelve al paquete. Con
menos, cancelar se puede pero la clase se pierde y el profesor cobra; reagendar no.
Quien cancela tarde no asistio: no califica ni suma progreso. Datos ficticios.
"""

from django.urls import reverse

from alumnos import paquetes
from alumnos.models import Inscripcion
from alumnos.services import InscripcionError, InscripcionService
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, Escenario, dar_paquete
from user_profesor.views import calcular_saldos

EN_2_HORAS, EN_5_HORAS, EN_3_DIAS = 2 / 24, 5 / 24, 3


class ReglaDeLas4HorasTests(Escenario):

    def setUp(self):
        self.paquete = dar_paquete(self.ana, self.profe)

    def reservar(self, dias):
        return InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=dias).pk)

    def cancelar(self, inscripcion):
        InscripcionService.cancelar_inscripcion(self.ana, inscripcion.pk)
        inscripcion.refresh_from_db()
        self.paquete.refresh_from_db()

    def test_con_4_horas_o_mas_la_clase_vuelve_al_paquete(self):
        inscripcion = self.reservar(EN_5_HORAS)
        self.cancelar(inscripcion)
        self.assertEqual(inscripcion.estado, Inscripcion.ESTADO_CANCELADA)
        self.assertEqual(self.paquete.clases_usadas, 0)

    def test_con_menos_de_4_horas_la_clase_se_pierde(self):
        inscripcion = self.reservar(EN_2_HORAS)
        self.assertFalse(inscripcion.a_tiempo_para_cambiar)
        self.cancelar(inscripcion)
        self.assertEqual(inscripcion.estado, Inscripcion.ESTADO_CANCELADA_TARDE)
        self.assertEqual(self.paquete.clases_usadas, 1)

    def test_cancelar_tarde_libera_el_bloque(self):
        inscripcion = self.reservar(EN_2_HORAS)
        self.cancelar(inscripcion)
        self.assertEqual(inscripcion.sesion.cupos_ocupados, 0)

    def test_reagendar_exige_4_horas(self):
        inscripcion = self.reservar(EN_2_HORAS)
        otra = crear_sesion(self.clase, dias=EN_3_DIAS)
        self.assertFalse(inscripcion.puede_reprogramar)
        with self.assertRaisesMessage(InscripcionError, 'al menos 4 horas'):
            InscripcionService.reprogramar_inscripcion(self.ana, inscripcion.pk, otra.pk)

    def test_reagendar_con_4_horas_es_directo(self):
        inscripcion = self.reservar(EN_5_HORAS)
        otra = crear_sesion(self.clase, dias=EN_3_DIAS)
        self.assertTrue(inscripcion.puede_reprogramar)
        movida = InscripcionService.reprogramar_inscripcion(self.ana, inscripcion.pk, otra.pk)
        self.assertEqual((movida.sesion, movida.estado), (otra, Inscripcion.ESTADO_CONFIRMADA))

    def test_al_profesor_se_le_paga_la_cancelada_tarde_cuando_pasa_la_hora(self):
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, paquete=self.paquete,
                                   sesion=crear_sesion(self.clase, dias=-1),
                                   estado=Inscripcion.ESTADO_CANCELADA_TARDE)
        valor = paquetes.valor_clase(Inscripcion.objects.get())
        self.assertEqual(calcular_saldos(self.profe)['disponible'], paquetes.pago_profesor(valor))

    def test_antes_de_la_hora_aun_no_se_paga(self):
        self.cancelar(self.reservar(EN_2_HORAS))
        self.assertEqual(calcular_saldos(self.profe)['disponible'], 0)

    def test_quien_cancelo_tarde_no_cuenta_como_clase_hecha(self):
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, paquete=self.paquete,
                                   sesion=crear_sesion(self.clase, dias=-1),
                                   estado=Inscripcion.ESTADO_CANCELADA_TARDE)
        self.assertFalse(Inscripcion.objects.completadas().exists())  # ni resena ni progreso


class AvisoEnElPanelTests(Escenario):

    def test_con_menos_de_4_horas_avisa_antes_de_cancelar_y_no_ofrece_reagendar(self):
        dar_paquete(self.ana, self.profe)
        InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=EN_2_HORAS).pk)
        self.entrar(RUT_ANA)
        respuesta = self.client.get(reverse('alumno_pag1'))
        self.assertContains(respuesta, 'Faltan menos de 4 horas: si cancelas, pierdes esta clase')
        self.assertNotContains(respuesta, 'title="Reprogramar clase"')
