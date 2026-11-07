"""Inicio del panel del profesor con datos reales de HOY (antes: primeras 6 materias y un 8 fijo).

La hora se fija a las 12:00 de Chile: "hoy" no depende de cuando se corran las pruebas. Datos ficticios.
"""

from datetime import datetime, time, timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos import paquetes
from alumnos.models import Asignatura, Clase, Genero, Inscripcion, SesionClase
from alumnos.utils import formato_clp
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_progreso_alumno import crear_alumno
from user_profesor import inicio

HOY = timezone.localdate()
MEDIODIA = timezone.make_aware(datetime.combine(HOY, time(12)))


def a_las(hora, dias=0):
    return timezone.make_aware(datetime.combine(HOY + timedelta(days=dias), time(hora)))


@mock.patch('django.utils.timezone.now', lambda: MEDIODIA)
class InicioProfesorTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        cls.ana = crear_alumno('11111111-1', 'Ana', genero)
        cls.luis = crear_alumno('12222222-2', 'Luis', genero)
        cls.profesor = crear_profesor('20000000-1', 'profe@lbwus.cl', None)
        cls.algebra = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                           modalidad='online', profesor=cls.profesor)
        cls.calculo = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Cálculo'),
                                           modalidad='presencial', profesor=cls.profesor)

    def sesion(self, clase, hora, dias=0, alumno=None, estado=Inscripcion.ESTADO_CONFIRMADA):
        inicio_ = a_las(hora, dias)
        sesion = SesionClase(clase=clase, fecha_hora_inicio=inicio_,
                             fecha_hora_fin=inicio_ + timedelta(hours=1), cupo_maximo=1)
        sesion.save(skip_clean=inicio_ <= MEDIODIA)  # clean() exige fecha futura al crear (como crear_sesion)
        if alumno:
            return Inscripcion.objects.create(alumno=alumno, clase=clase, sesion=sesion, estado=estado)
        return sesion

    def test_clases_de_hoy_son_las_reservadas_para_hoy_en_orden_de_hora(self):
        self.sesion(self.calculo, 15, alumno=self.luis)
        self.sesion(self.algebra, 9, alumno=self.ana)
        self.sesion(self.algebra, 17, alumno=self.ana, estado=Inscripcion.ESTADO_CANCELADA)  # la cancelo
        self.sesion(self.algebra, 10, dias=-1, alumno=self.ana)  # ayer
        self.sesion(self.algebra, 10, dias=1, alumno=self.luis)  # manana
        clases = inicio.contexto(self.profesor)['clases_hoy']
        self.assertEqual([(c['inicio'], c['nombre_curso'], c['alumno'], c['modalidad']) for c in clases],
                         [(a_las(9), 'Álgebra', 'Ana', 'Online'), (a_las(15), 'Cálculo', 'Luis', 'Presencial')])

    def test_dinero_de_hoy_es_lo_ya_dictado_hoy_como_en_su_saldo(self):
        dictada = self.sesion(self.algebra, 9, alumno=self.ana)
        self.sesion(self.calculo, 15, alumno=self.luis)  # todavia no se dicta
        self.sesion(self.algebra, 10, dias=-1, alumno=self.ana)  # ayer: no es de hoy
        esperado = paquetes.pago_profesor(paquetes.valor_clase(dictada))
        self.assertEqual(inicio.contexto(self.profesor)['dinero_hoy'], formato_clp(esperado))

    def test_disponibles_son_los_bloques_libres_que_quedan_hoy(self):
        self.sesion(self.algebra, 8)  # ya paso
        self.sesion(self.calculo, 15, alumno=self.luis)
        self.sesion(self.algebra, 15)  # misma hora que una reservada: el profesor esta ocupado
        self.sesion(self.algebra, 18)
        self.sesion(self.calculo, 18)  # misma hora, otra materia: es un solo bloque
        self.sesion(self.algebra, 19)
        self.sesion(self.algebra, 10, dias=1)  # manana
        self.assertEqual(inicio.contexto(self.profesor)['clases_disponibles'], 2)  # 18:00 y 19:00

    def test_sin_nada_hoy_todo_en_cero(self):
        self.assertEqual(inicio.contexto(self.profesor),
                         {'clases_hoy': [], 'dinero_hoy': formato_clp(0), 'clases_disponibles': 0})

    def test_el_panel_muestra_la_hora_real_y_sin_tope_de_6(self):
        self.sesion(self.algebra, 9, alumno=self.ana)
        self.client.post(reverse('login'), {'username': '20000000-1', 'password': CLAVE})
        html = self.client.get(reverse('panel_profesor')).content.decode()
        self.assertIn('09:00 – 10:00', html)
        self.assertNotIn('Max. 6', html)
