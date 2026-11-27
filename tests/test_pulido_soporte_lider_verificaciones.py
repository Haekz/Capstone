"""Portal de soporte (lider), Apoderados y Documentos de profesores: los registros plegables de la copia con la logica real. Datos ficticios."""
from django.test import TestCase
from django.urls import reverse

from apoderados.models import Apoderado
from soporte.models import Ticket
from tests.test_apoderados import RUT, crear_agente, crear_apoderado, entrar_soporte
from tests.test_apoderados_vinculos import crear_menor_vinculado

REGISTROS_APODERADOS = ('Decisiones sobre identidad', 'Decisiones sobre vínculos', 'Revocaciones', 'Accesos a documentos')


class ApoderadosDelLiderTests(TestCase):

    def setUp(self):
        self.vinculo = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO))
        self.lider = crear_agente('10000003-5', Ticket.APODERADOS, lider=True)
        self.agente = crear_agente('10000001-9', Ticket.APODERADOS)

    def pagina(self, quien):
        entrar_soporte(self.client, quien)
        return self.client.get(reverse('apoderados_revision')).content.decode()

    def test_vinculos_verificados_con_estado_y_boton_de_revocar(self):
        html = self.pagina(self.lider)
        self.assertIn('<span class="sop-chip sop-chip--estado">Vigente</span>', html)
        self.assertIn(f'<a class="sop-btn sop-btn--peligro" href="{reverse("apoderados_revocar_vinculo", args=[self.vinculo.pk])}">Revocar</a>', html)
        self.assertIn(f'<span class="sop-persona-texto"><strong>{self.vinculo.alumno.user.first_name}</strong>', html)
        self.assertIn(f'<small>RUT {self.vinculo.alumno.user.rut}</small>', html)

    def test_los_cuatro_registros_van_plegados_despues_de_los_vinculos(self):
        html = self.pagina(self.lider)
        self.assertEqual(html.count('<details class="panel sop-registro">'), 4)
        self.assertNotIn('<details class="panel sop-registro" open', html)
        posiciones = [html.index('Vínculos verificados'), html.index('<h2 class="sop-grupo-titulo">Registros</h2>')]
        posiciones += [html.index(f'{titulo} <span class="sop-registro-nota">') for titulo in REGISTROS_APODERADOS]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertIn('Accesos a documentos <span class="sop-registro-nota">últimos 50</span>', html)
        self.assertIn('Todavía no hay decisiones registradas.', html)

    def test_el_agente_no_ve_vinculos_verificados_ni_registros(self):
        html = self.pagina(self.agente)
        for rastro in ('Vínculos verificados', 'sop-registro', 'sop-grupo-titulo', 'Revocar'):
            with self.subTest(rastro=rastro):
                self.assertNotIn(rastro, html)


class DocumentosDelLiderTests(TestCase):

    def setUp(self):
        self.lider = crear_agente('10000003-5', Ticket.TITULOS, lider=True)
        self.agente = crear_agente('10000001-9', Ticket.TITULOS)

    def pagina(self, quien):
        entrar_soporte(self.client, quien)
        return self.client.get(reverse('titulos_adm')).content.decode()

    def test_el_lider_ve_otros_profesores_y_las_aperturas_plegadas(self):
        html = self.pagina(self.lider)
        self.assertIn('Otros profesores</h2>', html)
        self.assertNotIn('Resto de profesores', html)
        self.assertIn('<h2 class="sop-grupo-titulo">Registros</h2>', html)
        self.assertIn('Aperturas de documentos <span class="sop-registro-nota">últimas 50</span>', html)
        self.assertEqual(html.count('<details class="panel sop-registro">'), 1)

    def test_el_agente_no_ve_nada_del_lider(self):
        html = self.pagina(self.agente)
        for rastro in ('Otros profesores', 'sop-registro', 'sop-grupo-titulo', 'Aperturas de documentos'):
            with self.subTest(rastro=rastro):
                self.assertNotIn(rastro, html)
