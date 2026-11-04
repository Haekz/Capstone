"""Reportar una conversacion y lectura de soporte (paso C1c, decidido 02-nov). Datos ficticios."""

from django.core import mail
from django.urls import reverse

from apoderados.models import Apoderado
from mensajes import servicio
from mensajes.models import AccesoConversacion, Conversacion, ReporteConversacion
from soporte.models import Ticket
from soporte.tickets import abrir_reporte, cerrar_tickets
from tests.test_apoderados import RUT, crear_agente, crear_apoderado, entrar, entrar_soporte
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA, RUT_PROFE, Escenario, dar_paquete
from tests.test_retiros import crear_admin

SECRETO = 'texto privado de la conversacion'
RUT_MENOR = '77777777-7'


class ReportarTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)
        self.agente = crear_agente('10000001-9', Ticket.CONDUCTA)
        self.lider = crear_agente('10000003-5', lider=True)
        self.conversacion = servicio.abrir_conversacion(self.ana, self.profe)
        servicio.enviar(self.ana.user, self.conversacion, SECRETO)
        self.url = reverse('mensajes_reportar', args=[self.conversacion.pk])

    def reportar(self, rut=RUT_ANA, texto='Me incomoda lo que escribe.'):
        self.entrar(rut)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, {'descripcion': texto})

    def test_el_formulario_avisa_que_soporte_podra_leerla(self):
        self.entrar(RUT_ANA)
        self.assertContains(self.client.get(self.url), 'Soporte podrá leer esta conversación')

    def test_el_alumno_reporta_y_se_abre_un_ticket_de_conducta_asignado(self):
        r = self.reportar()
        self.assertRedirects(r, reverse('mis_tickets'), fetch_redirect_response=False)
        reporte = ReporteConversacion.objects.get()
        ticket = reporte.ticket
        self.assertEqual((reporte.conversacion, reporte.reportado_por), (self.conversacion, self.ana.user))
        self.assertEqual((ticket.categoria, ticket.autor, ticket.asignado), (Ticket.CONDUCTA, self.ana.user, self.agente))
        self.assertEqual(ticket.titulo, f'Conversación #{self.conversacion.pk} reportada')
        self.assertEqual(ticket.descripcion, 'Me incomoda lo que escribe.')

    def test_los_lideres_se_enteran_al_instante(self):
        self.reportar()
        self.assertTrue(any(c.subject.startswith('Reporte de conducta') and c.to == [self.lider.user.email]
                            for c in mail.outbox))

    def test_el_profesor_tambien_puede_reportar(self):
        self.reportar(RUT_PROFE)
        self.assertEqual(ReporteConversacion.objects.get().reportado_por, self.profe.user)

    def test_el_texto_de_la_conversacion_no_se_copia_al_ticket(self):
        self.reportar()
        ticket = Ticket.objects.get()
        self.assertNotIn(SECRETO, ticket.titulo + ticket.descripcion)

    def test_un_solo_reporte_abierto_por_persona(self):
        self.reportar()
        r = self.reportar()
        self.assertContains(r, 'Ya reportaste esta conversación')
        self.assertEqual(ReporteConversacion.objects.count(), 1)

    def test_con_el_ticket_cerrado_puede_volver_a_reportar_y_el_otro_lado_reporta_aparte(self):
        self.reportar()
        cerrar_tickets(Ticket.objects.all())
        self.reportar()
        self.reportar(RUT_PROFE)
        self.assertEqual(ReporteConversacion.objects.count(), 3)

    def test_sin_descripcion_no_se_reporta(self):
        self.reportar(texto='')
        self.assertFalse(ReporteConversacion.objects.exists())

    def test_quien_no_participa_no_puede_ni_ver_el_formulario(self):
        dar_paquete(self.beto, self.otro)
        self.entrar(self.beto.user.rut)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, {'descripcion': 'x'}).status_code, 404)
        self.assertFalse(ReporteConversacion.objects.exists())

    def test_el_menor_no_reporta(self):
        vinculo = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO), rut=RUT_MENOR)
        ajena = Conversacion.objects.create(alumno=vinculo.alumno, profesor=self.profe, cliente=vinculo.alumno.user)
        entrar(self.client, vinculo.alumno.user, alumno_id=vinculo.alumno.id_alumno)
        r = self.client.post(reverse('mensajes_reportar', args=[ajena.pk]), {'descripcion': 'x'})
        self.assertNotEqual(r.status_code, 200)
        self.assertFalse(ReporteConversacion.objects.exists())

    def test_ambos_buzones_ofrecen_reportar(self):
        self.entrar(RUT_PROFE)
        self.assertContains(self.client.get(reverse('panel_profesor'), {'c': self.conversacion.pk}), self.url)
        self.entrar(RUT_ANA)
        self.assertContains(self.client.get(reverse('alumno_pag1'), {'c': self.conversacion.pk}), self.url)


class LecturaDeSoporteTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)
        self.agente = crear_agente('10000001-9', Ticket.CONDUCTA)
        self.lider = crear_agente('10000003-5', lider=True)
        self.conversacion = servicio.abrir_conversacion(self.ana, self.profe)
        servicio.enviar(self.ana.user, self.conversacion, SECRETO)
        self.reporte = servicio.reportar(self.ana.user, self.conversacion, 'Me incomoda.')
        self.url = reverse('mensajes_soporte_leer', args=[self.reporte.ticket_id])

    def accesos(self):
        return list(AccesoConversacion.objects.values_list('agente', flat=True))

    def test_el_agente_asignado_la_lee_y_queda_registrado(self):
        entrar_soporte(self.client, self.agente)
        r = self.client.get(self.url)
        self.assertContains(r, SECRETO)
        self.assertContains(r, 'Tu lectura queda registrada')
        self.assertEqual(self.accesos(), [self.agente.pk])

    def test_cada_lectura_deja_su_registro_y_se_muestra(self):
        entrar_soporte(self.client, self.agente)
        self.client.get(self.url)
        r = self.client.get(self.url)
        self.assertEqual(self.accesos(), [self.agente.pk, self.agente.pk])
        self.assertEqual(len(r.context['accesos']), 2)

    def test_el_lider_tambien_y_queda_con_su_nombre(self):
        entrar_soporte(self.client, self.lider)
        self.assertContains(self.client.get(self.url), SECRETO)
        self.assertEqual(self.accesos(), [self.lider.pk])

    def test_otro_agente_no_la_ve_ni_deja_registro(self):
        entrar_soporte(self.client, crear_agente('10000002-7', Ticket.CONDUCTA))
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.accesos(), [])

    def test_con_el_ticket_cerrado_el_agente_ya_no_la_ve_pero_el_lider_si(self):
        cerrar_tickets(Ticket.objects.all())
        entrar_soporte(self.client, self.agente)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        entrar_soporte(self.client, self.lider)
        self.assertContains(self.client.get(self.url), SECRETO)

    def test_el_administrador_no_puede_leerla(self):
        admin, _tutor = crear_admin()
        entrar(self.client, admin)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.accesos(), [])

    def test_los_participantes_tampoco_por_esta_via(self):
        for rut in (RUT_ANA, RUT_PROFE):
            self.entrar(rut)
            self.assertNotEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.accesos(), [])

    def test_un_ticket_que_no_es_de_conversacion_no_sirve(self):
        normal = abrir_reporte(self.ana.user, Ticket.CONDUCTA, 'Otra cosa', 'No es una conversacion')
        entrar_soporte(self.client, self.lider)
        self.assertEqual(self.client.get(reverse('mensajes_soporte_leer', args=[normal.pk])).status_code, 404)

    def test_el_ticket_de_soporte_ofrece_leerla_solo_si_es_de_conversacion(self):
        normal = abrir_reporte(self.ana.user, Ticket.CONDUCTA, 'Otra cosa', 'No es una conversacion')
        entrar_soporte(self.client, self.lider)
        self.assertContains(self.client.get(reverse('soporte_reporte', args=[self.reporte.ticket_id])), self.url)
        self.assertNotContains(self.client.get(reverse('soporte_reporte', args=[normal.pk])), 'Leer la conversación')
