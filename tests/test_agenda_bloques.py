"""Horario semanal y generacion de bloques (paso B1b, decidido 02-nov). Datos ficticios."""

from datetime import datetime, time, timedelta
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone

from agenda.bloques import generar, quitar_franja
from agenda.models import HorarioSemanal
from alumnos.models import Asignatura, Clase, SesionClase
from alumnos.services import InscripcionService
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import Escenario, dar_paquete

LUNES = 0
BLOQUES_LUNES_15_A_19 = 4 * 4  # 4 bloques por lunes, 4 semanas


def proximo_lunes():
    hoy = timezone.localdate()
    return timezone.make_aware(datetime.combine(hoy + timedelta(days=7 - hoy.weekday()), time(0, 0)))


class GenerarBloquesTests(Escenario):

    def setUp(self):
        self.ahora = proximo_lunes()
        self.franja = HorarioSemanal.objects.create(profesor=self.profe, dia_semana=LUNES,
                                                    hora_inicio=time(15), hora_fin=time(19))

    def sesiones(self):
        return SesionClase.objects.filter(clase__profesor=self.profe)

    def test_crea_bloques_de_60_min_y_1_alumno_por_4_semanas(self):
        self.assertEqual(generar(self.profe, self.ahora), BLOQUES_LUNES_15_A_19)
        for sesion in self.sesiones():
            inicio = sesion.inicio_local
            self.assertEqual((inicio.weekday(), sesion.duracion_minutos, sesion.cupo_maximo), (LUNES, 60, 1))
            self.assertIn(inicio.hour, (15, 16, 17, 18))

    def test_un_bloque_por_asignatura(self):
        Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Calculo'),
                             modalidad='online', horario=time(10), profesor=self.profe)
        self.assertEqual(generar(self.profe, self.ahora), 2 * BLOQUES_LUNES_15_A_19)

    def test_no_duplica_si_se_corre_de_nuevo(self):
        generar(self.profe, self.ahora)
        self.assertEqual(generar(self.profe, self.ahora), 0)

    def test_un_bloque_cancelado_no_vuelve(self):
        generar(self.profe, self.ahora)
        self.sesiones().filter(pk=self.sesiones().first().pk).update(estado=SesionClase.ESTADO_CANCELADA)
        self.assertEqual(generar(self.profe, self.ahora), 0)

    def test_profesor_sin_titulo_aprobado_no_recibe_bloques(self):
        HorarioSemanal.objects.create(profesor=self.sin_titulo, dia_semana=LUNES,
                                      hora_inicio=time(15), hora_fin=time(19))
        self.assertEqual(generar(self.sin_titulo, self.ahora), 0)

    def test_quitar_la_franja_borra_los_libres_y_deja_los_reservados(self):
        generar(self.profe, self.ahora)
        dar_paquete(self.ana, self.profe)
        reservada = self.sesiones().first()
        InscripcionService.inscribir_alumno_en_sesion(self.ana, reservada.pk)
        de_demo = crear_sesion(self.clase, dias=2)  # no salio de la agenda: no se toca
        quitar_franja(self.franja)
        self.assertEqual(set(self.sesiones()), {reservada, de_demo})
        self.assertFalse(HorarioSemanal.objects.exists())

    def test_el_comando_diario_genera_los_bloques(self):
        salida = StringIO()
        call_command('generar_bloques', stdout=salida)
        self.assertTrue(self.sesiones().exists())
        self.assertIn('Bloques nuevos:', salida.getvalue())


class FranjaValidaTests(Escenario):

    def franja(self, inicio, fin):
        return HorarioSemanal(profesor=self.profe, dia_semana=LUNES, hora_inicio=inicio, hora_fin=fin)

    def test_exige_horas_en_punto(self):
        with self.assertRaisesMessage(ValidationError, 'horas en punto'):
            self.franja(time(15, 30), time(19)).full_clean()

    def test_el_termino_va_despues_del_inicio(self):
        with self.assertRaisesMessage(ValidationError, 'posterior'):
            self.franja(time(19), time(15)).full_clean()

    def test_no_se_cruza_con_otra_del_mismo_dia(self):
        self.franja(time(15), time(19)).save()
        with self.assertRaisesMessage(ValidationError, 'se cruza'):
            self.franja(time(18), time(20)).full_clean()
