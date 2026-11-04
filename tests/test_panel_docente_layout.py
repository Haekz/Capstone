"""Panel del docente sobre el portal comun (base_docente -> base_admin, como admin y soporte).

El menu del docente son enlaces `#seccion` y el JS del panel cambia de seccion buscando `menu-X` y `sec-X`:
si un enlace pierde su seccion (o al reves), el clic falla en silencio. Esta prueba lo vigila.
"""

import re
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Especialidad, Genero, Profesor

from .css_vars import leer, sin_definir

User = get_user_model()

CLAVE = 'clave12345'
CSS_PORTAL = 'user_profesor/static/user_profesor/portal_docente.css'
CSS_ADMIN = 'admin_portal/static/admin_portal/css/admin_panel.css'

# Todo lo que dibuja el panel del docente: la base, el panel, sus parciales y sus hojas.
HOJAS_PANEL = [
    'user_profesor/static/panel.css', 'user_profesor/static/clases_solicitadas.css',
    'user_profesor/static/videos.css', 'user_profesor/static/clases_en_vivo.css',
]
PLANTILLAS_PANEL = [
    'user_profesor/templates/user_profesor/base_docente.html',
    'user_profesor/templates/user_profesor/panel_profesor.html',
    'user_profesor/templates/user_profesor/clases_solicitadas.html',
    'user_profesor/templates/user_profesor/clases_en_vivo.html',
    'user_profesor/templates/user_profesor/videos.html',
    'user_profesor/templates/user_profesor/titulo_aviso.html',
    'agenda/templates/agenda/panel_agenda.html',
    'mensajes/templates/mensajes/buzon_profesor.html',
]

# Mis Resenas: su plantilla y las dos hojas que comparte con el sitio publico (perfil del profesor, calificar).
HOJAS_RESENAS = ['resenas/static/resenas/resenas.css', 'alumnos/static/alumnos/css/perfil_profesor.css']
PLANTILLAS_RESENAS = [
    'resenas/templates/resenas/profesor.html', 'resenas/templates/resenas/_bloque.html',
    'resenas/templates/resenas/_estrellas.html', 'resenas/templates/resenas/_mensajes.html',
]


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

    def test_mis_resenas_vive_en_el_portal_con_su_item_activo(self):
        html = self.client.get(reverse('resenas_profesor')).content.decode()
        self.assertIn('class="sidebar"', html)
        self.assertEqual(html.count('<main'), 1)
        self.assertRegex(html, r'id="nav-resenas" class="nav-item active"')
        self.assertNotIn('Volver a mi panel', html)  # el menu ya lleva al panel

    def test_las_variables_css_de_mis_resenas_existen_en_el_portal(self):
        """Sus hojas son las del sitio publico (--line, --r-md, --surface...): el puente las traduce al portal."""
        faltantes = sin_definir(HOJAS_RESENAS + PLANTILLAS_RESENAS, definidas_en=[CSS_ADMIN, CSS_PORTAL, *HOJAS_RESENAS])
        self.assertEqual(faltantes, {})

    def test_los_enlaces_sueltos_usan_un_color_que_se_lee_en_oscuro(self):
        """Sin regla propia salen azul del navegador: sobre el fondo oscuro del portal apenas se leen."""
        css = leer(CSS_PORTAL)
        self.assertRegex(css, r'\.page-content a:not\(\[class\]\)\s*\{[^}]*color:\s*var\(--primary-light\)')

    def test_el_titulo_de_tarjeta_no_reparte_el_icono_y_el_texto_a_los_extremos(self):
        """Con space-between, 'icono + texto' mandaba el texto a la derecha. La etiqueta se empuja sola."""
        css = leer('user_profesor/static/panel.css')
        titulo = re.search(r'\.prof-card-title\s*\{([^}]*)\}', css).group(1)
        self.assertNotIn('space-between', titulo)
        etiqueta = re.search(r'\.prof-card-title-badge\s*\{([^}]*)\}', css).group(1)
        self.assertIn('margin-left: auto', etiqueta)

    def test_toda_variable_css_del_panel_existe_en_el_portal(self):
        """Una variable que no existe no da error: la propiedad queda sin valor (fondo transparente, color heredado).

        Pasaba con las del sitio publico (--text, --white...) y con --bg-panel / --border-color / --bg-dark, que solo
        existen dentro de sala_virtual.html. Cada var(--x) debe estar definida en el portal, en el puente
        o en las propias hojas del panel.
        """
        faltantes = sin_definir(HOJAS_PANEL + PLANTILLAS_PANEL, definidas_en=[CSS_ADMIN, CSS_PORTAL, *HOJAS_PANEL])
        self.assertEqual(faltantes, {})
