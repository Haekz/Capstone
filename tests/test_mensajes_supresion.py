"""Eliminar una cuenta sin perder las conversaciones reportadas (paso C1e, decidido 03-nov). Datos ficticios."""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from alumnos.models import Alumno, CustomUser
from mensajes import panel, retencion, servicio, supresion
from mensajes.models import Conversacion, Mensaje, ReporteConversacion
from mensajes.servicio import MensajeError
from notificaciones.models import Notificacion
from soporte.models import Ticket
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_paquetes import RUT_PROFE, Escenario, dar_paquete
from tests.test_retiros import crear_admin, entrar_admin

# Inconfundible: el panel del profesor trae un chat de demostracion con "Hola profesor".
TEXTO = 'Consulta sobre la guia 7'


class SuprimirCuentaTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)
        dar_paquete(self.ana, self.otro)
        self.con_profe = servicio.abrir_conversacion(self.ana, self.profe)
        self.con_otro = servicio.abrir_conversacion(self.ana, self.otro)
        self.nombre = self.ana.user.first_name
        with self.captureOnCommitCallbacks(execute=True):
            servicio.enviar(self.ana.user, self.con_profe, TEXTO)
            servicio.enviar(self.profe.user, self.con_profe, 'Claro, dime')  # le avisa a Ana
            servicio.enviar(self.ana.user, self.con_otro, 'Hola')

    def reportar(self):
        self.agente = crear_agente('10000001-9', Ticket.CONDUCTA)
        return servicio.reportar(self.profe.user, self.con_profe, 'Me incomoda.')

    def suprimir_a_ana(self):
        return supresion.suprimir_cuenta(CustomUser.objects.get(pk=self.ana.user_id))

    # --- sin reportes ---

    def test_sin_conversaciones_reportadas_se_borra_todo_como_siempre(self):
        self.assertTrue(self.suprimir_a_ana())
        self.assertFalse(CustomUser.objects.filter(pk=self.ana.user_id).exists())
        self.assertFalse(Conversacion.objects.exists())
        self.assertFalse(Mensaje.objects.exists())

    # --- con una conversacion reportada ---

    def test_con_una_reportada_la_cuenta_se_seudonimiza_y_no_se_borra(self):
        self.reportar()
        self.assertFalse(self.suprimir_a_ana())
        u = CustomUser.objects.get(pk=self.ana.user_id)
        self.assertEqual((u.first_name, u.last_name, u.email), ('Cuenta eliminada', '', ''))
        self.assertEqual((u.rut, u.telefono, u.direccion, u.fecha_nacimiento, u.genero), (None, '', '', None, None))
        self.assertFalse(u.is_active)
        self.assertFalse(u.has_usable_password())
        self.assertIsNotNone(u.suprimida)
        self.assertTrue(Alumno.objects.filter(pk=self.ana.pk).exists())

    def test_se_conserva_lo_reportado_y_se_borra_lo_demas(self):
        self.reportar()
        self.suprimir_a_ana()
        self.assertEqual(list(Conversacion.objects.values_list('pk', flat=True)), [self.con_profe.pk])
        self.assertEqual(Mensaje.objects.count(), 2)  # los dos de la reportada; el de la otra se fue
        self.assertEqual(ReporteConversacion.objects.count(), 1)
        self.assertEqual(Ticket.objects.filter(reporte_conversacion__isnull=False).count(), 1)

    def test_sus_avisos_se_borran(self):
        self.reportar()
        self.assertTrue(Notificacion.objects.filter(usuario=self.ana.user).exists())
        self.suprimir_a_ana()
        self.assertFalse(Notificacion.objects.filter(usuario_id=self.ana.user_id).exists())

    def test_la_otra_persona_ya_no_la_ve_queda_solo_para_soporte(self):
        self.reportar()
        self.suprimir_a_ana()
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('panel_profesor'), {'c': self.con_profe.pk})
        self.assertNotContains(r, TEXTO)
        self.assertNotContains(r, 'Cuenta eliminada')
        r = self.client.post(reverse('mensajes_profesor_enviar', args=[self.con_profe.pk]), {'texto': 'Hola'})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.client.get(reverse('mensajes_reportar', args=[self.con_profe.pk])).status_code, 404)
        with self.assertRaisesMessage(MensajeError, 'solo para lectura'):  # tambien fuera de las vistas
            servicio.enviar(self.profe.user, Conversacion.objects.get(), 'Hola')

    def test_soporte_la_sigue_leyendo(self):
        reporte = self.reportar()
        self.suprimir_a_ana()
        entrar_soporte(self.client, self.agente)
        r = self.client.get(reverse('mensajes_soporte_leer', args=[reporte.ticket_id]))
        self.assertContains(r, TEXTO)
        self.assertContains(r, 'Cuenta eliminada')
        self.assertNotContains(r, self.nombre)

    def test_aunque_este_anonimizada_no_se_borra_por_inactividad(self):
        self.reportar()
        self.suprimir_a_ana()
        Conversacion.objects.update(creada=timezone.now() - timedelta(days=400))
        Mensaje.objects.update(creado=timezone.now() - timedelta(days=400))
        Ticket.objects.update(estado=Ticket.CERRADO)
        self.assertEqual(retencion.borrar_inactivas(), 0)
        self.assertTrue(Conversacion.objects.exists())

    def test_si_elimina_la_cuenta_quien_reporto_el_ticket_tambien_se_conserva(self):
        self.reportar()
        self.assertFalse(supresion.suprimir_cuenta(CustomUser.objects.get(pk=self.profe.user_id)))
        ticket = Ticket.objects.get(reporte_conversacion__isnull=False)
        self.assertTrue(ticket.autor.suprimida)
        self.assertEqual(Conversacion.objects.filter(pk=self.con_profe.pk).count(), 1)
        bandeja = [c.pk for c in panel.contexto_alumno(self.ana, None)['bandeja']]
        self.assertNotIn(self.con_profe.pk, bandeja)  # la alumna tampoco la ve: solo soporte
        self.assertIn(self.con_otro.pk, bandeja)

    # --- vista del administrador ---

    def borrar_desde_el_admin(self):
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)
        return self.client.post(reverse('alumnos_del', args=[self.ana.id_alumno]))

    def test_el_admin_elimina_un_alumno_sin_reportes_como_antes(self):
        r = self.borrar_desde_el_admin()
        self.assertContains(r, 'datos eliminados')
        self.assertFalse(Alumno.objects.filter(pk=self.ana.pk).exists())

    def test_el_admin_no_destruye_las_conversaciones_reportadas(self):
        self.reportar()
        r = self.borrar_desde_el_admin()
        self.assertContains(r, 'se seudonimizó')
        self.assertTrue(Alumno.objects.filter(pk=self.ana.pk).exists())
        self.assertTrue(Conversacion.objects.filter(pk=self.con_profe.pk).exists())
        self.assertFalse(Conversacion.objects.filter(pk=self.con_otro.pk).exists())
