"""Revision QA: reservas y saldo de paquetes (alumnos/services.py, InscripcionService).

Cubre las ramas de error que la suite no recorria: ids inexistentes o ajenos,
profesor sin titulo y la carrera que termina en IntegrityError. En todas el
riesgo es el mismo: que una reserva fallida gaste una clase del paquete o deje
una inscripcion a medias.
"""

from datetime import time
from unittest.mock import patch

from django.db import IntegrityError
from django.urls import reverse

from alumnos.exceptions import InscripcionDuplicadaError, InscripcionError, SesionNoDisponibleError
from alumnos.models import Clase, Inscripcion
from alumnos.services import InscripcionService
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import Escenario, dar_paquete

NO_EXISTE = 999999


def chocar(objetivo, *args):
    """Simula la carrera: la base rechaza la escritura por la restriccion unica."""
    return patch(objetivo, *args, side_effect=IntegrityError('duplicada'))


class Reserva(Escenario):

    def setUp(self):
        self.paquete = dar_paquete(self.ana, self.profe)
        self.sesion = crear_sesion(self.clase, dias=2)

    def saldo(self):
        self.paquete.refresh_from_db()
        return self.paquete.clases_disponibles

    def assertSinEfecto(self, saldo):
        self.assertEqual(self.saldo(), saldo)
        self.assertFalse(Inscripcion.objects.filter(alumno=self.ana).exists())


class ReservaEnSesionTests(Reserva):

    def test_sesion_inexistente_no_reserva(self):
        """Riesgo: un id manipulado produce un 500 o una inscripcion sin sesion."""
        with self.assertRaises(SesionNoDisponibleError):
            InscripcionService.inscribir_alumno_en_sesion(self.ana, NO_EXISTE)
        self.assertSinEfecto(4)

    def test_profesor_sin_titulo_no_recibe_reservas(self):
        """Riesgo: reservar (y cobrar) clases de un profesor sin titulo aprobado."""
        clase = Clase.objects.create(asignatura=self.clase.asignatura, modalidad='online',
                                     horario=time(9, 0), profesor=self.sin_titulo)
        dar_paquete(self.ana, self.sin_titulo)
        with self.assertRaises(SesionNoDisponibleError):
            InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(clase, dias=2).pk)
        self.assertFalse(Inscripcion.objects.exists())

    def test_la_carrera_que_termina_en_integrity_error_no_gasta_la_clase(self):
        """Riesgo: dos reservas simultaneas del mismo alumno; la que choca con la restriccion
        unica de la base debe deshacerse entera (atomic) y no consumir saldo."""
        with chocar('alumnos.services.Inscripcion.objects.create'), self.assertRaises(InscripcionDuplicadaError):
            InscripcionService.inscribir_alumno_en_sesion(self.ana, self.sesion.pk)
        self.assertSinEfecto(4)


class ReservaEnClaseGeneralTests(Reserva):

    def test_clase_inexistente_no_reserva(self):
        with self.assertRaises(SesionNoDisponibleError):
            InscripcionService.inscribir_alumno_en_clase(self.ana, NO_EXISTE)
        self.assertSinEfecto(4)

    def test_profesor_sin_titulo_no_recibe_reservas_generales(self):
        clase = Clase.objects.create(asignatura=self.clase.asignatura, modalidad='online',
                                     horario=time(9, 0), profesor=self.sin_titulo)
        with self.assertRaises(SesionNoDisponibleError):
            InscripcionService.inscribir_alumno_en_clase(self.ana, clase.pk)
        self.assertSinEfecto(4)

    def test_la_carrera_en_clase_general_no_gasta_la_clase(self):
        with chocar('alumnos.services.Inscripcion.objects.create'), self.assertRaises(InscripcionDuplicadaError):
            InscripcionService.inscribir_alumno_en_clase(self.ana, self.clase.pk)
        self.assertSinEfecto(4)


class CancelarYReprogramarAjenoTests(Reserva):

    def setUp(self):
        super().setUp()
        self.reserva = InscripcionService.inscribir_alumno_en_sesion(self.ana, self.sesion.pk)
        self.otra_sesion = crear_sesion(self.clase, dias=3)

    def assertReservaIntacta(self):
        self.reserva.refresh_from_db()
        self.assertEqual((self.reserva.estado, self.reserva.sesion_id),
                         (Inscripcion.ESTADO_CONFIRMADA, self.sesion.pk))
        self.assertEqual(self.saldo(), 3)

    def test_otro_alumno_no_cancela_la_reserva(self):
        """Riesgo: IDOR. Beto manda el id de la reserva de Ana."""
        with self.assertRaises(InscripcionError):
            InscripcionService.cancelar_inscripcion(self.beto, self.reserva.pk)
        self.assertReservaIntacta()

    def test_otro_alumno_no_reprograma_la_reserva(self):
        with self.assertRaises(InscripcionError):
            InscripcionService.reprogramar_inscripcion(self.beto, self.reserva.pk, self.otra_sesion.pk)
        self.assertReservaIntacta()

    def test_reprogramar_a_una_sesion_inexistente_no_toca_la_reserva(self):
        with self.assertRaises(SesionNoDisponibleError):
            InscripcionService.reprogramar_inscripcion(self.ana, self.reserva.pk, NO_EXISTE)
        self.assertReservaIntacta()

    def test_la_carrera_al_reprogramar_deja_la_reserva_donde_estaba(self):
        """Riesgo: el save choca con la restriccion unica y la reserva queda movida a medias."""
        with chocar('alumnos.models.Inscripcion.save'), self.assertRaises(InscripcionDuplicadaError):
            InscripcionService.reprogramar_inscripcion(self.ana, self.reserva.pk, self.otra_sesion.pk)
        self.assertReservaIntacta()


class CancelarVistaAjenaTests(Reserva):

    def test_la_vista_no_cancela_la_reserva_de_otro_alumno(self):
        """Riesgo: IDOR en /alumnos/cancelar_inscripcion/<pk>/ (la vista filtra por el alumno de la sesion)."""
        reserva = InscripcionService.inscribir_alumno_en_sesion(self.ana, self.sesion.pk)
        self.entrar('22222222-2')  # Beto
        r = self.client.post(reverse('cancelar_inscripcion', args=[reserva.pk]))
        self.assertEqual(r.status_code, 404)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Inscripcion.ESTADO_CONFIRMADA)
