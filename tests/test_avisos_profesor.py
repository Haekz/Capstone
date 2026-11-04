"""Avisos al profesor: reserva, cancelacion y reagenda (paso B2b, decidido 02-nov).

Correo + campanita, solo despues de guardar (on_commit) y solo con el nombre
de pila del alumno. Datos ficticios.
"""

from django.core import mail

from alumnos.exceptions import SinClasesDisponiblesError
from alumnos.services import InscripcionService
from notificaciones.models import Notificacion
from tests.test_cancelar_4_horas import EN_2_HORAS, EN_3_DIAS, EN_5_HORAS
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, Escenario, dar_paquete


class AvisosAlProfesorTests(Escenario):

    def reservar(self, dias=EN_5_HORAS):
        with self.captureOnCommitCallbacks(execute=True):
            return InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=dias).pk)

    def avisos(self):
        return list(Notificacion.objects.filter(usuario=self.profe.user).values_list('texto', flat=True))

    def test_reserva_avisa_por_campanita_y_correo(self):
        dar_paquete(self.ana, self.profe)
        self.reservar()
        [texto] = self.avisos()
        self.assertIn('Ana reservó Algebra para el', texto)
        [correo] = mail.outbox
        self.assertEqual((correo.subject, correo.to), ('Nueva reserva - LBWUS', ['profe@lbwus.cl']))
        self.assertIn(texto, correo.body)

    def test_cancelacion_tardia_le_dice_que_se_le_paga(self):
        dar_paquete(self.ana, self.profe)
        inscripcion = self.reservar(EN_2_HORAS)
        with self.captureOnCommitCallbacks(execute=True):
            InscripcionService.cancelar_inscripcion(self.ana, inscripcion.pk)
        self.assertIn('Ana canceló Algebra del', self.avisos()[0])
        self.assertIn('se te paga igual', self.avisos()[0])

    def test_cancelacion_a_tiempo_no_menciona_pago(self):
        dar_paquete(self.ana, self.profe)
        inscripcion = self.reservar()
        with self.captureOnCommitCallbacks(execute=True):
            InscripcionService.cancelar_inscripcion(self.ana, inscripcion.pk)
        self.assertNotIn('se te paga', self.avisos()[0])

    def test_reagenda_dice_de_cuando_a_cuando(self):
        dar_paquete(self.ana, self.profe)
        inscripcion = self.reservar()
        otra = crear_sesion(self.clase, dias=EN_3_DIAS)
        with self.captureOnCommitCallbacks(execute=True):
            InscripcionService.reprogramar_inscripcion(self.ana, inscripcion.pk, otra.pk)
        self.assertRegex(self.avisos()[0], r'^Ana movió Algebra del .+ al .+\.$')

    def test_si_la_reserva_falla_no_sale_ningun_aviso(self):
        with self.assertRaises(SinClasesDisponiblesError):  # sin paquete
            self.reservar()
        self.assertEqual((self.avisos(), mail.outbox), ([], []))

    def test_el_aviso_no_lleva_datos_personales_del_alumno(self):
        dar_paquete(self.ana, self.profe)
        self.reservar()
        texto, cuerpo = self.avisos()[0], mail.outbox[0].body
        for privado in filter(None, (RUT_ANA, self.ana.user.email, self.ana.user.last_name)):
            self.assertNotIn(privado, texto)
            self.assertNotIn(privado, cuerpo)
