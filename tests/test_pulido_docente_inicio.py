"""Panel docente, etapa 2 del rediseño: Inicio con banner (fecha y resumen del dia), metricas dentro del banner y las especializaciones al final.

Los datos siguen saliendo del servidor (saludo, dinero, clases disponibles, clases de hoy): solo cambia como se agrupan.
"""

import re

from django.urls import reverse

from alumnos.models import Profesor
from alumnos.roles import PROFESOR
from tests.test_especialidad import crear_profesor
from tests.test_resenas import BaseResenas, entrar


class InicioDelPanelDocenteTests(BaseResenas):

    def setUp(self):
        entrar(self.client, self.profesor, PROFESOR)
        self.html = self.client.get(reverse('panel_profesor')).content.decode()
        inicio = self.html.index('id="sec-inicio"')
        self.inicio = self.html[inicio:self.html.index('<section', inicio + 1)]

    def test_el_banner_reemplaza_la_cabecera_y_saluda_con_el_nombre_real(self):
        self.assertIn('class="prof-hero"', self.inicio)
        self.assertNotIn('prof-section-header', self.inicio)
        self.assertIn(f'Prof. {self.profesor.user.first_name}!', self.inicio)

    def test_el_js_encuentra_donde_escribir_la_fecha_y_el_resumen(self):
        # mejoras_docente.js completa #prof-hoy y #prof-resumen-hoy; con otro id la fecha quedaria en "Panel docente"
        self.assertIn('id="prof-hoy"', self.inicio)
        self.assertIn('id="prof-resumen-hoy"', self.inicio)

    def test_los_botones_del_banner_abren_agenda_y_videos(self):
        self.assertIn("switchSection('agenda')", self.inicio)
        self.assertIn("switchSection('grabaciones')", self.inicio)
        # esas secciones existen: si no, el boton no haria nada
        self.assertIn('id="sec-agenda"', self.html)
        self.assertIn('id="sec-grabaciones"', self.html)

    def test_las_dos_metricas_van_dentro_del_banner_y_antes_del_grafico(self):
        banner, metricas = self.inicio.index('class="prof-hero"'), self.inicio.index('class="prof-metrics-grid"')
        grilla = self.inicio.index('class="prof-dashboard-grid"')
        self.assertLess(banner, metricas)
        self.assertLess(metricas, grilla)
        self.assertEqual(self.inicio.count('prof-metric-card'), 2)
        self.assertIn('Generado hoy', self.inicio)
        self.assertIn('Clases disponibles restantes', self.inicio)

    def test_mis_especializaciones_va_al_final_del_inicio(self):
        self.assertLess(self.inicio.index('class="prof-dashboard-grid"'), self.inicio.index('id="espec-h"'))
        self.assertEqual(len(re.findall(r'id="espec-h"', self.inicio)), 1)  # no se duplico al moverla

    def test_el_aviso_del_titulo_solo_sale_sin_titulo_aprobado_y_va_arriba_del_grafico(self):
        self.assertNotIn('titulo-aviso', self.inicio)  # el profesor de la prueba tiene el titulo aprobado
        en_revision = crear_profesor('20000000-9', 'revision@lbwus.cl', None, titulo_estado=Profesor.TITULO_EN_REVISION)
        self.client.logout()
        entrar(self.client, en_revision, PROFESOR)
        html = self.client.get(reverse('panel_profesor')).content.decode()
        inicio = html[html.index('id="sec-inicio"'):]
        self.assertIn('Tu título está en revisión', inicio)
        self.assertLess(inicio.index('titulo-aviso'), inicio.index('class="prof-dashboard-grid"'))

    def test_carga_la_hoja_del_inicio_despues_de_la_del_marco(self):
        self.assertLess(self.html.index('06a_pulido_docente_marco.css'), self.html.index('06b_pulido_docente_inicio.css'))
