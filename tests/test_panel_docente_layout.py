"""Panel del docente sobre el portal comun (base_docente -> base_admin, como admin y soporte).

El menu del docente son enlaces `#seccion` y el JS del panel cambia de seccion buscando `menu-X` y `sec-X`:
si un enlace pierde su seccion (o al reves), el clic falla en silencio. Esta prueba lo vigila.
"""

import re
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Especialidad, Genero, Profesor

User = get_user_model()

CLAVE = 'clave12345'
CSS_PORTAL = Path(__file__).resolve().parent.parent / 'user_profesor/static/user_profesor/portal_docente.css'


class PanelDocenteLayoutTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        usuario = User.objects.create_user(
            '22222222-2', password=CLAVE, rol='profesor', rut='22222222-2',
            first_name='Pedro', last_name='Profe', email='p@lbwus.cl', direccion='C2',
            fecha_nacimiento=date(1990, 1, 1), telefono='911111111',
            genero=Genero.objects.create(descripcion='Otro'),
        )
        Profesor.objects.create(user=usuario, especialidad=Especialidad.objects.create(nombre='Mate'))

    def setUp(self):
        self.client.post(reverse('login'), {'username': '22222222-2', 'password': CLAVE})
        self.html = self.client.get(reverse('panel_profesor')).content.decode()

    def test_usa_el_menu_del_portal_y_no_el_del_sitio_publico(self):
        self.assertIn('class="sidebar"', self.html)
        self.assertNotIn('prof-sidebar', self.html)
        self.assertEqual(self.html.count('<main'), 1)  # la base ya trae el suyo: no se anida otro

    def test_la_ficha_lleva_el_nombre_del_docente_y_su_rol(self):
        self.assertRegex(self.html, r'sidebar-user-name">\s*Pedro')
        self.assertRegex(self.html, r'sidebar-user-role">\s*Docente')

    def test_cada_enlace_del_menu_tiene_su_seccion(self):
        enlaces = set(re.findall(r'data-seccion="(\w+)"', self.html))
        secciones = set(re.findall(r'<section id="sec-(\w+)"', self.html))
        self.assertTrue(enlaces)
        self.assertEqual(enlaces, secciones)
        for seccion in enlaces:
            with self.subTest(seccion=seccion):
                self.assertIn(f'id="menu-{seccion}"', self.html)  # el JS busca menu-X

    def test_el_menu_lleva_a_mis_resenas_y_hay_campanita(self):
        self.assertIn(f'href="{reverse("resenas_profesor")}"', self.html)
        self.assertIn('notif-btn', self.html)

    def test_inicio_es_la_seccion_activa_de_entrada(self):
        self.assertRegex(self.html, r'<section id="sec-inicio" class="prof-section active"')
        self.assertRegex(self.html, r'id="menu-inicio" class="nav-item active"')

    def test_los_enlaces_sueltos_usan_un_color_que_se_lee_en_oscuro(self):
        """Sin regla propia salen azul del navegador: sobre el fondo oscuro del portal apenas se leen."""
        css = CSS_PORTAL.read_text(encoding='utf-8')
        self.assertRegex(css, r'\.page-content a:not\(\[class\]\)\s*\{[^}]*color:\s*var\(--primary-light\)')
