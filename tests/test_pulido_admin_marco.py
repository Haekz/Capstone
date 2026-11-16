"""Portal de admin: marco de la capa de diseno (06a-06d).

Todo cuelga de #portal-admin (id del <body> que pone base_admin por defecto). Soporte y Docente comparten esa base y NO deben cargar la capa
ni cambiar su <body>. Datos ficticios.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from alumnos.roles import PROFESOR
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_pulido_soporte_marco import reglas_de_nivel_superior, selectores
from tests.test_resenas import BaseResenas, entrar
from tests.test_retiros import crear_admin, entrar_admin
from soporte.models import Ticket

CSS = Path(__file__).resolve().parent.parent / 'admin_portal/static/admin_portal/css/admin_panel'
PARTES = ['06a_pulido_admin_marco.css', '06b_pulido_admin_resumen.css', '06c_pulido_admin_pantallas.css', '06d_pulido_admin_cierre.css']
CUERPO_ADMIN = '<body id="portal-admin" class="light-mode">'
PAGINAS_ADMIN = ('dashboard_admin', 'planes_adm', 'nosotros_adm', 'casos_escalados', 'asignaturas_adm', 'resenas_moderacion')


class HojasDeAdminTests(SimpleTestCase):

    def test_ninguna_hoja_pasa_de_600_lineas(self):
        for parte in PARTES:
            with self.subTest(parte=parte):
                self.assertLessEqual(len((CSS / parte).read_text(encoding='utf-8').splitlines()), 600)

    def test_toda_regla_cuelga_de_portal_admin(self):
        """Si una regla suelta se colara, Soporte y Docente (que comparten base_admin) cambiarian de aspecto."""
        for parte in PARTES:
            with self.subTest(parte=parte):
                sueltos = [s for r in reglas_de_nivel_superior((CSS / parte).read_text(encoding='utf-8'))
                           for s in selectores(r) if '#portal-admin' not in s]
                self.assertEqual(sueltos, [])


class MarcoDeAdminTests(TestCase):

    def pagina(self, nombre):
        return self.client.get(reverse(nombre)).content.decode()

    def test_las_paginas_del_admin_marcan_su_body_y_cargan_la_capa_en_orden(self):
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)
        for nombre in PAGINAS_ADMIN:
            with self.subTest(pagina=nombre):
                html = self.pagina(nombre)
                self.assertIn(CUERPO_ADMIN, html)
                posiciones = [html.index(p) for p in PARTES]  # falla si alguna no esta
                self.assertEqual(posiciones, sorted(posiciones))  # 06d, con las pantallas medianas y el movil, va al final de la capa
                self.assertLess(html.index('05_rediseno_contenido.css'), posiciones[0])  # la capa pisa a las anteriores

    def test_soporte_no_carga_la_capa_ni_cambia_de_body(self):
        entrar_soporte(self.client, crear_agente('88888888-8', Ticket.APODERADOS, Ticket.TITULOS))
        html = self.pagina('panel_soporte')
        self.assertIn('<body id="portal-soporte" class="light-mode">', html)
        self.assertNotIn('portal-admin', html)
        self.assertNotIn('06a_pulido_admin', html)


class MarcoDeAdminTitulosTests(TestCase):
    """Etapa A2: la marca, el menu, la barra superior y los titulos con los nombres de la copia."""

    def setUp(self):
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)

    def pagina(self, nombre):
        return self.client.get(reverse(nombre)).content.decode()

    def test_la_marca_y_el_menu_usan_los_nombres_de_la_copia(self):
        html = self.pagina('dashboard_admin')
        self.assertIn('<span class="sidebar-brand-role">Portal admin</span>', html)
        nombres = re.findall(r'<a id="nav-[a-z]+" class="nav-item[^"]*"[^>]*>\s*<i[^>]*></i>\s*([^<]+?)\s*</a>', html)
        self.assertEqual(nombres, ['Resumen', 'Usuarios', 'Reseñas', 'Planes', 'Nosotros', 'Casos escalados', 'Clases', 'Asignaturas', 'Finanzas', 'Ajustes'])
        self.assertEqual(re.findall(r'<span class="nav-label">([^<]+)</span>', html), ['Principal', 'Contenido', 'Herramientas'])

    def test_la_barra_trae_el_boton_ir_a_antes_de_la_campana(self):
        for nombre in PAGINAS_ADMIN:
            with self.subTest(pagina=nombre):
                html = self.pagina(nombre)
                self.assertIn('<span>Ir a…</span>', html)
                self.assertIn('<kbd>Ctrl K</kbd>', html)
                self.assertLess(html.index('class="topbar-buscar"'), html.index('toggleNotifications()'))

    def test_el_dashboard_titula_cada_seccion_como_la_copia(self):
        html = self.pagina('dashboard_admin')
        self.assertIn('<h1 id="section-title">Resumen</h1>', html)
        for esperado in ("resumen: ['Resumen', 'Cómo está LBWUS hoy']", "usuarios: ['Usuarios', 'Alumnos, profesores y administradores']",
                         "clases: ['Clases', 'Las clases que soporte asignó a cada profesor (solo lectura)']",
                         "finanzas: ['Finanzas', 'Ingresos de la plataforma y retiros de los profesores']",
                         "ajustes: ['Ajustes', 'Tus datos y la apariencia del panel']"):
            with self.subTest(titulo=esperado):
                self.assertIn(esperado, html)

    def test_las_paginas_sueltas_titulan_como_la_copia(self):
        esperados = {'planes_adm': 'Planes', 'nosotros_adm': 'Nosotros', 'casos_escalados': 'Casos escalados',
                     'asignaturas_adm': 'Asignaturas', 'resenas_moderacion': 'Moderación de reseñas'}
        for nombre, titulo in esperados.items():
            with self.subTest(pagina=nombre):
                self.assertIn(f'<h1 id="section-title">{titulo}</h1>', self.pagina(nombre))
        self.assertIn('Vista interna de la sección "Nosotros" del sitio', self.pagina('nosotros_adm'))


class MarcoDeAdminFrenteAlDocenteTests(BaseResenas):

    def test_el_docente_no_carga_la_capa_ni_cambia_de_body(self):
        entrar(self.client, self.profesor, PROFESOR)
        html = self.client.get(reverse('panel_profesor')).content.decode()
        self.assertIn('<body id="portal-docente" class="light-mode">', html)
        self.assertNotIn('portal-admin', html)
        self.assertNotIn('06a_pulido_admin', html)
        self.assertIn('<span>Cerrar sesión</span>', html)  # como la copia del docente (antes salia con S mayuscula, la de la base)
