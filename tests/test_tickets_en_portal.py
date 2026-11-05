"""Ayuda y soporte dentro de cada portal: mis tickets, el detalle y Abrir un ticket.

El alumno y el docente las ven con el menu de su portal y la seccion marcada; el apoderado sigue en el diseno publico
(su portal usa ese diseno). Datos ficticios.
"""

from django.test import SimpleTestCase
from django.urls import reverse

from alumnos.roles import ALUMNO, APODERADO, PROFESOR
from apoderados.models import Apoderado
from soporte.models import Ticket
from soporte.tickets import abrir_reporte
from tests.css_vars import sin_definir
from tests.test_apoderados import crear_apoderado
from tests.test_panel_docente_layout import CSS_ADMIN, CSS_PORTAL
from tests.test_portal_alumno_variables import PAGINA_ALUMNO
from tests.test_resenas import BaseResenas, entrar

PAGINAS = ('mis_tickets', 'nuevo_ticket', 'mi_ticket')

# Lo que dibujan las tres paginas: sus hojas (escritas para el sitio publico) y sus plantillas con sus parciales.
HOJAS_TICKETS = ['alumnos/static/alumnos/css/perfil_profesor.css', 'apoderados/static/apoderados/apoderados.css']
PLANTILLAS_TICKETS = [
    'soporte/templates/soporte/mis_tickets.html', 'soporte/templates/soporte/mi_ticket.html',
    'apoderados/templates/apoderados/formulario.html', 'apoderados/templates/apoderados/_mensajes.html',
    'soporte/templates/soporte/_conversacion.html', 'soporte/templates/soporte/_formulario_mensaje.html',
]


class VariablesCssDeTicketsTests(SimpleTestCase):
    """Una variable sin definir no da error: el borde o el fondo desaparecen. Cada portal hace su puente."""

    def test_en_el_portal_del_alumno(self):
        faltantes = sin_definir(HOJAS_TICKETS + PLANTILLAS_TICKETS, definidas_en=PAGINA_ALUMNO + HOJAS_TICKETS)
        self.assertEqual(faltantes, {})

    def test_en_el_portal_del_docente(self):
        faltantes = sin_definir(HOJAS_TICKETS + PLANTILLAS_TICKETS, definidas_en=[CSS_ADMIN, CSS_PORTAL, *HOJAS_TICKETS])
        self.assertEqual(faltantes, {})


class TicketsEnElPortalTests(BaseResenas):

    def url(self, nombre, usuario):
        if nombre != 'mi_ticket':
            return reverse(nombre)
        ticket = abrir_reporte(usuario, Ticket.PAGOS, 'Cobro doble', 'Aparecen dos cargos.')
        return reverse('mi_ticket', args=[ticket.pk])

    def test_el_alumno_las_ve_en_su_portal_con_soporte_marcado(self):
        entrar(self.client, self.ana, ALUMNO)
        for nombre in PAGINAS:
            with self.subTest(pagina=nombre):
                r = self.client.get(self.url(nombre, self.ana.user))
                self.assertTemplateUsed(r, 'alumnos/base_alumno.html')
                self.assertContains(r, '<aside class="sidebar-menu"')
                self.assertContains(r, "ayuda: 'view-support'")  # el JS sabe a que boton corresponde la seccion...
                self.assertContains(r, "}['ayuda']")  # ...y la vista pidio esa seccion
                self.assertEqual(r.content.decode().count('<h1'), 1)  # el de la barra; no se repite en la pagina

    def test_el_alumno_lee_la_seccion_en_la_barra(self):
        entrar(self.client, self.ana, ALUMNO)
        self.assertContains(self.client.get(reverse('mis_tickets')), '<h1 id="portal-title">Ayuda y soporte</h1>')
        self.assertContains(self.client.get(reverse('nuevo_ticket')), '<h1 id="portal-title">Abrir un ticket</h1>')

    def test_sin_volver_al_portal_porque_el_menu_ya_lleva(self):
        entrar(self.client, self.ana, ALUMNO)
        self.assertNotContains(self.client.get(reverse('mis_tickets')), 'Volver a mi portal')

    def test_el_docente_las_ve_en_su_portal_con_ayuda_marcada(self):
        entrar(self.client, self.profesor, PROFESOR)
        for nombre in PAGINAS:
            with self.subTest(pagina=nombre):
                r = self.client.get(self.url(nombre, self.profesor.user))
                self.assertTemplateUsed(r, 'user_profesor/base_docente.html')
                self.assertContains(r, 'id="nav-ayuda" class="nav-item active"')
                self.assertContains(r, 'portal_docente.css')  # el block.super: sin el, el portal pierde su CSS

    def test_en_el_panel_del_docente_ayuda_no_queda_marcada(self):
        entrar(self.client, self.profesor, PROFESOR)
        r = self.client.get(reverse('panel_profesor'))
        self.assertContains(r, f'id="nav-ayuda" class="nav-item" href="{reverse("mis_tickets")}"')

    def test_el_apoderado_sigue_en_el_diseno_publico(self):
        apoderado = crear_apoderado('44444444-4', Apoderado.VERIFICADO)
        entrar(self.client, apoderado, APODERADO)
        for nombre in PAGINAS:
            with self.subTest(pagina=nombre):
                r = self.client.get(self.url(nombre, apoderado.user))
                self.assertTemplateNotUsed(r, 'alumnos/base_alumno.html')
                self.assertTemplateNotUsed(r, 'user_profesor/base_docente.html')
                self.assertNotContains(r, 'class="sidebar-menu"')
        self.assertContains(self.client.get(reverse('mis_tickets')), 'Volver a mi cuenta')
