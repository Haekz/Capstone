"""Eliminar mi cuenta dentro de cada portal: la evaluacion, la confirmacion (enlace del correo) y la solicitud en curso.

Pertenece a Ayuda y soporte: el alumno ve marcado Soporte / Reportes y el docente Ayuda y soporte. El apoderado sigue en
el diseno publico. Datos ficticios.
"""

from django.core import signing
from django.test import SimpleTestCase
from django.urls import reverse

from alumnos.roles import ALUMNO, APODERADO, PROFESOR
from apoderados.models import Apoderado
from supresiones import identidad, solicitud
from tests.css_vars import sin_definir
from tests.test_apoderados import crear_apoderado
from tests.test_panel_docente_layout import CSS_ADMIN, CSS_PORTAL
from tests.test_portal_alumno_variables import PAGINA_ALUMNO
from tests.test_resenas import BaseResenas, entrar
from tests.test_tickets_en_portal import HOJAS_TICKETS

PLANTILLAS = [
    'supresiones/templates/supresiones/eliminar_cuenta.html', 'supresiones/templates/supresiones/confirmar.html',
    'supresiones/templates/supresiones/en_curso.html', 'supresiones/templates/supresiones/_evaluacion.html',
]


class VariablesCssDeEliminarCuentaTests(SimpleTestCase):
    """Mismas hojas que Ayuda y soporte; aqui se suman sus plantillas y la evaluacion."""

    def test_en_el_portal_del_alumno(self):
        self.assertEqual(sin_definir(HOJAS_TICKETS + PLANTILLAS, definidas_en=PAGINA_ALUMNO + HOJAS_TICKETS), {})

    def test_en_el_portal_del_docente(self):
        definidas = [CSS_ADMIN, CSS_PORTAL, *HOJAS_TICKETS]
        self.assertEqual(sin_definir(HOJAS_TICKETS + PLANTILLAS, definidas_en=definidas), {})


class EliminarCuentaEnElPortalTests(BaseResenas):

    def paginas(self, user):
        """Las tres pantallas, en el orden en que aparecen; la ultima necesita una solicitud abierta."""
        token = signing.dumps({'usuario': user.pk}, salt=identidad.SAL)
        yield 'eliminar_cuenta', reverse('eliminar_cuenta')
        yield 'confirmar', reverse('confirmar_eliminar_cuenta', args=[token])
        solicitud.abrir(user)
        yield 'en_curso', reverse('eliminar_cuenta')

    def test_el_alumno_las_ve_en_su_portal_con_un_solo_h1(self):
        entrar(self.client, self.ana, ALUMNO)
        for nombre, url in self.paginas(self.ana.user):
            with self.subTest(pagina=nombre):
                r = self.client.get(url)
                self.assertTemplateUsed(r, 'alumnos/base_alumno.html')
                self.assertContains(r, '<h1 id="portal-title">Eliminar mi cuenta</h1>')
                self.assertContains(r, "{ayuda: 'view-support'}['ayuda']")
                self.assertEqual(r.content.decode().count('<h1'), 1)

    def test_el_docente_las_ve_en_su_portal_con_ayuda_marcada(self):
        entrar(self.client, self.profesor, PROFESOR)
        for nombre, url in self.paginas(self.profesor.user):
            with self.subTest(pagina=nombre):
                r = self.client.get(url)
                self.assertTemplateUsed(r, 'user_profesor/base_docente.html')
                self.assertContains(r, 'id="nav-ayuda" class="nav-item active"')
                self.assertContains(r, 'portal_docente.css')

    def test_el_apoderado_sigue_en_el_diseno_publico(self):
        apoderado = crear_apoderado('44444444-4', Apoderado.VERIFICADO)
        entrar(self.client, apoderado, APODERADO)
        for nombre, url in self.paginas(apoderado.user):
            with self.subTest(pagina=nombre):
                r = self.client.get(url)
                self.assertTemplateNotUsed(r, 'alumnos/base_alumno.html')
                self.assertTemplateNotUsed(r, 'user_profesor/base_docente.html')
                self.assertNotContains(r, 'class="sidebar-menu"')
