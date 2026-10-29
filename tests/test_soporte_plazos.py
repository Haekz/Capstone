"""Soporte 2b-2: plazos en dias habiles de Chile, correos y avisos de atraso.

Datos ficticios. Fechas fijas de 2026 para que los feriados no dependan del dia
en que corre la prueba.
"""

from datetime import date, datetime, time, timedelta
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apoderados.models import Apoderado, Vinculo
from soporte.models import Ticket
from soporte.plazos import es_habil, vencimiento
from soporte.tickets import abrir_ticket, reasignar
from tests.test_apoderados import RUT, crear_agente, crear_apoderado, entrar_soporte
from tests.test_apoderados_vinculos import crear_menor_vinculado


def a_las(dia, hora=10):
    """Fecha y hora de Chile."""
    return timezone.make_aware(datetime.combine(dia, time(hora)))


def fin_del_dia(dia):
    return timezone.make_aware(datetime.combine(dia, time(23, 59, 59)))


class PlazosTests(TestCase):

    def test_el_dia_de_apertura_no_cuenta_ni_el_fin_de_semana(self):
        viernes = date(2026, 10, 23)
        self.assertEqual(vencimiento(a_las(viernes), 1), fin_del_dia(date(2026, 10, 26)))  # lunes

    def test_se_salta_los_feriados_moviles(self):
        viernes = date(2026, 6, 26)  # el lunes 29 es San Pedro y San Pablo
        self.assertEqual(vencimiento(a_las(viernes), 1), fin_del_dia(date(2026, 6, 30)))

    def test_cinco_dias_habiles_con_fiestas_patrias(self):
        lunes = date(2026, 9, 14)  # 18 y 19 son feriados
        self.assertEqual(vencimiento(a_las(lunes, 23), 5), fin_del_dia(date(2026, 9, 22)))

    def test_dias_habiles(self):
        self.assertTrue(es_habil(date(2026, 9, 21)))
        self.assertFalse(es_habil(date(2026, 9, 18)))  # feriado
        self.assertFalse(es_habil(date(2026, 9, 26)))  # sabado


class PlazoDelTicketTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.APODERADOS)
        self.otro = crear_agente('10000002-7', Ticket.APODERADOS)

    def test_el_ticket_vence_a_los_dias_habiles_de_su_categoria(self):
        with mock.patch('django.utils.timezone.now', return_value=a_las(date(2026, 9, 14))):
            abrir_ticket(Ticket.APODERADOS, apoderado=crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE))
        self.assertEqual(Ticket.objects.get().vence, fin_del_dia(date(2026, 9, 22)))

    def test_reasignar_no_reinicia_el_plazo(self):
        abrir_ticket(Ticket.APODERADOS, apoderado=crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE))
        ticket = Ticket.objects.get()
        vence = ticket.vence
        reasignar(ticket, self.otro, autor=None)
        ticket.refresh_from_db()
        self.assertEqual(ticket.vence, vence)

    def test_atrasado_solo_si_sigue_abierto_y_ya_vencio(self):
        abrir_ticket(Ticket.APODERADOS, apoderado=crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE))
        ticket = Ticket.objects.get()
        self.assertFalse(ticket.atrasado)
        ticket.vence = timezone.now() - timedelta(minutes=1)
        self.assertTrue(ticket.atrasado)
        ticket.estado = Ticket.CERRADO
        self.assertFalse(ticket.atrasado)

    def test_el_panel_muestra_el_plazo_y_los_atrasados(self):
        abrir_ticket(Ticket.APODERADOS, apoderado=crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE))
        Ticket.objects.update(vence=timezone.now() - timedelta(days=1))
        entrar_soporte(self.client, self.agente)
        respuesta = self.client.get(reverse('panel_soporte'))
        self.assertContains(respuesta, '<th>Vence</th>', html=True)
        self.assertContains(respuesta, 'Atrasado')


class DespliegueTests(TransactionTestCase):
    """Las migraciones de verdad: soporte vuelve a 0001 y avanza hasta el plazo."""

    def migrar(self, hasta):
        MigrationExecutor(connection).migrate([('soporte', hasta)])

    def test_lo_pendiente_al_desplegar_queda_como_ticket_sin_asignar_y_con_plazo(self):
        self.addCleanup(self.migrar, '0003_plazo_de_los_tickets')  # aunque falle, el resto sigue al dia
        self.migrar('0001_equipo_y_tickets')
        apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        vinculo = crear_menor_vinculado(crear_apoderado('15151515-1', Apoderado.VERIFICADO), estado=Vinculo.PENDIENTE)
        sin_verificar = crear_apoderado('13131313-1', Apoderado.REVISION_PENDIENTE)
        crear_menor_vinculado(sin_verificar, rut='14141414-1', estado=Vinculo.PENDIENTE)  # aun no se revisa

        self.migrar('0003_plazo_de_los_tickets')

        abiertos = Ticket.objects.filter(estado=Ticket.ABIERTO, asignado__isnull=True)
        self.assertEqual(set(abiertos.values_list('apoderado', 'vinculo')),
                         {(apoderado.pk, None), (sin_verificar.pk, None), (None, vinculo.pk)})
        for ticket in abiertos:
            self.assertEqual(ticket.vence, vencimiento(ticket.creado, Ticket.DIAS_HABILES[ticket.categoria]))


