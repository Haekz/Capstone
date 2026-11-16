"""Panel docente, etapa 1 del rediseño: el enganche #portal-docente, las hojas de la capa y el boton «Ir a…».

La capa de diseño cuelga de #portal-docente (id del <body>) y de body:not(.light-mode)#portal-docente para el modo noche.
El id lo pone base_docente a traves de un bloque de base_admin: admin y soporte comparten esa base y NO deben cambiar.
"""

import re

from django.urls import reverse

from alumnos.roles import ADMIN, PROFESOR
from tests.test_resenas import BaseResenas, entrar

CUERPO_DOCENTE = '<body id="portal-docente" class="light-mode">'


class MarcoDelPanelDocenteTests(BaseResenas):

    def pagina(self, nombre, perfil, rol):
        self.client.logout()
        entrar(self.client, perfil, rol)
        return self.client.get(reverse(nombre)).content.decode()

    def test_todo_el_portal_docente_lleva_el_enganche_de_la_capa(self):
        for nombre in ('panel_profesor', 'resenas_profesor'):
            with self.subTest(pagina=nombre):
                self.assertIn(CUERPO_DOCENTE, self.pagina(nombre, self.profesor, PROFESOR))

    def test_admin_y_soporte_comparten_la_base_pero_no_cambian(self):
        html = self.pagina('resenas_moderacion', self.admin, ADMIN)
        self.assertIn('<body class="light-mode">', html)
        self.assertNotIn('portal-docente', html)

    def test_la_capa_carga_marco_tablas_y_cierre_en_ese_orden(self):
        # Las tablas van con el marco: sin ellas, el area de contenido (overflow:visible) deja que una tabla ancha estire la pagina.
        orden = ['panel/06a_pulido_docente_marco.css', 'panel/06d_pulido_docente_tablas.css', 'panel/06h_pulido_docente_cierre.css']
        for nombre in ('panel_profesor', 'resenas_profesor'):
            with self.subTest(pagina=nombre):
                html = self.pagina(nombre, self.profesor, PROFESOR)
                posiciones = [html.index(hoja) for hoja in orden]  # falla si alguna no esta
                self.assertEqual(posiciones, sorted(posiciones))  # el cierre (celular) va al final de la capa

    def test_el_boton_ir_a_solo_esta_en_el_panel(self):
        # En las demas paginas, Ctrl+K abriria el buscador del admin: ahi el docente solo lleva su campanita.
        panel = self.pagina('panel_profesor', self.profesor, PROFESOR)
        self.assertIn('class="topbar-buscar"', panel)
        self.assertIn('<kbd>Ctrl K</kbd>', panel)
        resenas = self.pagina('resenas_profesor', self.profesor, PROFESOR)
        self.assertNotIn('topbar-buscar', resenas)
        self.assertIn('notif-btn', resenas)  # la campanita sigue en todas

    def test_ningun_comentario_de_plantilla_se_imprime_como_texto(self):
        # {# ... #} solo sirve en UNA linea: en dos, Django lo imprime tal cual (se vio sobre la barra superior). Para varias, {% comment %}.
        for nombre in ('panel_profesor', 'resenas_profesor'):
            with self.subTest(pagina=nombre):
                html = self.pagina(nombre, self.profesor, PROFESOR)
                self.assertNotIn('{#', html)
                self.assertNotIn('#}', html)

    def test_el_menu_dice_lo_mismo_que_el_titulo_de_la_barra_superior(self):
        # el JS escribe estos titulos arriba al cambiar de seccion: si el menu dijera otra cosa, el usuario veria dos nombres
        panel = self.pagina('panel_profesor', self.profesor, PROFESOR)
        esperado = {'menu-inicio': 'Inicio', 'menu-clases': 'Clases solicitadas', 'menu-agenda': 'Mi agenda', 'menu-buzon': 'Buzón de alumnos',
                    'menu-grabaciones': 'Videos de apoyo', 'menu-streaming': 'Sala de streaming', 'menu-perfil': 'Mi perfil',
                    'menu-saldo': 'Saldo y pagos', 'nav-resenas': 'Mis reseñas', 'nav-ayuda': 'Ayuda y soporte'}
        for id_, texto in esperado.items():
            with self.subTest(enlace=id_):
                contenido = re.search(rf'<a [^>]*id="{id_}"[^>]*>(.*?)</a>', panel, re.S).group(1)
                self.assertEqual(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', contenido)).strip(), texto)

    def test_las_mejoras_de_uso_cargan_solo_en_el_panel_y_despues_de_sus_funciones(self):
        panel = self.pagina('panel_profesor', self.profesor, PROFESOR)
        etiqueta = re.search(r'<script[^>]+mejoras_docente\.js', panel)  # la etiqueta, no cualquier mencion del nombre
        self.assertIsNotNone(etiqueta)
        # usa window.switchSection y closeUploadModal: tienen que estar definidas antes
        self.assertLess(panel.index('window.switchSection = switchSection'), etiqueta.start())
        self.assertNotIn('mejoras_docente.js', self.pagina('resenas_profesor', self.profesor, PROFESOR))
