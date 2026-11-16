"""Portal de soporte, Escalar: la estructura de la copia (columna principal + historial lateral) con la logica real. Datos ficticios."""
from django.urls import reverse

from soporte.models import Escalamiento
from tests.test_escalamientos import MOTIVO, Escenario
from tests.test_apoderados import entrar_soporte
from tests.test_retiros import crear_admin, entrar_admin


class EscalarComoLaCopiaTests(Escenario):

    def test_el_agente_ve_el_formulario_y_el_historial_vacio(self):
        entrar_soporte(self.client, self.agente)
        html = self.client.get(self.url).content.decode()
        self.assertIn(f'<a class="sop-volver" href="{reverse("soporte_reporte", args=[self.ticket.pk])}">', html)
        self.assertIn(f'Volver al ticket #{self.ticket.pk}', html)
        self.assertIn('Escalar al líder de soporte</h2>', html)
        self.assertIn('<strong>Solo para casos graves:</strong>', html)
        self.assertIn('El ticket pasa al líder de soporte y deja de aparecer en tu panel. El plazo no cambia.', html)
        self.assertIn('<p class="sop-ficha-vacio">Este ticket no se ha escalado.</p>', html)
        self.assertIn('name="motivo"', html)

    def test_el_lider_escala_a_un_administrador(self):
        entrar_soporte(self.client, self.lider)
        html = self.client.get(self.url).content.decode()
        self.assertIn('Escalar a un administrador</h2>', html)
        self.assertIn('El ticket sigue en soporte: el administrador lee tu motivo', html)
        self.assertNotIn('Escalar al líder', html)

    def test_esperando_indicacion_no_hay_formulario_y_el_estado_va_en_el_historial(self):
        self.escalar_como(self.lider)
        html = self.client.get(self.url).content.decode()
        self.assertIn('Ya está escalado a un administrador.', html)
        self.assertNotIn('name="motivo"', html)
        self.assertIn(MOTIVO, html)
        self.assertIn('<span class="badge">Esperando indicación del administrador</span>', html)
        self.assertIn('<dl class="sop-datos">', html)

    def test_la_indicacion_del_admin_aparece_en_el_historial(self):
        self.escalar_como(self.lider)
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)
        self.client.post(reverse('indicar_escalado', args=[Escalamiento.objects.get().pk]), {'indicacion': 'Devuelvan el cobro y cierren.'})
        entrar_soporte(self.client, self.agente)
        html = self.client.get(self.url).content.decode()
        self.assertIn('<dt>Indicación de Admin (', html)
        self.assertIn('Devuelvan el cobro y cierren.', html)
        self.assertNotIn('Esperando indicación', html)
