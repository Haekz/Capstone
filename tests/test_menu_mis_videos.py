"""B5 (13-nov): "Cursos Premium" llevaba a una pantalla vacia; ahora el menu tiene "Mis videos" y abre la videoteca real.

Los videos viven en su propia vista "Mis videos" (view-videos; antes era la pestana tab-videos del Inicio). El boton del
menu dice a que vista ir (data-view); fuera del panel lleva a alumno_pag1#view-videos. Vale igual para el menor.
Los enlaces viejos (?pestana=videos, #tab-videos) se siguen entendiendo: los resuelve el script del panel.
"""

from django.urls import reverse

from apoderados.models import Apoderado
from tests.test_apoderados import crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA, Escenario
from tests.test_ver_videos import RUT_APODERADO, RUT_MENOR

BOTON = 'data-view="view-videos"'


class MenuMisVideosTests(Escenario):

    def panel(self):
        return self.client.get(reverse('alumno_pag1'))

    def test_el_menu_abre_la_videoteca(self):
        self.entrar(RUT_ANA)
        respuesta = self.panel()
        self.assertContains(respuesta, BOTON)
        self.assertContains(respuesta, 'id="view-videos"')  # la vista que abre existe

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
        self.assertContains(respuesta, 'id="view-videos"')

    def test_fuera_del_panel_el_boton_lleva_a_la_vista(self):
        """En otras paginas del portal (Planes) no hay vistas: el menu va a alumno_pag1#view-videos."""
        self.entrar(RUT_ANA)
        respuesta = self.client.get(reverse('planes'))
        self.assertContains(respuesta, BOTON)
        self.assertContains(respuesta, 'irAlPortal(btn.dataset.tab || btn.dataset.view)')
