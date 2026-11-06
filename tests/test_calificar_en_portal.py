"""Calificar dentro del portal del alumno (solo el alumno la ve: @alumno_required). Datos ficticios."""

from django.test import SimpleTestCase
from django.urls import reverse

from alumnos.roles import ALUMNO
from tests.css_vars import leer_hoja, sin_definir
from tests.test_panel_docente_layout import HOJAS_RESENAS
from tests.test_portal_alumno_variables import PAGINA_ALUMNO
from tests.test_resenas import BaseResenas, entrar

PLANTILLAS = [
    'resenas/templates/resenas/calificar.html', 'resenas/templates/resenas/_estrellas.html',
    'resenas/templates/resenas/_mensajes.html', 'alumnos/templates/alumnos/includes/lineas_ayuda.html',
]


class VariablesCssDeCalificarTests(SimpleTestCase):
    """Sus hojas se escribieron para el sitio publico; el puente del portal del alumno tiene que cubrirlas."""

    def test_la_caja_de_telefonos_de_ayuda_tiene_estilo(self):
        """Estaba como texto plano en todos los disenos: el banner del menor y Calificar la usan."""
        css = leer_hoja('alumnos/static/alumnos/css/alumn_1')
        self.assertIn('.linea-ayuda-menor {', css)
        self.assertIn('color-mix(in srgb, currentColor', css)  # se adapta al fondo: banner oscuro o tarjeta clara

    def test_en_el_portal_del_alumno(self):
        self.assertEqual(sin_definir(HOJAS_RESENAS + PLANTILLAS, definidas_en=PAGINA_ALUMNO + HOJAS_RESENAS), {})


class CalificarEnElPortalTests(BaseResenas):

    def calificar(self):
        entrar(self.client, self.ana, ALUMNO)
        return self.client.get(reverse('resena_calificar', args=[self.insc_paquete.pk]))

    def test_se_ve_con_el_menu_del_alumno_y_mis_clases_marcado(self):
        r = self.calificar()
        self.assertTemplateUsed(r, 'alumnos/base_alumno.html')
        self.assertContains(r, '<h1 id="portal-title">Calificar clase</h1>')
        self.assertContains(r, "clases: 'view-my-classes'")  # el JS sabe a que boton corresponde la seccion...
        self.assertContains(r, "}['clases']")  # ...y la vista pidio esa seccion

    def test_un_solo_h1_y_la_pregunta_baja_a_h2(self):
        r = self.calificar()
        self.assertEqual(r.content.decode().count('<h1'), 1)
        self.assertContains(r, '<h2>Calificar a ')

    def test_sin_volver_al_portal_porque_el_menu_ya_lleva(self):
        self.assertNotContains(self.calificar(), 'Volver a mi portal')

    def test_con_una_estrella_siguen_los_telefonos_de_ayuda(self):
        entrar(self.client, self.ana, ALUMNO)
        url = reverse('resena_calificar', args=[self.insc_paquete.pk])
        self.client.post(url, {'puntaje': 1, 'comentario': ''})
        r = self.client.get(url)
        self.assertTemplateUsed(r, 'alumnos/base_alumno.html')
        self.assertContains(r, '¿Necesitas ayuda ahora?')
        self.assertContains(r, 'tel:133')

    def test_el_formulario_se_conserva(self):
        r = self.calificar()
        self.assertContains(r, 'Publicar reseña')
        self.assertContains(r, 'resena-form__puntaje')
