"""Panel docente, etapa 4 del rediseno: Videos de apoyo (ventana de subida), Sala de streaming y Clases solicitadas.

Videos ya tenia el marcado del diseno: solo cambia la ventana de subida. Streaming pasa de estilos en linea a clases stream-*.
"""

from django.urls import reverse

from tests.test_paquetes import RUT_PROFE, RUT_SIN_TITULO, Escenario


def _seccion(html, nombre):
    inicio = html.index(f'id="sec-{nombre}"')
    return html[inicio:html.index('</section>', inicio)]


class ContenidoDelPanelDocenteTests(Escenario):

    def panel(self, rut=RUT_PROFE):
        self.entrar(rut)
        return self.client.get(reverse('panel_profesor')).content.decode()

    # --- Videos de apoyo: la ventana de subida ---

    def test_la_ventana_de_subida_usa_clases_y_deja_donde_escribir_el_detalle_del_archivo(self):
        html = self.panel()
        ventana = html[html.index('id="profe-upload-modal"'):html.index('Publicar en mi biblioteca')]  # solo esta ventana, no los otros diálogos de la página
        self.assertIn('<h3 class="upload-titulo">Subir video de apoyo</h3>', ventana)
        self.assertIn('aria-label="Cerrar"', ventana)
        self.assertNotIn('&times;', ventana)
        # el JS escribe nombre, peso y duracion en #upload-file-info: sin ese parrafo la ayuda no aparece nunca
        self.assertRegex(ventana, r'<p class="upload-archivo-info" id="upload-file-info" role="status" hidden></p>')

    def test_la_ventana_conserva_los_campos_que_lee_el_script_de_subida(self):
        ventana = self.panel()
        for pieza in ('id="profe-video-upload-form"', 'onsubmit="submitUploadedVideo(event)"', 'id="upload-title"', 'id="upload-course"',
                      'id="upload-file"', 'accept="video/mp4"', 'onclick="closeUploadModal()"', 'onclick="openUploadModal()"'):
            self.assertIn(pieza, ventana)

    # --- Sala de streaming ---

    def test_streaming_muestra_cada_clase_como_tarjeta_y_abre_su_sala_de_forma_segura(self):
        streaming = _seccion(self.panel(), 'streaming')
        self.assertIn('class="stream-grid"', streaming)
        self.assertEqual(streaming.count('class="stream-card"'), 1)
        self.assertIn('class="stream-modalidad">online<', streaming)
        self.assertIn('class="stream-card-titulo">Algebra<', streaming)
        enlace = f'href="{reverse("sala_virtual", args=[self.clase.id_clase])}" target="_blank" rel="noopener" class="stream-entrar"'
        self.assertIn(enlace, streaming)  # target=_blank sin rel=noopener deja que la sala controle la pagina que la abrio
        self.assertNotIn('style=', streaming)  # ya no hay estilos en linea

    def test_streaming_sin_clases_lo_dice_con_el_estado_vacio_del_diseno(self):
        streaming = _seccion(self.panel(RUT_SIN_TITULO), 'streaming')
        self.assertNotIn('stream-grid', streaming)
        self.assertIn('prof-empty-card', streaming)
        self.assertIn('No tienes clases creadas aún', streaming)

    # --- Clases solicitadas ---

    def test_clases_solicitadas_usa_los_textos_del_diseno(self):
        clases = _seccion(self.panel(), 'clases')
        self.assertIn('Clases solicitadas', clases)
        self.assertIn('Inscripciones activas', clases)
        self.assertIn('Aún no recibes solicitudes. Cuando un alumno se inscriba en una de tus clases, aparecerá aquí.', clases)

    # --- Hojas ---

    def test_la_capa_completa_carga_sus_ocho_hojas_en_orden(self):
        html = self.panel()
        nombres = ('marco', 'inicio', 'formularios', 'tablas', 'agenda', 'cuenta', 'contenido', 'cierre')
        orden = [f'panel/06{letra}_pulido_docente_{nombre}.css' for letra, nombre in zip('abcdefgh', nombres)]
        posiciones = [html.index(hoja) for hoja in orden]
        self.assertEqual(posiciones, sorted(posiciones))