class CorreosTests(TestCase):

    def abrir(self, rut=RUT):
        apoderado = crear_apoderado(rut, Apoderado.REVISION_PENDIENTE)
        with self.captureOnCommitCallbacks(execute=True):
            abrir_ticket(Ticket.APODERADOS, apoderado=apoderado)
        return apoderado

    def test_el_agente_recibe_el_ticket_sin_datos_personales(self):
        agente = crear_agente('10000001-9', Ticket.APODERADOS)
        apoderado = self.abrir()

        correo, = mail.outbox
        ticket = Ticket.objects.get()
        self.assertEqual(correo.to, [agente.user.email])
        self.assertEqual(correo.subject, f'Ticket #{ticket.pk} asignado - LBWUS')
        self.assertIn('Apoderados y menores', correo.body)
        for dato in (apoderado.nombre, apoderado.user.rut, apoderado.user.email):
            self.assertNotIn(dato, correo.body)

    def test_sin_agente_se_avisa_a_los_lideres_activos(self):
        lider = crear_agente('10000001-9', lider=True)
        inactivo = crear_agente('10000002-7', lider=True)
        inactivo.user.is_active = False
        inactivo.user.save()
        crear_agente('10000003-5', Ticket.TITULOS)  # otra categoria

        self.abrir()

        correo, = mail.outbox
        self.assertEqual(correo.to, [lider.user.email])
        self.assertIn('sin asignar', correo.subject)

    def test_al_reasignar_avisa_al_nuevo_agente(self):
        crear_agente('10000001-9', Ticket.APODERADOS)
        otro = crear_agente('10000002-7', Ticket.APODERADOS)
        self.abrir()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            reasignar(Ticket.objects.get(), otro, autor=None)
        self.assertEqual([c.to for c in mail.outbox], [[otro.user.email]])

    def test_si_la_transaccion_se_deshace_no_sale_el_correo(self):
        crear_agente('10000001-9', Ticket.APODERADOS)
        apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    abrir_ticket(Ticket.APODERADOS, apoderado=apoderado)
                    raise RuntimeError('falla despues de abrir')
            except RuntimeError:
                pass
        self.assertFalse(Ticket.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_si_el_correo_falla_el_ticket_queda(self):
        crear_agente('10000001-9', Ticket.APODERADOS)
        with mock.patch('alumnos.correo.send_mail', side_effect=OSError('sin servidor')):
            self.abrir()
        self.assertTrue(Ticket.objects.filter(estado=Ticket.ABIERTO).exists())


class AvisoDeAtrasosTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.APODERADOS)
        self.al_dia = crear_agente('10000002-7', Ticket.TITULOS)
        self.lider = crear_agente('10000003-5', lider=True)
        abrir_ticket(Ticket.APODERADOS, apoderado=crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE))
        self.atrasado = Ticket.objects.get()
        sin_agente = crear_apoderado('13131313-1', Apoderado.REVISION_PENDIENTE)
        Ticket.objects.filter(pk=self.atrasado.pk).update(vence=timezone.now() - timedelta(days=1))
        self.agente.habilitaciones.all().delete()  # el siguiente queda sin asignar
        abrir_ticket(Ticket.APODERADOS, apoderado=sin_agente)
        Ticket.objects.filter(apoderado=sin_agente).update(vence=timezone.now() - timedelta(days=2))
        mail.outbox.clear()

    def avisar(self, dia):
        salida = StringIO()
        with mock.patch('django.utils.timezone.localdate', return_value=dia):
            call_command('avisar_tickets_atrasados', stdout=salida)
        return salida.getvalue()

    def test_en_dia_habil_avisa_al_agente_lo_suyo_y_al_lider_todo(self):
        salida = self.avisar(date(2026, 9, 21))

        self.assertIn('Tickets atrasados avisados: 2', salida)
        correos = {c.to[0]: c.body for c in mail.outbox}
        self.assertEqual(set(correos), {self.agente.user.email, self.lider.user.email})  # el agente al dia, nada
        self.assertIn(f'#{self.atrasado.pk}', correos[self.agente.user.email])
        self.assertEqual(correos[self.agente.user.email].count('Ticket #'), 1)
        self.assertEqual(correos[self.lider.user.email].count('Ticket #'), 2)
        self.assertIn('Sin asignar', correos[self.lider.user.email])

    def test_en_fin_de_semana_o_feriado_no_envia_nada(self):
        for dia in (date(2026, 9, 18), date(2026, 9, 19), date(2026, 9, 20)):
            with self.subTest(dia=dia):
                self.assertIn('no es día hábil', self.avisar(dia))
        self.assertEqual(mail.outbox, [])
