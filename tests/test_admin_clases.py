"""El admin ve las clases de los profesores, pero ya no las crea ni las elimina (fase 3, paso 3).

Las crea soporte al aprobar un titulo o una especializacion (test_asignar_asignaturas). Datos ficticios.
"""

from django.test import TestCase
from django.urls import reverse

from alumnos.models import Asignatura, Clase
from tests.test_especialidad import crear_profesor
from tests.test_retiros import crear_admin, entrar_admin


class ClasesDelAdminTests(TestCase):

    def setUp(self):
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)

    def test_ve_las_clases_sin_crear_ni_eliminar(self):
        profesor = crear_profesor('20000000-1', 'profe@lbwus.cl', None)
        Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Trigonometría'),
                             modalidad='online', profesor=profesor)
        html = self.client.get(reverse('dashboard_admin')).content.decode()
        self.assertIn('Trigonometría', html)
        self.assertIn('Clases de los profesores', html)
        for control in ('Nueva Clase', 'form-crear-clase', 'crear_clase', 'eliminar_clase', 'Eliminar Clase'):
            self.assertNotIn(control, html)

    def test_sin_clases_explica_de_donde_salen(self):
        html = self.client.get(reverse('dashboard_admin')).content.decode()
        self.assertIn('Aparecen cuando soporte aprueba el título o una especialización', html)
        self.assertNotIn('Crear la primera clase', html)
