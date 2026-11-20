"""Escalar casos graves (D5, revisada 05-nov): el agente al lider, que lo toma; el lider a un
administrador, que decide y soporte ejecuta. Siempre con motivo. Datos ficticios."""

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from soporte.models import Asignacion, Escalamiento, Ticket
from soporte.tickets import abrir_reporte, escalar
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_campana import avisos_de
from tests.test_retiros import crear_admin, entrar_admin
from tests.test_soporte_reportes import crear_alumno_adulto

MOTIVO = 'El apoderado amenaza con demandar por el cobro.'
DESCRIPCION = 'Detalle privado que solo ve soporte.'


class Escenario(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.PAGOS)
        self.lider = crear_agente('10000003-5', Ticket.APODERADOS, lider=True)  # no atiende Pagos
        self.ticket = abrir_reporte(crear_alumno_adulto().user, Ticket.PAGOS, 'Cobro doble', DESCRIPCION)
        self.url = reverse('soporte_escalar', args=[self.ticket.pk])
        mail.outbox.clear()  # el aviso de asignacion

    def escalar_como(self, agente, motivo=MOTIVO):
        entrar_soporte(self.client, agente)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, {'motivo': motivo})


class AgenteAlLiderTests(Escenario):

    def test_el_motivo_es_obligatorio(self):
        self.assertContains(self.escalar_como(self.agente, motivo='   '), 'Escribe por qué lo escalas.')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.asignado, self.agente)
        self.assertFalse(Escalamiento.objects.exists())

    def test_pasa_al_lider_aunque_no_atienda_la_categoria(self):
        vence = self.ticket.vence
        self.assertRedirects(self.escalar_como(self.agente), reverse('panel_soporte'), fetch_redirect_response=False)
        self.ticket.refresh_from_db()
        self.assertEqual((self.ticket.asignado, self.ticket.vence), (self.lider, vence))  # el plazo no cambia
        escalamiento = Escalamiento.objects.get()
        self.assertEqual((escalamiento.destino, escalamiento.autor, escalamiento.motivo),
                         (Escalamiento.AL_LIDER, self.agente.user, MOTIVO))
        self.assertEqual(Asignacion.objects.first().autor, self.agente.user)
        correo, = mail.outbox
        self.assertEqual((correo.to, correo.subject), ([self.lider.user.email],
                                                        f'Ticket #{self.ticket.pk} escalado a ti - LBWUS'))
        self.assertNotIn('demandar', correo.body)  # el motivo solo se lee en LBWUS

    def test_el_agente_deja_de_verlo_y_el_lider_lo_atiende(self):
        self.escalar_como(self.agente)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        entrar_soporte(self.client, self.lider)
        self.assertContains(self.client.get(reverse('panel_soporte')), 'Escalado')
        self.assertContains(self.client.get(self.url), MOTIVO)
        self.client.post(reverse('soporte_reporte', args=[self.ticket.pk]), {'texto': 'Lo vemos con legal.'})
        self.assertTrue(self.ticket.mensajes.filter(de_soporte=True).exists())

    def test_la_campana_del_lider_no_lo_cuenta_como_sin_agente(self):
        self.escalar_como(self.agente)
        titulos = [aviso.titulo for aviso in avisos_de(soporte_id=self.lider.id_agente)]
        self.assertFalse([titulo for titulo in titulos if 'sin agente' in titulo])

    def test_sin_lider_activo_no_se_mueve(self):
        self.lider.user.is_active = False
        self.lider.user.save(update_fields=['is_active'])
        self.assertContains(self.escalar_como(self.agente), 'No hay un líder de soporte activo')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.asignado, self.agente)

    def test_otro_agente_no_escala_un_ticket_ajeno(self):
        entrar_soporte(self.client, crear_agente('10000002-7', Ticket.PAGOS))
        self.assertEqual(self.client.get(self.url).status_code, 404)


class LiderAlAdminTests(Escenario):

    def setUp(self):
        super().setUp()
        self.admin, self.tutor = crear_admin()
        self.admin.email = 'admin@example.com'
        self.admin.save(update_fields=['email'])

    def test_el_ticket_sigue_en_soporte_y_se_avisa_a_los_admins(self):
        self.assertRedirects(self.escalar_como(self.lider), reverse('panel_soporte'), fetch_redirect_response=False)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.asignado, self.agente)
        self.assertEqual(Escalamiento.objects.get().destino, Escalamiento.AL_ADMIN)
        correo, = mail.outbox
        self.assertEqual(correo.to, ['admin@example.com'])
        self.assertNotIn('demandar', correo.body)
        [aviso] = avisos_de(admin_id=self.tutor.id_tutor)
        self.assertEqual((aviso.titulo, aviso.urgente), ('1 caso escalado por soporte', True))

    def test_el_admin_ve_el_motivo_pero_no_el_detalle_del_ticket(self):
        self.escalar_como(self.lider)
        entrar_admin(self.client, self.admin, self.tutor)
        pagina = self.client.get(reverse('casos_escalados'))
        self.assertContains(pagina, MOTIVO)
        self.assertContains(pagina, 'Cobro doble')
        self.assertNotContains(pagina, DESCRIPCION)

    def test_no_se_escala_de_nuevo_mientras_espera(self):
        self.escalar_como(self.lider)
        self.assertContains(self.client.get(self.url), 'Ya está escalado a un administrador')
        with self.assertRaisesMessage(ValidationError, 'espera la indicación'):
            escalar(self.ticket, self.lider, 'Otra vez')

    def test_el_admin_indica_y_soporte_la_lee(self):
        self.escalar_como(self.lider)
        escalamiento = Escalamiento.objects.get()
        entrar_admin(self.client, self.admin, self.tutor)
        url = reverse('indicar_escalado', args=[escalamiento.pk])
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {'indicacion': 'Devuelvan el cobro y cierren.'})
        escalamiento.refresh_from_db()
        self.assertEqual((escalamiento.indicado_por, escalamiento.pendiente), (self.admin, False))
        self.assertEqual(sorted(c.to[0] for c in mail.outbox), sorted([self.lider.user.email, self.agente.user.email]))
        self.assertEqual(avisos_de(admin_id=self.tutor.id_tutor), [])
        entrar_soporte(self.client, self.agente)
        self.assertContains(self.client.get(self.url), 'Devuelvan el cobro y cierren.')

    def test_la_indicacion_es_obligatoria_y_se_responde_una_vez(self):
        self.escalar_como(self.lider)
        escalamiento = Escalamiento.objects.get()
        entrar_admin(self.client, self.admin, self.tutor)
        url = reverse('indicar_escalado', args=[escalamiento.pk])
        self.assertContains(self.client.post(url, {'indicacion': ' '}, follow=True), 'Escribe tu indicación para soporte.')
        self.client.post(url, {'indicacion': 'Primera.'})
        self.assertContains(self.client.post(url, {'indicacion': 'Segunda.'}, follow=True), 'ya tiene una indicación')
        escalamiento.refresh_from_db()
        self.assertEqual(escalamiento.indicacion, 'Primera.')

    def test_soporte_no_entra_a_la_bandeja_del_admin(self):
        entrar_soporte(self.client, self.lider)
        self.assertNotContains(self.client.get(reverse('casos_escalados')), MOTIVO, status_code=302)
