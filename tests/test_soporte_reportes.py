"""Pasos 6a y 6b: tickets que abren los usuarios (D10, D16, D18) y su conversacion.

Datos ficticios. Alumno, profesor y apoderado abren tickets y ven solo los suyos; el
alumno menor no (los abre su apoderado). Llegan al agente habilitado con su plazo, y
el detalle lo ve el agente que lo tiene o un lider. Responde y cierra solo el agente
asignado; los correos avisan sin el texto.
"""

from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Alumno, Reporte
from apoderados.models import Apoderado, Vinculo
from soporte.correo import avisar_atrasados
from soporte.models import Ticket
from soporte.tickets import abrir_reporte, agregar_mensaje
from tests.test_apoderados import RUT, User, crear_agente, crear_apoderado, entrar, entrar_soporte
from tests.test_apoderados_vinculos import crear_menor_vinculado, hace_anios
from tests.test_soporte import crear_profesor


def crear_alumno_adulto(rut='18181818-1'):
    user = User.objects.create_user(rut, rut=rut, email=f'{rut}@demo.cl', first_name='Ana Ficticia',
                                    fecha_nacimiento=hace_anios(20))
    return Alumno.objects.create(user=user, nivel_educacion='superior')


def datos(**cambios):
    return {'categoria': Ticket.PAGOS, 'titulo': 'Me cobraron dos veces',
            'descripcion': 'Pagué el plan mensual y aparece dos veces en mi cartola.', **cambios}


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

    def test_el_menor_no_abre_tickets_los_abre_su_apoderado(self):
        menor = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO), estado=Vinculo.VERIFICADO).alumno
        entrar(self.client, menor.user, alumno_id=menor.id_alumno)
        self.assertEqual(self.client.get(reverse('mis_tickets')).status_code, 302)
        self.client.post(reverse('nuevo_ticket'), datos(categoria=Ticket.CLASES))
        self.assertFalse(Ticket.objects.exists())  # D18, revisada el 01-nov
        # Tampoco por el canal viejo de reportes del portal.
        respuesta = self.client.post(reverse('enviar_reporte'), {'descripcion': 'Algo pasó'},
                                     content_type='application/json')
        self.assertFalse(respuesta.json()['success'])
        self.assertFalse(Reporte.objects.exists())

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
        self.ticket = abrir_reporte(crear_alumno_adulto().user, Ticket.CLASES, 'Profesor no llegó',
                                    'Esperé 30 minutos y nadie entró a la clase.')
        self.url = reverse('soporte_reporte', args=[self.ticket.pk])

    def test_el_agente_asignado_lo_ve_desde_su_panel(self):
        entrar_soporte(self.client, self.agente)
        self.assertContains(self.client.get(reverse('panel_soporte')), self.url)
        self.assertContains(self.client.get(self.url), 'Esperé 30 minutos')

    def test_otro_agente_no_y_el_lider_si(self):
        entrar_soporte(self.client, crear_agente('10000002-7', *Ticket.DE_USUARIOS))
        self.assertEqual(self.client.get(self.url).status_code, 404)
        entrar_soporte(self.client, crear_agente('10000003-5', lider=True))
        self.assertContains(self.client.get(self.url), 'Esperé 30 minutos')


class ConversacionTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', *Ticket.DE_USUARIOS)
        self.alumno = crear_alumno_adulto()
        self.ticket = abrir_reporte(self.alumno.user, Ticket.CLASES, 'Profesor no llegó', 'Esperé 30 minutos.')
        self.url = reverse('soporte_reporte', args=[self.ticket.pk])
        self.url_usuario = reverse('mi_ticket', args=[self.ticket.pk])

    def responder(self, **extra):
        entrar_soporte(self.client, self.agente)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, {'texto': 'Te devolvimos la clase.', **extra})

    def entrar_alumno(self):
        entrar(self.client, self.alumno.user, alumno_id=self.alumno.id_alumno)

    def test_el_agente_responde_y_el_usuario_la_lee(self):
        self.assertRedirects(self.responder(), self.url, fetch_redirect_response=False)
        correo, = mail.outbox
        self.assertEqual(correo.to, [self.alumno.user.email])
        self.assertNotIn('Te devolvimos la clase', correo.body)  # el texto solo se lee en LBWUS
        self.entrar_alumno()
        pagina = self.client.get(self.url_usuario)
        self.assertContains(pagina, 'Te devolvimos la clase.')
        self.assertContains(pagina, 'Equipo de soporte LBWUS')
        self.assertNotContains(pagina, self.agente.nombre)

    def test_cerrar_con_la_respuesta_vuelve_al_panel(self):
        self.assertRedirects(self.responder(cerrar='on'), reverse('panel_soporte'), fetch_redirect_response=False)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.CERRADO)
        self.assertIn('cerramos', mail.outbox[0].body)

    def test_el_usuario_contesta_y_se_avisa_al_agente(self):
        self.entrar_alumno()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url_usuario, {'texto': 'Gracias, era la del martes.'})
        mensaje, = self.ticket.mensajes.all()
        self.assertEqual((mensaje.de_soporte, mensaje.autor), (False, self.alumno.user))
        self.assertEqual(mail.outbox[0].to, [self.agente.user.email])

    def test_cerrado_ya_no_se_contesta(self):
        self.responder(cerrar='on')
        self.entrar_alumno()
        self.client.post(self.url_usuario, {'texto': 'Otra cosa'})
        self.assertEqual(self.ticket.mensajes.count(), 1)
        self.assertContains(self.client.get(self.url_usuario), 'Este ticket está cerrado')

    def test_responde_solo_el_agente_asignado(self):
        entrar_soporte(self.client, crear_agente('10000003-5', lider=True))
        self.client.post(self.url, {'texto': 'Respuesta del líder'})
        self.assertFalse(self.ticket.mensajes.exists())

    def test_el_ticket_ajeno_no_se_ve(self):
        otro = crear_alumno_adulto('19191919-1')
        entrar(self.client, otro.user, alumno_id=otro.id_alumno)
        self.assertEqual(self.client.get(self.url_usuario).status_code, 404)

    def test_sin_correo_se_guarda_igual(self):
        self.alumno.user.email = ''
        self.alumno.user.save(update_fields=['email'])
        self.responder()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(self.ticket.mensajes.count(), 1)


class PlazoCumplidoTests(TestCase):
    """La primera respuesta de soporte cumple el plazo (decidido el 31-oct)."""

    def setUp(self):
        self.agente = crear_agente('10000001-9', *Ticket.DE_USUARIOS)
        self.alumno = crear_alumno_adulto()
        self.ticket = abrir_reporte(self.alumno.user, Ticket.PAGOS, 'Cobro doble', 'Detalle.')
        Ticket.objects.filter(pk=self.ticket.pk).update(vence=timezone.now() - timedelta(days=10))
        self.ticket.refresh_from_db()

    def atrasados_avisados(self):
        with mock.patch('soporte.correo._toca_avisar', return_value=True):  # sin depender del dia
            return avisar_atrasados(timezone.localdate())

    def test_responder_cumple_el_plazo(self):
        self.assertTrue(self.ticket.atrasado)
        self.assertEqual(self.atrasados_avisados(), 1)
        agregar_mensaje(self.ticket, self.agente.user, 'Lo estamos revisando.', de_soporte=True)
        primera = self.ticket.respondido
        self.assertFalse(self.ticket.atrasado)
        self.assertEqual(self.atrasados_avisados(), 0)
        agregar_mensaje(self.ticket, self.agente.user, 'Listo.', de_soporte=True)
        self.assertEqual(self.ticket.respondido, primera)  # cuenta la primera

    def test_la_respuesta_del_usuario_no_lo_cumple(self):
        agregar_mensaje(self.ticket, self.alumno.user, 'Sigo esperando.', de_soporte=False)
        self.assertIsNone(self.ticket.respondido)
        self.assertTrue(self.ticket.atrasado)

    def test_mientras_espera_se_disculpa_con_quien_lo_abrio(self):
        self.atrasados_avisados()
        disculpa, = [c for c in mail.outbox if 'va con atraso' in c.subject]
        self.assertEqual(disculpa.to, [self.alumno.user.email])
        self.assertNotIn('Cobro doble', disculpa.body)  # sin datos del caso
