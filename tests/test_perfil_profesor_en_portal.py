"""Perfil del profesor dentro del portal del alumno (solo el alumno lo ve: @alumno_required). Datos ficticios."""

from datetime import time

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from alumnos.models import Asignatura, Clase, Especialidad, Genero
from tests.css_vars import sin_definir
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_panel_docente_layout import HOJAS_RESENAS, PLANTILLAS_RESENAS
from tests.test_portal_alumno_variables import PAGINA_ALUMNO
from tests.test_progreso_alumno import crear_alumno

RUT_ANA = '11111111-1'
RUT_PROFE = '20000000-1'
PLANTILLAS = ['alumnos/templates/alumnos/perfil_profesor.html', *PLANTILLAS_RESENAS]


class VariablesCssDelPerfilTests(SimpleTestCase):
    """Sus hojas se escribieron para el sitio publico; el puente del portal del alumno tiene que cubrirlas."""

    def test_en_el_portal_del_alumno(self):
        self.assertEqual(sin_definir(HOJAS_RESENAS + PLANTILLAS, definidas_en=PAGINA_ALUMNO + HOJAS_RESENAS), {})


class PerfilDelProfesorEnElPortalTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        crear_alumno(RUT_ANA, 'Ana', Genero.objects.create(descripcion='Otro'))
        matematicas = Especialidad.objects.create(nombre='Matemáticas')
        cls.profe = crear_profesor(RUT_PROFE, 'profe@lbwus.cl', matematicas)
        clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                     modalidad='online', horario=time(10, 0), profesor=cls.profe)
        crear_sesion(clase, dias=3)

    def perfil(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        return self.client.get(reverse('perfil_profesor', args=[self.profe.id_profesor]))

    def test_se_ve_con_el_menu_del_alumno_y_el_titulo_en_la_barra(self):
        r = self.perfil()
        self.assertTemplateUsed(r, 'alumnos/base_alumno.html')
        self.assertContains(r, '<h1 id="portal-title">Perfil del profesor</h1>')
        self.assertEqual(r.content.decode().count('<h1'), 1)  # el nombre del profesor baja a h2
        self.assertContains(r, '<h2>Profe')

    def test_ningun_item_del_menu_queda_marcado(self):
        """El perfil no es un item del menu: se llega desde la busqueda o los favoritos."""
        self.assertContains(self.perfil(), "}['']")

    def test_sin_volver_al_portal_porque_el_menu_ya_lleva(self):
        self.assertNotContains(self.perfil(), 'Volver a mi portal')

    def test_conserva_su_contenido_y_el_enlace_a_reservar(self):
        r = self.perfil()
        for dato in ('Matemáticas', 'Título profesional verificado', 'Álgebra', 'Reservar un horario'):
            self.assertContains(r, dato)
