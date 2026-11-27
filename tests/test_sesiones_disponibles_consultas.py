"""Listar sesiones disponibles no hace una consulta por sesion (con 18.000 tardaba 18 s y hacia 8.970 consultas).

SesionClase.objects.disponibles() ya calcula los cupos ocupados; cupos_ocupados debe usar ese dato.
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from alumnos.models import Inscripcion, SesionClase
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, Escenario, dar_paquete


class SesionesDisponiblesTests(Escenario):

    def listar(self):
        with CaptureQueriesContext(connection) as consultas:
            datos = self.client.get(reverse('sesiones_disponibles')).json()['sesiones']
        return datos, len(consultas)

    def test_no_hace_una_consulta_por_sesion_y_los_cupos_siguen_bien(self):
        sesiones = [crear_sesion(self.clase, dias, cupo=3) for dias in range(1, 13)]
        Inscripcion.objects.create(alumno=self.beto, clase=self.clase, sesion=sesiones[0],
                                   paquete=dar_paquete(self.beto, self.profe))
        self.entrar(RUT_ANA)
        datos, consultas = self.listar()
        self.assertEqual(len(datos), 12)
        self.assertLess(consultas, 12)  # antes: al menos una por sesion
        cupos = {d['id_sesion']: d['cupos_disponibles'] for d in datos}
        self.assertEqual(cupos[sesiones[0].pk], 2)  # la que tiene una reserva
        self.assertEqual({cupos[s.pk] for s in sesiones[1:]}, {3})

    def test_sin_el_dato_anotado_sigue_contando_las_reservas(self):
        sesion = crear_sesion(self.clase, 2, cupo=3)
        Inscripcion.objects.create(alumno=self.beto, clase=self.clase, sesion=sesion,
                                   paquete=dar_paquete(self.beto, self.profe))
        self.assertEqual(SesionClase.objects.get(pk=sesion.pk).cupos_disponibles, 2)  # sin anotar
        self.assertEqual(SesionClase.objects.disponibles().get(pk=sesion.pk).cupos_disponibles, 2)  # anotada
