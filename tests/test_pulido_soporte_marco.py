"""Portal de soporte: marco de la capa de diseno (07a-07d, mejoras_soporte.js, menu por grupos, boton Ir a...).

Todo cuelga de #portal-soporte (id del <body> que pone base_soporte): el portal admin comparte base_admin y no debe verlo. Datos ficticios.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from soporte.models import Ticket
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_retiros import crear_admin, entrar_admin

CSS = Path(__file__).resolve().parent.parent / 'admin_portal/static/admin_portal/css/admin_panel'
PARTES = ['07a_pulido_soporte_marco.css', '07b_pulido_soporte_tickets.css', '07c_pulido_soporte_detalle.css', '07d_pulido_soporte_cierre.css']
PAGINAS = ('panel_soporte', 'apoderados_revision', 'titulos_adm')


def reglas_de_nivel_superior(css):
    """(cabecera, cuerpo) de cada regla; las de @media se abren, @keyframes se salta (sus 'from/to' no son selectores)."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    salida, profundidad, cabecera, cuerpo, abiertas = [], 0, '', '', []
    for ch in css:
        if ch == '{':
            abiertas.append(cabecera.strip())
            cabecera = ''
            profundidad += 1
        elif ch == '}':
            cerrada = abiertas.pop()
            profundidad -= 1
            if not cerrada.startswith('@') and not any(a.startswith('@keyframes') for a in abiertas):
                salida.append(cerrada)
            cabecera = ''
        else:
            cabecera += ch
    return salida


def selectores(cabecera):
    """Separa por las comas de NIVEL SUPERIOR: las de ':is(a, b)' no separan selectores."""
    partes, nivel, actual = [], 0, ''
    for ch in cabecera:
        nivel += (ch == '(') - (ch == ')')
        if ch == ',' and nivel == 0:
            partes.append(actual.strip())
            actual = ''
        else:
            actual += ch
    return partes + [actual.strip()]


class HojasDeSoporteTests(SimpleTestCase):

    def test_ninguna_hoja_pasa_de_600_lineas(self):
        for parte in PARTES:
            with self.subTest(parte=parte):
                self.assertLessEqual(len((CSS / parte).read_text(encoding='utf-8').splitlines()), 600)

    def test_toda_regla_cuelga_de_portal_soporte(self):
        """Si una regla suelta se colara, el portal admin (que comparte base_admin) cambiaria de aspecto."""
        for parte in PARTES:
            with self.subTest(parte=parte):
                sueltos = [s for r in reglas_de_nivel_superior((CSS / parte).read_text(encoding='utf-8'))
                           for s in selectores(r) if '#portal-soporte' not in s]
                self.assertEqual(sueltos, [])


class MarcoDeSoporteTests(TestCase):

    def pagina(self, nombre='panel_soporte', lider=False):
        agente = crear_agente('88888888-8', Ticket.APODERADOS, Ticket.TITULOS, lider=lider)
        entrar_soporte(self.client, agente)
        return self.client.get(reverse(nombre)).content.decode()

    def test_las_paginas_de_soporte_marcan_su_body_y_cargan_la_capa_en_orden(self):
        self.pagina()  # crea al agente y entra; las paginas se piden con esa misma sesion
        for nombre in PAGINAS:
            with self.subTest(pagina=nombre):
                html = self.client.get(reverse(nombre)).content.decode()
                self.assertIn('<body id="portal-soporte" class="light-mode">', html)
                posiciones = [html.index(p) for p in PARTES]
                self.assertEqual(posiciones, sorted(posiciones))  # 07d, con las pantallas medianas y el movil, va al final
                self.assertIn('soporte/mejoras_soporte.js', html)
                self.assertLess(html.index('sweetalert2'), html.index('mejoras_soporte.js'))  # usa Swal para confirmar el escalamiento

    def test_el_menu_va_en_grupos_y_el_agente_no_ve_privacidad_y_legal(self):
        html = self.pagina()
        self.assertEqual(re.findall(r'<span class="nav-label">([^<]+)</span>', html), ['Tickets', 'Verificaciones'])

    def test_el_lider_suma_privacidad_y_legal(self):
        html = self.pagina(lider=True)
        self.assertEqual(re.findall(r'<span class="nav-label">([^<]+)</span>', html), ['Tickets', 'Verificaciones', 'Privacidad y legal'])

    def test_la_barra_trae_el_boton_ir_a_antes_de_la_campana(self):
        html = self.pagina()
        self.assertIn('<span>Ir a…</span>', html)
        self.assertIn('<kbd>Ctrl K</kbd>', html)
        self.assertLess(html.index('class="topbar-buscar"'), html.index('toggleNotifications()'))

    def test_el_buscador_de_soporte_es_propio_y_sale_vacio_para_que_lo_arme_el_js(self):
        html = self.pagina()
        self.assertIn('role="dialog" aria-modal="true" aria-label="Ir a una sección o ticket"', html)
        self.assertIn('placeholder="Ir a una sección o ticket…"', html)
        self.assertIn('<span class="search-esc-badge">Esc</span>', html)
        self.assertRegex(html, r'id="search-modal-results">\s*</div>')  # sin los items fijos del admin (Usuarios, Clases)
        self.assertNotIn('Buscar alumnos, profesores, clases', html)

    def test_el_buscador_del_admin_sigue_igual(self):
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)
        html = self.client.get(reverse('dashboard_admin')).content.decode()
        self.assertIn('placeholder="Buscar alumnos, profesores, clases..."', html)
        self.assertIn('<span class="search-esc-badge">ESC</span>', html)
        self.assertIn('Sugerencias rápidas', html)
        self.assertNotIn('role="dialog" aria-modal="true" aria-label="Ir a una sección', html)

    def test_el_portal_admin_no_recibe_la_capa_de_soporte(self):
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)
        html = self.client.get(reverse('dashboard_admin')).content.decode()
        self.assertNotIn('portal-soporte', html)
        self.assertNotIn('07a_pulido_soporte', html)
        self.assertNotIn('mejoras_soporte.js', html)
        self.assertNotIn('topbar-buscar', html)
