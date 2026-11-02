"""Paso 8c: la campana avisa plazos segun quien la abre (admin_portal/avisos.py).

Antes mostraba siempre el punto rojo y dos avisos inventados ("Jose" en el Plan
Basico y "Tanger" con $45.000). Ahora el admin ve sus retiros con plazo y el
agente de soporte sus tickets por vencer o atrasados; los avisos desaparecen
solos al resolverse.
"""

from datetime import datetime, time, timedelta

from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from admin_portal import avisos
from alumnos import catalogos
from alumnos.models import TIPOS_CUENTA, CuentaBancaria, SolicitudRetiro
from soporte.models import Ticket
from soporte.tickets import abrir_reporte
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_paquetes import Escenario
from tests.test_retiros import crear_admin, entrar_admin
from tests.test_soporte_reportes import crear_alumno_adulto


def avisos_de(**sesion):
    request = RequestFactory().get('/')
    request.session = sesion
    return avisos.para(request)


class CampanaAdminTests(Escenario):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin, cls.tutor = crear_admin()

    def setUp(self):
        self.hoy = timezone.localdate()

    def retiro(self, estado=SolicitudRetiro.PENDIENTE, dias=0, monto=10000, profesor=None):
        """Retiro que se paga dentro de `dias` (negativo: ya debia pagarse)."""
        return SolicitudRetiro.objects.create(profesor=profesor or self.profe, monto=monto, estado=estado,
                                              pagar_el=self.hoy + timedelta(days=dias))

    def avisos_admin(self):
        return avisos_de(admin_id=self.tutor.id_tutor)

    def test_sin_retiros_no_hay_avisos(self):
        self.assertEqual(self.avisos_admin(), [])

    def test_retiros_por_revisar(self):
        self.retiro(dias=3)
        self.retiro(dias=3, monto=5000, profesor=self.otro)
        [aviso] = self.avisos_admin()
        self.assertEqual(aviso.titulo, '2 retiros por revisar')
        self.assertIn('Suman $15.000. El más antiguo llegó hoy.', aviso.detalle)
        self.assertFalse(aviso.urgente)

    def test_por_revisar_es_urgente_si_ya_debia_pagarse(self):
        self.retiro(dias=0)
        [aviso] = self.avisos_admin()
        self.assertTrue(aviso.urgente)
        self.assertIn('Hay retiros que ya debían pagarse.', aviso.detalle)

    def test_aprobados_atrasados_de_hoy_y_futuros(self):
        self.retiro(SolicitudRetiro.APROBADO, dias=-3, monto=20000)
        self.retiro(SolicitudRetiro.APROBADO, dias=0)
        self.retiro(SolicitudRetiro.APROBADO, dias=4)  # aun no toca: sin aviso
        atrasado, de_hoy = self.avisos_admin()
        self.assertEqual(atrasado.titulo, '1 retiro con pago atrasado')
        self.assertIn(f'Suman $20.000. Debía pagarse el {self.hoy - timedelta(days=3):%d/%m}.', atrasado.detalle)
        self.assertTrue(atrasado.urgente)
        self.assertEqual(de_hoy.titulo, '1 retiro para pagar hoy')
        self.assertIn('Suman $10.000.', de_hoy.detalle)

    def test_cuenta_recien_cambiada_espera_y_no_cuenta_como_pago_de_hoy(self):
        CuentaBancaria.objects.create(profesor=self.profe, banco=catalogos.BANCOS[0], tipo_cuenta=TIPOS_CUENTA[0][0],
                                      numero_cifrado=b'x', ultimos_digitos='1234', cambiada_en=timezone.now())
        self.retiro(SolicitudRetiro.APROBADO, dias=0)
        [aviso] = self.avisos_admin()
        self.assertEqual(aviso.titulo, f'Retiro de {self.profe.nombre}: espera para transferir')
        self.assertIn('se puede pagar desde el', aviso.detalle)

    def test_pagados_y_rechazados_no_avisan(self):
        self.retiro(SolicitudRetiro.PAGADO, dias=-5)
        self.retiro(SolicitudRetiro.RECHAZADO, dias=-5)
        self.assertEqual(self.avisos_admin(), [])

    def test_solo_el_admin_ve_los_retiros(self):
        self.retiro()
        self.assertEqual(avisos_de(soporte_id=1), [])
        self.assertEqual(avisos_de(), [])

    def test_el_panel_muestra_la_campana_real(self):
        self.retiro()
        entrar_admin(self.client, self.admin, self.tutor)
        respuesta = self.client.get(reverse('dashboard_admin'))
        self.assertContains(respuesta, '1 retiro por revisar')
        self.assertContains(respuesta, 'notif-badge-dot')
        for falso in ('Tánger', 'Jose', 'Plan Básico', 'Marcar todas como leídas'):
            self.assertNotContains(respuesta, falso)

    def test_sin_avisos_no_hay_punto_rojo(self):
        entrar_admin(self.client, self.admin, self.tutor)
        respuesta = self.client.get(reverse('dashboard_admin'))
        self.assertNotContains(respuesta, 'notif-badge-dot')
        self.assertContains(respuesta, 'No hay avisos pendientes.')


