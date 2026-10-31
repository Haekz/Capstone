"""Sala virtual: solo entra una inscripcion confirmada de una sesion no cancelada.

'pendiente' solo la asigna un admin a mano y aun no esta confirmada; antes
mostraba "Unirse a la Clase" y la vista dejaba entrar con cualquier inscripcion,
incluso cancelada.
"""

from datetime import time

from django.test import TestCase
from django.urls import reverse

from alumnos.models import Asignatura, Clase, Genero, Inscripcion, SesionClase
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_progreso_alumno import crear_alumno

RUT_ANA = '11111111-1'
CONFIRMADA, PENDIENTE, CANCELADA = (Inscripcion.ESTADO_CONFIRMADA, Inscripcion.ESTADO_PENDIENTE,
                                    Inscripcion.ESTADO_CANCELADA)


class AccesoSalaVirtualTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.ana = crear_alumno(RUT_ANA, 'Ana', Genero.objects.create(descripcion='Otro'))
        profesor = crear_profesor('20000000-1', 'profe@lbwus.cl', None)
        cls.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                         modalidad='online', horario=time(10, 0), profesor=profesor)

    def inscribir(self, estado=CONFIRMADA, sesion_estado=SesionClase.ESTADO_PROGRAMADA, dias=2):
        sesion = crear_sesion(self.clase, dias=dias, estado=sesion_estado)
        return Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=sesion, estado=estado)

    def entrar(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        return self.client.get(reverse('sala_virtual', args=[self.clase.id_clase]))

    def test_regla_puede_unirse(self):
        casos = [
            ('confirmada', dict(estado=CONFIRMADA), True),
            ('pendiente', dict(estado=PENDIENTE), False),
            ('cancelada por la alumna', dict(estado=CANCELADA), False),
            ('sesion cancelada', dict(sesion_estado=SesionClase.ESTADO_CANCELADA), False),
        ]
        for i, (nombre, datos, esperado) in enumerate(casos):
            with self.subTest(nombre):
                self.assertIs(self.inscribir(dias=i + 1, **datos).puede_unirse, esperado)

    def test_confirmada_sin_sesion_puntual_puede_unirse(self):
        insc = Inscripcion.objects.create(alumno=self.ana, clase=self.clase, estado=CONFIRMADA)
        self.assertTrue(insc.puede_unirse)

    def test_confirmada_entra_a_la_sala(self):
        self.inscribir()
        self.assertEqual(self.entrar().status_code, 200)

    def test_sin_inscripcion_no_entra(self):
        self.assertEqual(self.entrar().status_code, 403)

    def test_pendiente_no_entra(self):
        self.inscribir(estado=PENDIENTE)
        self.assertEqual(self.entrar().status_code, 403)

    def test_cancelada_por_la_alumna_no_entra(self):
        self.inscribir(estado=CANCELADA)
        self.assertEqual(self.entrar().status_code, 403)

    def test_sesion_cancelada_no_entra(self):
        self.inscribir(sesion_estado=SesionClase.ESTADO_CANCELADA)
        self.assertEqual(self.entrar().status_code, 403)

    def test_basta_una_inscripcion_valida_de_la_clase(self):
        self.inscribir(sesion_estado=SesionClase.ESTADO_CANCELADA, dias=2)
        self.inscribir(estado=CONFIRMADA, dias=5)
        self.assertEqual(self.entrar().status_code, 200)
