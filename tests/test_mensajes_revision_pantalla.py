"""Pantalla del lider para revisar conversaciones reportadas (paso C1f-2). Datos ficticios."""

from dateutil.relativedelta import relativedelta
from django.urls import reverse
from django.utils import timezone

from mensajes import servicio
from mensajes.models import Conversacion, DecisionRetencion
from soporte.models import Ticket
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_paquetes import Escenario, dar_paquete
from tests.test_retiros import crear_admin, entrar_admin

DATOS = {'accion': 'conservar', 'motivo': DecisionRetencion.RECLAMACION, 'alcance': 'Los mensajes del 28-oct.',
         'fundamento': 'Posible reclamo del apoderado.', 'termino': 'Cuando se resuelva el reclamo.'}


def fecha(dia):
    return f'{dia:%d-%m-%Y}'


class PantallaRevisionTests(Escenario):

    def setUp(self):
        self.hoy = timezone.localdate()
        self.lider = crear_agente('10000002-7', Ticket.CONDUCTA, lider=True)
        self.agente = crear_agente('10000001-9', Ticket.CONDUCTA)
        dar_paquete(self.ana, self.profe)
        self.conversacion = servicio.abrir_conversacion(self.ana, self.profe)
        self.reporte = servicio.reportar(self.profe.user, self.conversacion, 'Me incomoda.')
        self.cerrar_ticket()
        self.lista = reverse('mensajes_revision')
        self.detalle = reverse('mensajes_revision_detalle', args=[self.conversacion.pk])
        entrar_soporte(self.client, self.lider)

    def cerrar_ticket(self):
        Ticket.objects.filter(pk=self.reporte.ticket_id).update(estado=Ticket.CERRADO, cerrado=timezone.now())

    # --- quien entra ---

    def test_un_agente_no_entra_ni_decide(self):
        entrar_soporte(self.client, self.agente)
        self.assertRedirects(self.client.get(self.lista), reverse('panel_soporte'), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(self.detalle), reverse('panel_soporte'), fetch_redirect_response=False)
        self.client.post(self.detalle, {'accion': 'liberar'})
        self.assertFalse(DecisionRetencion.objects.exists())

    def test_el_administrador_no_entra(self):
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)
        self.assertNotEqual(self.client.get(self.lista).status_code, 200)
        self.assertNotEqual(self.client.get(self.detalle).status_code, 200)

    def test_sin_sesion_no_entra(self):
        self.client.logout()
        self.assertNotEqual(self.client.get(self.lista).status_code, 200)

    # --- lista ---

    def test_la_lista_muestra_la_pendiente_solo_con_nombres_de_pila(self):
        r = self.client.get(self.lista)
        self.assertContains(r, 'Esperan tu decisión (1)')
        self.assertContains(r, f'{self.ana.user.first_name} y {self.profe.user.first_name} (profesor)')
        self.assertContains(r, self.detalle)
        for privado in (self.ana.user.email, self.ana.user.rut, self.profe.user.email, self.profe.user.rut):
            self.assertNotContains(r, privado)

    def test_con_el_ticket_abierto_todavia_no_esta_en_la_lista(self):
        Ticket.objects.update(estado=Ticket.ABIERTO, cerrado=None)
        self.assertContains(self.client.get(self.lista), 'Esperan tu decisión (0)')

    # --- detalle ---

    def test_el_detalle_de_una_pendiente_ofrece_decidir_y_leer_con_registro(self):
        r = self.client.get(self.detalle)
        self.assertContains(r, 'Liberar conversación')
        self.assertContains(r, 'Registrar retención')
        self.assertContains(r, reverse('mensajes_soporte_leer', args=[self.reporte.ticket_id]))
        self.assertContains(r, 'queda registrado quién la abre')

    def test_el_detalle_sin_decision_pendiente_no_ofrece_decidir(self):
        Ticket.objects.update(estado=Ticket.ABIERTO, cerrado=None)
        r = self.client.get(self.detalle)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Registrar retención')

    def test_una_conversacion_sin_reporte_da_404(self):
        dar_paquete(self.ana, self.otro)
        sin_reporte = servicio.abrir_conversacion(self.ana, self.otro)
        self.assertEqual(self.client.get(reverse('mensajes_revision_detalle', args=[sin_reporte.pk])).status_code, 404)

    # --- decidir ---

    def test_liberar(self):
        r = self.client.post(self.detalle, {'accion': 'liberar'}, follow=True)
        decision = DecisionRetencion.objects.get()
        self.assertEqual((decision.decision, decision.decidida_por), (DecisionRetencion.LIBERAR, self.lider))
        self.assertContains(r, 'Conversación liberada')
        self.assertContains(r, 'Esperan tu decisión (0)')

    def test_conservar_registra_y_aparece_en_conservadas(self):
        r = self.client.post(self.detalle, DATOS, follow=True)
        decision = DecisionRetencion.objects.get()
        self.assertEqual((decision.motivo, decision.alcance, decision.decidida_por),
                         (DecisionRetencion.RECLAMACION, DATOS['alcance'], self.lider))
        self.assertContains(r, 'Retención excepcional registrada')
        self.assertContains(r, 'Conservadas como retención excepcional (1)')
        self.assertContains(r, 'Reclamación o defensa de derechos')
        self.assertContains(r, fecha(self.hoy + relativedelta(months=6)))

    def test_conservar_incompleto_muestra_el_error_y_no_guarda(self):
        r = self.client.post(self.detalle, {**DATOS, 'termino': ''})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Condición de término')
        self.assertContains(r, 'role="alert"')
        self.assertContains(r, DATOS['alcance'])  # no pierde lo que ya escribio
        self.assertFalse(DecisionRetencion.objects.exists())

    def test_el_historial_muestra_quien_decidio(self):
        self.client.post(self.detalle, {'accion': 'liberar'})
        r = self.client.get(self.detalle)
        self.assertContains(r, 'Historial de decisiones')
        self.assertContains(r, self.lider.nombre)
        self.assertContains(r, 'Liberar')

    # --- menu ---

    def test_el_menu_con_el_acceso_es_solo_del_lider(self):
        self.assertContains(self.client.get(reverse('panel_soporte')), 'id="nav-revision"')
        entrar_soporte(self.client, self.agente)
        self.assertNotContains(self.client.get(reverse('panel_soporte')), 'id="nav-revision"')

    def test_la_pantalla_de_lectura_tambien_lo_muestra(self):
        r = self.client.get(reverse('mensajes_soporte_leer', args=[self.reporte.ticket_id]))
        self.assertContains(r, 'id="nav-revision"')
