"""Calificacion de cada profesor en las tarjetas del portal del alumno: promedio y total de resenas visibles.

Una sola consulta para todos los profesores (nada de N+1), sin las resenas ocultas por moderacion. Sin resenas
no hay calificacion: la tarjeta dice "Nuevo", no inventa estrellas.
"""

from django.urls import reverse

from alumnos.roles import ALUMNO
from resenas.consultas import calificaciones_por_profesor, formatear_promedio
from resenas.models import Resena
from tests.test_resenas import BaseResenas, entrar


class CalificacionesPorProfesorTests(BaseResenas):

    def setUp(self):
        self.resena(self.insc_paquete, puntaje=5)
        self.resena(self.insc_bea, puntaje=4)
        self.resena(self.insc_suelta, puntaje=1, estado=Resena.ESTADO_OCULTA)  # moderada: no cuenta

    def test_promedio_y_total_solo_con_resenas_visibles(self):
        calificacion = calificaciones_por_profesor()[self.profesor.id_profesor]
        self.assertEqual((calificacion['promedio'], calificacion['total']), (4.5, 2))

    def test_el_profesor_sin_resenas_no_aparece(self):
        self.assertNotIn(self.otro_profesor.id_profesor, calificaciones_por_profesor())

    def test_se_calcula_en_una_sola_consulta(self):
        with self.assertNumQueries(1):
            calificaciones_por_profesor()

    def test_formato_con_una_decimal_y_coma(self):
        self.assertEqual([formatear_promedio(n) for n in (4.5, 5, 3.25)], ['4,5', '5,0', '3,2'])

    def test_las_tarjetas_del_portal_reciben_la_calificacion_real_o_nada(self):
        entrar(self.client, self.ana, ALUMNO)
        tarjetas = {t['id']: t for t in self.client.get(reverse('alumno_pag1')).context['profesores_js']}
        self.assertEqual(tarjetas[self.profesor.id_profesor]['rating'], {'promedio': '4,5', 'total': 2})
        self.assertIsNone(tarjetas[self.otro_profesor.id_profesor]['rating'])
