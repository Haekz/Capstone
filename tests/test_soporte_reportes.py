"""Paso 6a: tickets que abren los usuarios (D10, D16, D18).

Datos ficticios. Alumno, profesor y apoderado abren tickets y ven solo los suyos; el
alumno menor solo de clases y tecnicos. Llegan al agente habilitado con su plazo, y
el detalle lo ve el agente que lo tiene o un lider.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Alumno
from apoderados.models import Apoderado, Vinculo
from soporte.models import Ticket
from soporte.tickets import abrir_reporte
from tests.test_apoderados import RUT, User, crear_agente, crear_apoderado, entrar, entrar_soporte
from tests.test_apoderados_vinculos import crear_menor_vinculado, hace_anios
from tests.test_soporte import crear_profesor


def crear_alumno_adulto(rut='18181818-1'):
    user = User.objects.create_user(rut, rut=rut, email=f'{rut}@demo.cl', first_name='Ana Ficticia',
                                    fecha_nacimiento=hace_anios(20))
    return Alumno.objects.create(user=user, nivel_educacion='superior')


def datos(**cambios):
    return {'categoria': Ticket.PAGOS, 'titulo': 'Me cobraron dos veces',
            'descripcion': 'Pagu\u00e9 el plan mensual y aparece dos veces en mi cartola.', **cambios}


class AbrirTicketTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', *Ticket.DE_USUARIOS)
        self.alumno = crear_alumno_adulto()
        entrar(self.client, self.alumno.user, alumno_id=self.alumno.id_alumno)

    def test_lo_abre_y_llega_al_agente_con_su_plazo(self):
        respuesta = self.client.post(reverse('nuevo_ticket'), datos())
        self.assertRedirects(respuesta, reverse('mis_tickets'), fetch_redirect_response=False)
        ticket = Ticket.objects.get()
        self.assertEqual((ticket.autor, ticket.categoria, ticket.asignado), (self.alumno.user, Ticket.PAGOS, self.agente))
        self.assertEqual(ticket.asunto, 'Me cobraron dos veces')
        self.assertLess(ticket.vence - timezone.now(), timedelta(days=5))  # 2 dias habiles (D4)
        self.assertContains(self.client.get(reverse('mis_tickets')), 'Me cobraron dos veces')

    def test_puede_tener_varios_abiertos(self):
        self.client.post(reverse('nuevo_ticket'), datos())
        self.client.post(reverse('nuevo_ticket'), datos(categoria=Ticket.TECNICO, titulo='No carga el video'))
        self.assertEqual(Ticket.objects.filter(autor=self.alumno.user, estado=Ticket.ABIERTO).count(), 2)

    def test_solo_ve_sus_tickets(self):
        otro = crear_alumno_adulto('19191919-1')
        abrir_reporte(otro.user, Ticket.CLASES, 'Ticket ajeno', 'Algo')
        self.assertNotContains(self.client.get(reverse('mis_tickets')), 'Ticket ajeno')

    def test_profesor_y_apoderado_tambien_abren(self):
        profesor = crear_profesor()
        apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        for user, sesion in ((profesor.user, {'profesor_id': profesor.id_profesor}),
                             (apoderado.user, {'apoderado_id': apoderado.id_apoderado})):
            with self.subTest(sesion=sesion):
                self.client.logout()
                entrar(self.client, user, **sesion)
                self.client.post(reverse('nuevo_ticket'), datos())
                self.assertTrue(Ticket.objects.filter(autor=user).exists())


class PermisosTests(TestCase):

    def test_el_menor_solo_abre_de_clases_y_tecnicos(self):
        menor = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO), estado=Vinculo.VERIFICADO).alumno
        entrar(self.client, menor.user, alumno_id=menor.id_alumno)
        self.client.post(reverse('nuevo_ticket'), datos(categoria=Ticket.PAGOS))
        self.assertFalse(Ticket.objects.exists())  # los de pagos los abre su apoderado (D18)
        self.client.post(reverse('nuevo_ticket'), datos(categoria=Ticket.CLASES))
        self.assertEqual(Ticket.objects.get().categoria, Ticket.CLASES)

    def test_no_se_abren_verificaciones_a_mano(self):
        alumno = crear_alumno_adulto()
        entrar(self.client, alumno.user, alumno_id=alumno.id_alumno)
        self.client.post(reverse('nuevo_ticket'), datos(categoria=Ticket.APODERADOS))
        self.assertFalse(Ticket.objects.exists())

    def test_anonimo_al_login_y_soporte_a_su_panel(self):
        self.assertRedirects(self.client.get(reverse('mis_tickets')), reverse('login'), fetch_redirect_response=False)
        entrar_soporte(self.client, crear_agente('10000001-9'))
        self.assertRedirects(self.client.get(reverse('nuevo_ticket')), reverse('panel_soporte'),
                             fetch_redirect_response=False)

    def test_el_menu_muestra_ayuda_solo_a_quien_abre_tickets(self):
        alumno = crear_alumno_adulto()
        entrar(self.client, alumno.user, alumno_id=alumno.id_alumno)
        self.assertContains(self.client.get(reverse('home')), reverse('mis_tickets'))
        self.client.logout()
        self.assertNotContains(self.client.get(reverse('home')), reverse('mis_tickets'))


class DetalleEnSoporteTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', *Ticket.DE_USUARIOS)
        self.ticket = abrir_reporte(crear_alumno_adulto().user, Ticket.CLASES, 'Profesor no lleg\u00f3',
                                    'Esper\u00e9 30 minutos y nadie entr\u00f3 a la clase.')
        self.url = reverse('soporte_reporte', args=[self.ticket.pk])

    def test_el_agente_asignado_lo_ve_desde_su_panel(self):
        entrar_soporte(self.client, self.agente)
        self.assertContains(self.client.get(reverse('panel_soporte')), self.url)
        self.assertContains(self.client.get(self.url), 'Esper\u00e9 30 minutos')

    def test_otro_agente_no_y_el_lider_si(self):
        entrar_soporte(self.client, crear_agente('10000002-7', *Ticket.DE_USUARIOS))
        self.assertEqual(self.client.get(self.url).status_code, 404)
        entrar_soporte(self.client, crear_agente('10000003-5', lider=True))
        self.assertContains(self.client.get(self.url), 'Esper\u00e9 30 minutos')
