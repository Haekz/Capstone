"""SCRUM-29: "Mis clases" del portal muestra cuando es cada sesion reservada.

Proximas = inscripciones activas cuya sesion aun no termina (o a la clase sin
sesion puntual), en orden de fecha. Las sesiones ya realizadas van al historial.
"""

from datetime import time

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Asignatura, Clase, Genero, Inscripcion, SesionClase
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_progreso_alumno import crear_alumno

RUT_ANA = '11111111-1'


def dia(sesion):
    return timezone.localtime(sesion.fecha_hora_inicio).strftime('%d/%m/%Y')


class MisClasesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.ana = crear_alumno(RUT_ANA, 'Ana', Genero.objects.create(descripcion='Otro'))
        profesor = crear_profesor('20000000-1', 'profe@lbwus.cl', None)
        cls.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                         modalidad='online', horario=time(10, 0), profesor=profesor)

        def inscribir(sesion, estado=Inscripcion.ESTADO_CONFIRMADA):
            return Inscripcion.objects.create(alumno=cls.ana, clase=cls.clase,
                                              sesion=sesion, estado=estado)

        cls.lejana = inscribir(crear_sesion(cls.clase, dias=9))
        cls.cercana = inscribir(crear_sesion(cls.clase, dias=2))
        cls.pendiente = inscribir(crear_sesion(cls.clase, dias=4), Inscripcion.ESTADO_PENDIENTE)
        cls.cancelada = inscribir(crear_sesion(cls.clase, dias=6, estado=SesionClase.ESTADO_CANCELADA))
        cls.sin_sesion = Inscripcion.objects.create(alumno=cls.ana, clase=cls.clase)
        cls.realizada = inscribir(crear_sesion(cls.clase, dias=-3))
        # No aparecen en ningun lado: cancelada por la alumna y pendiente que ya paso.
        inscribir(crear_sesion(cls.clase, dias=3), Inscripcion.ESTADO_CANCELADA)
        inscribir(crear_sesion(cls.clase, dias=-1), Inscripcion.ESTADO_PENDIENTE)

    def _portal(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        return self.client.get(reverse('alumno_pag1'))

    def test_proximas_excluye_realizadas_y_canceladas_por_la_alumna(self):
        self.assertEqual(
            set(Inscripcion.objects.filter(alumno=self.ana).proximas()),
            {self.lejana, self.cercana, self.pendiente, self.cancelada, self.sin_sesion},
        )

    def test_mis_clases_en_orden_de_fecha_y_sin_sesion_al_final(self):
        r = self._portal()
        self.assertEqual(list(r.context['mis_inscripciones']),
                         [self.cercana, self.pendiente, self.cancelada, self.lejana, self.sin_sesion])
        self.assertEqual(list(r.context['historial_clases']), [self.realizada])

    def test_tarjeta_muestra_dia_y_hora_de_la_sesion(self):
        r = self._portal()
        sesion = self.cercana.sesion
        horas = '{} - {} hrs'.format(*(timezone.localtime(h).strftime('%H:%M')
                                       for h in (sesion.fecha_hora_inicio, sesion.fecha_hora_fin)))
        self.assertContains(r, f'Sesión: {dia(sesion)}')
        self.assertContains(r, horas)
        # La inscripcion a la clase completa sigue mostrando el horario general.
        self.assertContains(r, 'Horario: 10:00 hrs')

    def test_estados_pendiente_y_sesion_cancelada_sin_boton_de_unirse(self):
        r = self._portal()
        self.assertContains(r, '>Pendiente</span>')
        self.assertContains(r, '>Sesión cancelada</span>')
        # Solo las confirmadas de sesion no cancelada (cercana, lejana, sin sesion) muestran
        # "Unirse": la pendiente aun no esta confirmada (ver test_sala_virtual_acceso).
        self.assertContains(r, 'Unirse a la Clase', count=3)

    def test_historial_muestra_las_sesiones_realizadas(self):
        r = self._portal()
        self.assertContains(r, 'Historial de Clases Completadas')
        self.assertContains(r, '>Completada</span>')
        self.assertContains(r, f'Sesión: {dia(self.realizada.sesion)}')

    def test_historial_vacio_lo_explica(self):
        Inscripcion.objects.filter(pk=self.realizada.pk).delete()
        self.assertContains(self._portal(), 'Todavía no tienes clases completadas.')
