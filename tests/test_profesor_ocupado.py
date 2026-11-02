"""El profesor no puede estar en dos clases a la vez (paso B1a, decidido 02-nov).

Con varias asignaturas hay un bloque por asignatura a la misma hora: al reservar
uno, los demas que se cruzan dejan de ofrecerse. Datos ficticios.
"""

from datetime import time

from alumnos.exceptions import SesionNoDisponibleError
from alumnos.models import Asignatura, Clase, SesionClase
from alumnos.services import InscripcionService
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import Escenario, dar_paquete

EN_3_DIAS, MEDIA_HORA = 3, 0.5 / 24
OCUPADO = 'ya tiene una clase a esa hora'


class ProfesorOcupadoTests(Escenario):

    def setUp(self):
        self.calculo = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Calculo'),
                                            modalidad='online', horario=time(10, 0), profesor=self.profe)
        self.algebra_15 = crear_sesion(self.clase, dias=EN_3_DIAS, cupo=1)
        self.calculo_15 = crear_sesion(self.calculo, dias=EN_3_DIAS, cupo=1)
        dar_paquete(self.ana, self.profe)
        dar_paquete(self.beto, self.profe)

    def disponibles(self):
        return set(SesionClase.objects.disponibles())

    def test_no_se_puede_reservar_otra_asignatura_a_la_misma_hora(self):
        InscripcionService.inscribir_alumno_en_sesion(self.ana, self.algebra_15.pk)
        with self.assertRaisesMessage(SesionNoDisponibleError, OCUPADO):
            InscripcionService.inscribir_alumno_en_sesion(self.beto, self.calculo_15.pk)

    def test_el_bloque_que_se_cruza_deja_de_ofrecerse(self):
        self.assertIn(self.calculo_15, self.disponibles())
        InscripcionService.inscribir_alumno_en_sesion(self.ana, self.algebra_15.pk)
        self.assertNotIn(self.calculo_15, self.disponibles())

    def test_al_cancelar_vuelve_a_ofrecerse(self):
        inscripcion = InscripcionService.inscribir_alumno_en_sesion(self.ana, self.algebra_15.pk)
        InscripcionService.cancelar_inscripcion(self.ana, inscripcion.pk)
        self.assertIn(self.calculo_15, self.disponibles())

    def test_la_clase_grupal_sigue_admitiendo_alumnos(self):
        grupal = crear_sesion(self.clase, dias=EN_3_DIAS + 1, cupo=5)
        InscripcionService.inscribir_alumno_en_sesion(self.ana, grupal.pk)
        self.assertIn(grupal, self.disponibles())
        InscripcionService.inscribir_alumno_en_sesion(self.beto, grupal.pk)

    def test_no_se_puede_reagendar_a_una_hora_ocupada(self):
        InscripcionService.inscribir_alumno_en_sesion(self.ana, self.algebra_15.pk)
        de_beto = InscripcionService.inscribir_alumno_en_sesion(self.beto, crear_sesion(self.clase, dias=5).pk)
        with self.assertRaisesMessage(SesionNoDisponibleError, OCUPADO):
            InscripcionService.reprogramar_inscripcion(self.beto, de_beto.pk, self.calculo_15.pk)

    def test_reagendar_media_hora_no_choca_con_su_propia_reserva(self):
        propia = InscripcionService.inscribir_alumno_en_sesion(self.ana, self.algebra_15.pk)
        media_hora_despues = crear_sesion(self.clase, dias=EN_3_DIAS + MEDIA_HORA, cupo=1)
        movida = InscripcionService.reprogramar_inscripcion(self.ana, propia.pk, media_hora_despues.pk)
        self.assertEqual(movida.sesion, media_hora_despues)

    def test_otro_profesor_a_la_misma_hora_no_se_ve_afectado(self):
        del_otro = crear_sesion(self.clase_otro, dias=EN_3_DIAS, cupo=1)
        InscripcionService.inscribir_alumno_en_sesion(self.ana, self.algebra_15.pk)
        self.assertIn(del_otro, self.disponibles())