class CampanaAgenteTests(TestCase):
    """El agente ve sus tickets sin respuesta que vencen a mas tardar el proximo dia habil."""

    def setUp(self):
        self.agente = crear_agente('20202020-2', Ticket.CLASES, Ticket.CONDUCTA)
        self.alumno = crear_alumno_adulto()

    def ticket(self, categoria=Ticket.CLASES, vence=None, **cambios):
        ticket = abrir_reporte(self.alumno.user, categoria, 'Profesor no llegó', 'Esperé 30 minutos.')
        if vence is not None:
            cambios['vence'] = vence
        Ticket.objects.filter(pk=ticket.pk).update(**cambios)
        return ticket

    def fin_de_hoy(self):
        return timezone.make_aware(datetime.combine(timezone.localdate(), time(23, 59, 59)))

    def avisos_agente(self):
        return avisos_de(soporte_id=self.agente.id_agente)

    def test_con_plazo_holgado_no_avisa(self):
        self.ticket()  # clases: 2 dias habiles
        self.assertEqual(self.avisos_agente(), [])

    def test_ticket_atrasado_es_urgente_y_lleva_a_la_conversacion(self):
        ticket = self.ticket(vence=timezone.now() - timedelta(hours=1))
        [aviso] = self.avisos_agente()
        self.assertEqual(aviso.titulo, f'Ticket #{ticket.pk} atrasado')
        self.assertIn('Profesor no llegó. Venció el', aviso.detalle)
        self.assertTrue(aviso.urgente)
        self.assertEqual(aviso.url, reverse('soporte_reporte', args=[ticket.pk]))

    def test_ticket_que_vence_hoy(self):
        ticket = self.ticket(vence=self.fin_de_hoy())
        [aviso] = self.avisos_agente()
        self.assertEqual(aviso.titulo, f'Ticket #{ticket.pk} vence hoy')
        self.assertFalse(aviso.urgente)

    def test_conducta_por_vencer_es_urgente(self):
        self.ticket(Ticket.CONDUCTA, vence=self.fin_de_hoy())
        [aviso] = self.avisos_agente()
        self.assertTrue(aviso.urgente)

    def test_respondido_cumple_el_plazo(self):
        self.ticket(vence=timezone.now() - timedelta(hours=1), respondido=timezone.now())
        self.assertEqual(self.avisos_agente(), [])

    def test_no_ve_los_tickets_de_otro_agente(self):
        otro = crear_agente('21212121-2', Ticket.CLASES)
        self.ticket(vence=timezone.now() - timedelta(hours=1), asignado=otro)
        self.assertEqual(self.avisos_agente(), [])

    def test_el_panel_de_soporte_muestra_su_campana(self):
        ticket = self.ticket(vence=timezone.now() - timedelta(hours=1))
        entrar_soporte(self.client, self.agente)
        respuesta = self.client.get(reverse('panel_soporte'))
        self.assertContains(respuesta, f'Ticket #{ticket.pk} atrasado')
        self.assertContains(respuesta, 'notif-badge-dot')
        self.assertNotContains(respuesta, 'onclick="openSearchModal()"')  # el buscador es del admin
