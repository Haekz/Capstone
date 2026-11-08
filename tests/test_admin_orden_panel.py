"""Panel del admin: "ultimos" alumnos y profesores son los ultimos registrados, y las tablas salen siempre en el mismo orden.

Sin order_by, PostgreSQL devuelve las filas en cualquier orden: el resumen mostraba 3 cualesquiera y la tabla de
usuarios cambiaba entre cargas.
"""

from django.test import TestCase
from django.urls import reverse

from alumnos.models import Especialidad, Genero
from tests.test_especialidad import crear_profesor
from tests.test_progreso_alumno import crear_alumno
from tests.test_retiros import crear_admin, entrar_admin


class OrdenDelPanelAdminTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        especialidad = Especialidad.objects.create(nombre='Mate')
        cls.alumnos = [crear_alumno(f'1000000{n}-0', f'Al{n}', genero) for n in range(5)]
        cls.profesores = [crear_profesor(f'2000000{n}-0', f'p{n}@lbwus.cl', especialidad) for n in range(5)]
        cls.admin, cls.tutor = crear_admin()

    def setUp(self):
        entrar_admin(self.client, self.admin, self.tutor)
        self.contexto = self.client.get(reverse('dashboard_admin')).context

    def test_los_ultimos_son_los_tres_mas_recientes_del_mas_nuevo_al_mas_viejo(self):
        self.assertEqual(list(self.contexto['ultimos_alumnos']), self.alumnos[:1:-1])
        self.assertEqual(list(self.contexto['ultimos_profesores']), self.profesores[:1:-1])

    def test_las_tablas_de_usuarios_salen_en_orden_de_registro(self):
        self.assertEqual(list(self.contexto['alumnos']), self.alumnos)
        self.assertEqual(list(self.contexto['profesores']), self.profesores)

    def test_la_tabla_de_clases_sale_en_orden_de_creacion(self):
        self.assertEqual(self.contexto['clases'].query.order_by, ('pk',))
