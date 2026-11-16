"""Portal del apoderado: lo que faltaba para verse como su copia visual (Abrir un ticket, observaciones vacias, Registrar estudiante).

Solo se prueba el diseno (estructura y orden de hojas); los datos de la demo de la copia no se copian. Datos ficticios.
"""
from django.template.loader import render_to_string
from django.urls import reverse

from alumnos.roles import APODERADO, PROFESOR
from apoderados.models import Apoderado
from soporte.models import Ticket
from tests.test_apoderados import crear_apoderado
from tests.test_resenas import BaseResenas, entrar


class AbrirUnTicketDelApoderadoTests(BaseResenas):

    def pagina_del_apoderado(self):
        apoderado = crear_apoderado('44444444-4', Apoderado.VERIFICADO)
        entrar(self.client, apoderado, APODERADO)
        return self.client.get(reverse('nuevo_ticket')).content.decode()

    def test_los_plazos_son_dos_filas_con_los_dias_del_modelo(self):
        html = self.pagina_del_apoderado()
        rapidos, lentos = Ticket.DIAS_HABILES[Ticket.PAGOS], Ticket.DIAS_HABILES[Ticket.TECNICO]
        self.assertIn('<ul class="tk-plazos">', html)
        self.assertIn(f'<li><span>Pagos, clases, conducta y videos</span><strong>{rapidos} días hábiles</strong></li>', html)
        self.assertIn(f'<li><span>Problemas técnicos y otros</span><strong>{lentos} días hábiles</strong></li>', html)
        self.assertNotIn('class="tk-ayuda-texto"', html)  # la frase corrida es del resto de los roles

    def test_la_fila_de_pagos_vale_para_todas_las_categorias_que_nombra(self):
        """La fila 'Pagos, clases, conducta y videos' lleva un solo numero: si el modelo las separara, la lista mentiria."""
        rapidas = {Ticket.DIAS_HABILES[c] for c in (Ticket.PAGOS, Ticket.CLASES, Ticket.CONDUCTA, Ticket.VIDEOS)}
        otras = {Ticket.DIAS_HABILES[c] for c in (Ticket.TECNICO, Ticket.OTRO)}
        self.assertEqual((len(rapidas), len(otras)), (1, 1))

    def test_la_barra_superior_trae_su_subtitulo(self):
        html = self.pagina_del_apoderado()
        self.assertIn('Cuéntanos qué pasó y te respondemos por escrito', html)

    def test_el_docente_sigue_con_la_frase_y_sin_lista(self):
        entrar(self.client, self.profesor, PROFESOR)
        html = self.client.get(reverse('nuevo_ticket')).content.decode()
        self.assertNotIn('class="tk-plazos"', html)
        self.assertIn('Pagos, clases, horario, conducta y videos: respondemos en 2 días hábiles.', html)


class ObservacionesVaciasTests(BaseResenas):

    def test_el_apoderado_las_ve_con_icono_y_la_clase_del_diseno(self):
        html = render_to_string('observaciones/_lista.html', {'observaciones': [], 'es_apoderado': True})
        self.assertIn('<p class="apo-vacio"><i class="bi bi-pencil-square" aria-hidden="true"></i> Aún no hay observaciones', html)

    def test_el_alumno_sigue_con_el_parrafo_simple(self):
        html = render_to_string('observaciones/_lista.html', {'observaciones': []})
        self.assertIn('<p>Aún no hay observaciones: tus profesores las dejan después de cada clase.</p>', html)
        self.assertNotIn('apo-vacio', html)


class RegistrarEstudianteComoLaCopiaTests(BaseResenas):

    def test_la_hoja_de_ajuste_carga_despues_de_la_del_portal(self):
        apoderado = crear_apoderado('44444444-4', Apoderado.VERIFICADO)
        entrar(self.client, apoderado, APODERADO)
        html = self.client.get(reverse('apoderado_registrar_estudiante')).content.decode()
        portal, ajuste = '16_portal_apoderado.css', '17_registrar_como_en_la_copia.css'
        self.assertIn(ajuste, html)
        self.assertLess(html.index(portal), html.index(ajuste))  # con el mismo peso, gana la que carga despues

    def test_el_ajuste_solo_actua_en_formularios_con_confirmacion_de_clave_del_portal(self):
        from pathlib import Path
        css = (Path(__file__).resolve().parent.parent / 'apoderados/static/apoderados/17_registrar_como_en_la_copia.css').read_text(encoding='utf-8')
        reglas = [r.split('{')[0].strip() for r in css.split('}') if '{' in r and not r.strip().startswith('/*')]
        sueltas = [r for r in reglas if not (r.startswith('#portal-alumno.portal-apoderado .apod-form:has(#id_confirmar_password)'))]
        self.assertEqual(sueltas, [])
