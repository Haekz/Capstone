"""B5 (13-nov): "Cursos Premium" llevaba a una pantalla vacia; ahora el menu tiene "Mis videos" y abre la videoteca real.

Los videos viven en la pestana "Mis videos" del Inicio (tab-videos). El boton del menu dice a que vista ir
(data-view) y que pestana abrir (data-tab); fuera del panel lleva a alumno_pag1#tab-videos. Vale igual para el menor:
no depende del script de ?pestana=videos, que solo se carga para quien compra extras.
"""

from django.urls import reverse

from apoderados.models import Apoderado
from tests.test_apoderados import crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA, Escenario
from tests.test_ver_videos import RUT_APODERADO, RUT_MENOR

BOTON = 'data-view="view-dashboard" data-tab="tab-videos"'


class MenuMisVideosTests(Escenario):

    def panel(self):
        return self.client.get(reverse('alumno_pag1'))

    def test_el_menu_abre_la_videoteca(self):
        self.entrar(RUT_ANA)
        respuesta = self.panel()
        self.assertContains(respuesta, BOTON)
        self.assertContains(respuesta, 'id="tab-videos"')  # la pestana que abre existe

    def test_ya_no_hay_cursos_premium(self):
        self.entrar(RUT_ANA)
        respuesta = self.panel()
        for texto in ('Cursos Premium', 'id="view-courses"', 'Los cursos grabados estarán disponibles próximamente.'):
            with self.subTest(texto=texto):
                self.assertNotContains(respuesta, texto)

    def test_el_menor_tambien_llega_a_sus_videos(self):
        alumno = crear_menor_vinculado(crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO), rut=RUT_MENOR).alumno
        entrar(self.client, alumno.user, alumno_id=alumno.id_alumno)
        respuesta = self.panel()
        self.assertContains(respuesta, BOTON)
        self.assertContains(respuesta, 'id="tab-videos"')

    def test_fuera_del_panel_el_boton_lleva_a_la_pestana(self):
        """En otras paginas del portal (Planes) no hay vistas: el menu va a alumno_pag1#tab-videos."""
        self.entrar(RUT_ANA)
        respuesta = self.client.get(reverse('planes'))
        self.assertContains(respuesta, BOTON)
        self.assertContains(respuesta, 'irAlPortal(btn.dataset.tab || btn.dataset.view)')
