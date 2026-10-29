"""Soporte 2b-1: equipo, tickets de verificaciones con documentos y permisos.

Datos ficticios. Cubre la asignacion automatica (menor carga, categorias, sin
agentes), la apertura y el cierre de tickets en cada cambio de estado, quien ve
documentos y decide (solo el agente con el ticket; ni el admin ni el lider sin
ticket), la reasignacion del lider y el comando crear_soporte.
"""

import importlib
import tempfile
from io import StringIO
from unittest import mock

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from alumnos.models import Especialidad, Profesor
from apoderados.models import AccesoDocumento, Apoderado, Documento, Vinculo
from soporte.models import AgenteSoporte, Asignacion, Habilitacion, Ticket
from soporte.tickets import abrir_ticket
from tests.test_apoderados import CLAVE, RUT, adjuntar, crear_agente, crear_apoderado, entrar, entrar_soporte
from tests.test_apoderados_documentos import crear_admin
from tests.test_apoderados_vinculos import crear_menor_vinculado
from user_profesor import titulo

User = get_user_model()
PDF = b'%PDF-1.4 titulo ficticio'


def crear_profesor(rut='22222222-2'):
    user = User.objects.create_user(rut, rut=rut, password=CLAVE, first_name='Pedro Ficticio')
    return Profesor.objects.create(user=user, especialidad=Especialidad.objects.create(nombre='Mate'))


class AsignacionTests(TestCase):

    def test_va_al_agente_habilitado_con_menos_tickets_abiertos(self):
        cargado = crear_agente('10000001-9', Ticket.APODERADOS)
        libre = crear_agente('10000002-7', Ticket.APODERADOS)
        abrir_ticket(Ticket.APODERADOS, apoderado=crear_apoderado('11111111-1', Apoderado.REVISION_PENDIENTE))
        self.assertEqual(Ticket.objects.get().asignado, cargado)  # empate: el mas antiguo

        apoderado = crear_apoderado(RUT, Apoderado.CORREO_PENDIENTE)
        apoderado.confirmar_correo()

        ticket = apoderado.tickets.get()
        self.assertEqual(ticket.asignado, libre)
        self.assertEqual(ticket.asignaciones.get().autor, None)  # automatica

    def test_los_tickets_cerrados_no_cuentan_como_carga(self):
        primero = crear_agente('10000001-9', Ticket.APODERADOS)
        crear_agente('10000002-7', Ticket.APODERADOS)
        abrir_ticket(Ticket.APODERADOS, apoderado=crear_apoderado('11111111-1', Apoderado.REVISION_PENDIENTE))
        Ticket.objects.update(estado=Ticket.CERRADO)
        abrir_ticket(Ticket.APODERADOS, apoderado=crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE))
        self.assertEqual(Ticket.objects.get(estado=Ticket.ABIERTO).asignado, primero)

    def test_no_recibe_quien_no_atiende_la_categoria_o_tiene_la_cuenta_desactivada(self):
        crear_agente('10000001-9', Ticket.TITULOS)
        inactivo = crear_agente('10000002-7', Ticket.APODERADOS)
        User.objects.filter(pk=inactivo.user.pk).update(is_active=False)

        abrir_ticket(Ticket.APODERADOS, apoderado=crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE))

        ticket = Ticket.objects.get()
        self.assertIsNone(ticket.asignado)  # queda para el lider
        self.assertFalse(Asignacion.objects.exists())

    def test_no_duplica_el_ticket_abierto(self):
        apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        abrir_ticket(Ticket.APODERADOS, apoderado=apoderado)
        abrir_ticket(Ticket.APODERADOS, apoderado=apoderado)
        self.assertEqual(apoderado.tickets.count(), 1)


class CicloDelTicketTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.APODERADOS, Ticket.TITULOS)
        entrar_soporte(self.client, self.agente)

    def test_el_vinculo_abre_ticket_solo_con_la_identidad_verificada(self):
        apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        abrir_ticket(Ticket.APODERADOS, apoderado=apoderado)
        vinculo = crear_menor_vinculado(apoderado, estado=Vinculo.PENDIENTE)
        vinculo.abrir_ticket_si_revisable()
        self.assertFalse(vinculo.tickets.exists())  # aun no hay nada que decidir

        adjuntar(Documento.CARNET_FRENTE, apoderado=apoderado)
        adjuntar(Documento.CARNET_REVERSO, apoderado=apoderado)
        self.client.post(reverse('apoderado_revisar', args=[apoderado.pk]), {'decision': 'aprobar', 'rut_coincide': 'on'})

        self.assertEqual(apoderado.tickets.get().estado, Ticket.CERRADO)
        self.assertEqual(vinculo.tickets.get(estado=Ticket.ABIERTO).asignado, self.agente)

    def test_revocar_un_vinculo_pendiente_cierra_su_ticket(self):
        vinculo = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO), estado=Vinculo.PENDIENTE)
        vinculo.abrir_ticket_si_revisable()
        vinculo.revocar(self.agente.user, 'Disputa ficticia')
        self.assertEqual(vinculo.tickets.get().estado, Ticket.CERRADO)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_el_titulo_abre_ticket_al_subirlo_y_lo_cierra_al_resolverlo(self):
        profesor = crear_profesor()
        titulo.subir(profesor, SimpleUploadedFile('titulo.pdf', PDF))
        ticket = profesor.tickets.get()
        self.assertEqual((ticket.categoria, ticket.asignado), (Ticket.TITULOS, self.agente))

        self.client.post(reverse('resolver_titulo', args=[profesor.pk]), {'decision': 'aprobar'})
        profesor.refresh_from_db()
        ticket.refresh_from_db()
        self.assertTrue(profesor.puede_hacer_clases)
        self.assertEqual(ticket.estado, Ticket.CERRADO)
        self.assertIsNotNone(ticket.cerrado)

    def test_lo_pendiente_al_desplegar_queda_como_ticket_sin_asignar(self):
        apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        vinculo = crear_menor_vinculado(crear_apoderado('15151515-1', Apoderado.VERIFICADO), estado=Vinculo.PENDIENTE)
        sin_verificar = crear_apoderado('13131313-1', Apoderado.REVISION_PENDIENTE)
        crear_menor_vinculado(sin_verificar, rut='14141414-1', estado=Vinculo.PENDIENTE)  # aun no se revisa
        migracion = importlib.import_module('soporte.migrations.0002_tickets_de_pendientes')

        migracion.abrir_tickets_pendientes(apps, None)

        abiertos = Ticket.objects.filter(estado=Ticket.ABIERTO, asignado__isnull=True)
        self.assertEqual(set(abiertos.values_list('apoderado', 'vinculo')),
                         {(apoderado.pk, None), (sin_verificar.pk, None), (None, vinculo.pk)})


class PermisosTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.APODERADOS, Ticket.TITULOS)
        self.otro = crear_agente('10000002-7', Ticket.APODERADOS, Ticket.TITULOS)
        self.lider = crear_agente('10000003-5', Ticket.APODERADOS, lider=True)
        self.apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        self.carnet = adjuntar(Documento.CARNET_FRENTE, apoderado=self.apoderado)
        adjuntar(Documento.CARNET_REVERSO, apoderado=self.apoderado)
        abrir_ticket(Ticket.APODERADOS, apoderado=self.apoderado)  # al primero: todos sin carga
        self.ticket = self.apoderado.tickets.get()
        self.url_documento = reverse('apoderado_documento', args=[self.carnet.pk])

    def aprobar(self):
        respuesta = self.client.post(reverse('apoderado_revisar', args=[self.apoderado.pk]),
                                     {'decision': 'aprobar', 'rut_coincide': 'on'})
        self.apoderado.refresh_from_db()
        return respuesta

    def test_el_agente_con_el_ticket_ve_el_documento_y_decide(self):
        self.assertEqual(self.ticket.asignado, self.agente)
        entrar_soporte(self.client, self.agente)
        self.assertContains(self.client.get(reverse('apoderados_revision')), self.apoderado.nombre)
        respuesta = self.client.get(self.url_documento)
        self.assertEqual((respuesta.status_code, respuesta['Content-Type']), (200, 'image/jpeg'))
        self.assertEqual(AccesoDocumento.objects.get().administrador, self.agente.user)

        self.aprobar()
        self.assertEqual(self.apoderado.estado, Apoderado.VERIFICADO)

    def test_otro_agente_y_el_lider_sin_el_ticket_no_ven_el_documento_ni_deciden(self):
        for agente in (self.otro, self.lider):
            with self.subTest(agente.cargo):
                entrar_soporte(self.client, agente)
                self.assertNotContains(self.client.get(reverse('apoderados_revision')), self.apoderado.user.rut)
                self.assertEqual(self.client.get(self.url_documento).status_code, 404)
                self.assertEqual(self.aprobar().status_code, 404)
                self.assertEqual(self.apoderado.estado, Apoderado.REVISION_PENDIENTE)
        self.assertFalse(AccesoDocumento.objects.exists())

    def test_el_admin_ya_no_entra_a_las_revisiones(self):
        admin, tutor = crear_admin()
        entrar(self.client, admin, admin_id=tutor.id_tutor)
        profesor = crear_profesor()
        for url in (reverse('apoderados_revision'), self.url_documento, reverse('titulos_adm'),
                    reverse('ver_titulo', args=[profesor.pk])):
            with self.subTest(url):
                self.assertRedirects(self.client.get(url), reverse('dashboard_admin'), fetch_redirect_response=False)
        self.assertRedirects(self.aprobar(), reverse('dashboard_admin'), fetch_redirect_response=False)
        self.assertEqual(self.apoderado.estado, Apoderado.REVISION_PENDIENTE)
        self.assertNotContains(self.client.get(reverse('dashboard_admin')), reverse('apoderados_revision'))

    def test_sin_la_categoria_el_agente_pierde_el_ticket(self):
        Habilitacion.objects.filter(agente=self.agente, categoria=Ticket.APODERADOS).delete()
        entrar_soporte(self.client, self.agente)
        self.assertEqual(self.client.get(self.url_documento).status_code, 404)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_el_titulo_solo_lo_ve_y_resuelve_el_agente_con_el_ticket(self):
        profesor = crear_profesor()
        titulo.subir(profesor, SimpleUploadedFile('titulo.pdf', PDF))
        asignado = profesor.tickets.get().asignado
        ajeno = self.otro if asignado == self.agente else self.agente

        entrar_soporte(self.client, ajeno)
        self.assertEqual(self.client.get(reverse('ver_titulo', args=[profesor.pk])).status_code, 404)
        self.client.post(reverse('resolver_titulo', args=[profesor.pk]), {'decision': 'aprobar'})
        profesor.refresh_from_db()
        self.assertEqual(profesor.titulo_estado, Profesor.TITULO_EN_REVISION)

        entrar_soporte(self.client, asignado)
        self.assertEqual(self.client.get(reverse('ver_titulo', args=[profesor.pk])).status_code, 200)


class LiderTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.APODERADOS)
        self.otro = crear_agente('10000002-7', Ticket.APODERADOS)
        self.lider = crear_agente('10000003-5', lider=True)  # supervisa sin recibir tickets
        self.solo_titulos = crear_agente('10000004-3', Ticket.TITULOS)
        self.apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        abrir_ticket(Ticket.APODERADOS, apoderado=self.apoderado)
        self.ticket = self.apoderado.tickets.get()
        self.url = reverse('soporte_reasignar', args=[self.ticket.pk])

    def test_el_lider_ve_todos_los_tickets_y_reasigna_con_registro(self):
        entrar_soporte(self.client, self.lider)
        self.assertContains(self.client.get(reverse('panel_soporte')), self.ticket.asunto)

        self.client.post(self.url, {'agente': self.otro.pk})

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.asignado, self.otro)
        ultima = self.ticket.asignaciones.first()
        self.assertEqual((ultima.agente, ultima.autor), (self.otro, self.lider.user))

    def test_no_reasigna_a_quien_no_atiende_la_categoria(self):
        entrar_soporte(self.client, self.lider)
        for agente in (self.solo_titulos.pk, 999, 'x'):
            with self.subTest(agente):
                self.client.post(self.url, {'agente': agente})
                self.ticket.refresh_from_db()
                self.assertEqual(self.ticket.asignado, self.agente)

    def test_un_agente_no_reasigna_ni_revoca(self):
        vinculo = crear_menor_vinculado(crear_apoderado('15151515-1', Apoderado.VERIFICADO))
        entrar_soporte(self.client, self.agente)
        self.assertRedirects(self.client.post(self.url, {'agente': self.otro.pk}), reverse('panel_soporte'))
        self.assertRedirects(self.client.get(reverse('apoderados_revocar_vinculo', args=[vinculo.pk])),
                             reverse('panel_soporte'))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.asignado, self.agente)
        self.assertNotContains(self.client.get(reverse('panel_soporte')), 'Todos los tickets abiertos')


class AccesoTests(TestCase):

    def test_el_login_lleva_al_panel_de_soporte(self):
        agente = crear_agente('10000001-9', Ticket.APODERADOS)
        respuesta = self.client.post(reverse('login'), {'username': agente.user.rut, 'password': CLAVE})
        self.assertRedirects(respuesta, reverse('panel_soporte'))
        self.assertEqual(self.client.session['soporte_id'], agente.id_agente)

    def test_crear_soporte_pide_los_datos_y_no_da_acceso_a_django_admin(self):
        salida = StringIO()
        with mock.patch('builtins.input', side_effect=['11111111-1', 'Lia', 'Soporte', 'lia@example.com']), \
                mock.patch('getpass.getpass', side_effect=[CLAVE, CLAVE]):
            call_command('crear_soporte', '--categorias', 'titulos', 'apoderados', '--lider', stdout=salida)

        agente = AgenteSoporte.objects.get(user__rut='11111111-1')
        self.assertTrue(agente.es_lider)
        self.assertEqual(agente.categorias, {Ticket.TITULOS, Ticket.APODERADOS})
        self.assertEqual(agente.user.rol, 'soporte')
        self.assertFalse(agente.user.is_staff or agente.user.is_superuser)
        self.assertIn('Líder de soporte 11111111-1 creado', salida.getvalue())
