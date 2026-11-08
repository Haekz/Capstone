"""El profesor pide ayuda con su horario en un ticket de categoria propia (fase 7, commit 1, decidido 07-nov).

Solo el profesor abre "Horario de clases"; llega al agente habilitado en ella, con 2 dias habiles como Clases.
Desde Mi Agenda hay un enlace que abre el ticket con el tema ya elegido. Datos ficticios.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apoderados.models import Apoderado
from soporte.models import Ticket
from tests.test_apoderados import RUT, crear_agente, crear_apoderado, entrar
from tests.test_paquetes import RUT_PROFE, Escenario
from tests.test_soporte import crear_profesor
from tests.test_soporte_reportes import crear_alumno_adulto, datos

OPCION = '<option value="horario"{}>Horario de clases</option>'


class TicketHorarioTests(TestCase):

    def setUp(self):
        self.de_horario = crear_agente('10000001-9', Ticket.HORARIO)
        crear_agente('10000002-7', *Ticket.DE_USUARIOS)  # atiende lo demas, no el horario
        self.profesor = crear_profesor()

    def test_el_profesor_lo_abre_y_llega_al_agente_de_horario_en_2_dias_habiles(self):
        entrar(self.client, self.profesor.user, profesor_id=self.profesor.id_profesor)
        self.client.post(reverse('nuevo_ticket'), datos(categoria=Ticket.HORARIO, titulo='No s\u00e9 armar mi horario'))
        ticket = Ticket.objects.get()
        self.assertEqual((ticket.autor, ticket.categoria, ticket.asignado),
                         (self.profesor.user, Ticket.HORARIO, self.de_horario))
        self.assertLess(ticket.vence - timezone.now(), timedelta(days=5))  # 2 dias habiles, como Clases
        self.assertEqual(Ticket.DIAS_HABILES[Ticket.HORARIO], Ticket.DIAS_HABILES[Ticket.CLASES])

    def test_el_enlace_lo_abre_con_el_tema_elegido(self):
        entrar(self.client, self.profesor.user, profesor_id=self.profesor.id_profesor)
        r = self.client.get(reverse('nuevo_ticket'), {'categoria': Ticket.HORARIO})
        self.assertContains(r, OPCION.format(' selected'), html=True)
        self.assertContains(r, 'Pagos, clases, horario y conducta: respondemos en 2 d\u00edas h\u00e1biles.')

    def test_alumno_y_apoderado_no_lo_ven_ni_lo_abren(self):
        alumno = crear_alumno_adulto()
        apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        for user, sesion in ((alumno.user, {'alumno_id': alumno.id_alumno}),
                             (apoderado.user, {'apoderado_id': apoderado.id_apoderado})):
            with self.subTest(sesion=sesion):
                self.client.logout()
                entrar(self.client, user, **sesion)
                r = self.client.get(reverse('nuevo_ticket'), {'categoria': Ticket.HORARIO})
                self.assertNotContains(r, 'value="horario"')
                self.assertContains(r, 'Pagos, clases y conducta: respondemos')
                self.client.post(reverse('nuevo_ticket'), datos(categoria=Ticket.HORARIO))
                self.assertFalse(Ticket.objects.exists())


class EnlaceDesdeMiAgendaTests(Escenario):

    def test_mi_agenda_enlaza_al_ticket_de_horario(self):
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('panel_profesor'))
        self.assertContains(r, f'href="{reverse("nuevo_ticket")}?categoria=horario"')
