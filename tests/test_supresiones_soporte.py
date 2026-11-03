"""Soporte resuelve la solicitud de eliminar una cuenta: la ejecuta (borrando o seudonimizando segun la regla de
mensajes/supresion.py) o la rechaza explicando por que. Datos ficticios."""

from unittest import mock

from django.core import mail
from django.urls import reverse

from alumnos.models import Alumno, CustomUser, Inscripcion, PaqueteClases
from soporte.models import Mensaje, Ticket
from soporte.tickets import abrir_reporte
from supresiones import solicitud
from supresiones.models import SolicitudSupresion
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import Escenario, dar_paquete


class ResolverBase(Escenario):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.PRIVACIDAD)
        entrar_soporte(self.client, self.agente)

    def pedir(self, alumno):
        with self.captureOnCommitCallbacks(execute=True):
            sol, _ = solicitud.abrir(alumno.user)
        mail.outbox.clear()
        return sol

    def ejecutar(self, sol, confirmo='on', **extra):
        datos = {'confirmo': confirmo} if confirmo else {}
        return self.client.post(reverse('supresion_ejecutar', args=[sol.ticket_id]), datos, **extra)

    def consumir_paquete(self, alumno):
        """Paquete de una clase ya usada: no impide eliminar, pero hay historial que conservar."""
        paquete = dar_paquete(alumno, self.profe, plan='flexible')
        Inscripcion.objects.create(alumno=alumno, clase=self.clase, sesion=crear_sesion(self.clase, -3), paquete=paquete)


class PanelTests(ResolverBase):

    def test_el_agente_asignado_ve_la_evaluacion_y_las_acciones(self):
        sol = self.pedir(self.beto)
        r = self.client.get(reverse('soporte_reporte', args=[sol.ticket_id]))
        self.assertContains(r, 'Solicitud de eliminar la cuenta')
        self.assertContains(r, 'Datos de la cuenta')
        self.assertContains(r, 'No se pide carnet')
        self.assertContains(r, reverse('supresion_ejecutar', args=[sol.ticket_id]))
        self.assertContains(r, reverse('supresion_rechazar', args=[sol.ticket_id]))

    def test_con_bloqueos_se_muestran_y_el_boton_va_deshabilitado(self):
        dar_paquete(self.ana, self.profe)
        sol = self.pedir(self.ana)
        r = self.client.get(reverse('soporte_reporte', args=[sol.ticket_id]))
        self.assertContains(r, 'Hoy no se puede eliminar')
        self.assertContains(r, 'sin usar')
        self.assertContains(r, 'id="supresion-confirmo" disabled')

    def test_un_lider_sin_el_ticket_lo_ve_pero_no_resuelve(self):
        sol = self.pedir(self.beto)
        lider = crear_agente('10000002-7', Ticket.OTRO, lider=True)
        entrar_soporte(self.client, lider)
        r = self.client.get(reverse('soporte_reporte', args=[sol.ticket_id]))
        self.assertContains(r, 'Solo el agente asignado resuelve')
        self.assertNotContains(r, reverse('supresion_ejecutar', args=[sol.ticket_id]))
        self.assertEqual(self.ejecutar(sol).status_code, 404)
        self.assertTrue(CustomUser.objects.filter(pk=self.beto.user_id).exists())

    def test_otro_ticket_no_muestra_el_panel(self):
        ticket = abrir_reporte(self.beto.user, Ticket.PRIVACIDAD, 'Otra cosa', 'x')  # sin solicitud
        r = self.client.get(reverse('soporte_reporte', args=[ticket.pk]))
        self.assertNotContains(r, 'Solicitud de eliminar la cuenta')


class EjecutarTests(ResolverBase):

    def test_sin_historial_se_borra_la_cuenta_completa_y_queda_el_registro(self):
        sol = self.pedir(self.beto)
        correo_de_beto = self.beto.user.email
        r = self.ejecutar(sol)
        self.assertRedirects(r, reverse('panel_soporte'), fetch_redirect_response=False)
        self.assertFalse(CustomUser.objects.filter(pk=self.beto.user_id).exists())
        self.assertFalse(Alumno.objects.filter(pk=self.beto.pk).exists())
        sol.refresh_from_db()
        self.assertEqual((sol.estado, sol.resultado, sol.resuelta_por), (SolicitudSupresion.EJECUTADA,
                                                                         SolicitudSupresion.BORRADA, self.agente))
        self.assertIsNotNone(sol.resuelta)
        self.assertIsNone(sol.usuario)  # el registro no guarda a quien era
        self.assertEqual(mail.outbox[-1].to, [correo_de_beto])
        self.assertIn(f'solicitud #{sol.pk}', mail.outbox[-1].subject)
        self.assertIn('eliminado', mail.outbox[-1].body)

    def test_con_historial_se_seudonimiza_y_se_conserva_lo_que_corresponde(self):
        self.consumir_paquete(self.ana)
        sol = self.pedir(self.ana)
        correo_de_ana = self.ana.user.email
        self.ejecutar(sol)
        usuario = CustomUser.objects.get(pk=self.ana.user_id)
        self.assertIsNotNone(usuario.suprimida)
        self.assertEqual((usuario.first_name, usuario.email), ('Cuenta eliminada', ''))
        self.assertFalse(usuario.is_active)
        self.assertEqual(PaqueteClases.objects.filter(alumno=self.ana).count(), 1)
        sol.refresh_from_db()
        self.assertEqual(sol.resultado, SolicitudSupresion.SEUDONIMIZADA)
        self.assertEqual(sol.usuario, usuario)
        self.assertEqual(sol.ticket.estado, Ticket.CERRADO)
        self.assertIsNotNone(sol.ticket.respondido)  # cumple el plazo
        self.assertEqual(mail.outbox[-1].to, [correo_de_ana])
        self.assertIn('Pagos y clases: se conserva', mail.outbox[-1].body)

    def test_el_correo_del_resultado_no_se_manda_a_un_correo_vacio(self):
        self.consumir_paquete(self.ana)
        sol = self.pedir(self.ana)
        CustomUser.objects.filter(pk=self.ana.user_id).update(email='')
        self.ejecutar(sol)
        self.assertEqual(len(mail.outbox), 0)

    def test_si_el_correo_no_sale_se_le_avisa_al_agente(self):
        sol = self.pedir(self.beto)
        with mock.patch('supresiones.correo.enviar', return_value=False):
            r = self.ejecutar(sol, follow=True)
        self.assertContains(r, 'No se pudo enviar el correo')
        self.assertFalse(CustomUser.objects.filter(pk=self.beto.user_id).exists())  # igual se elimino

    def test_con_bloqueos_no_se_elimina(self):
        dar_paquete(self.ana, self.profe)
        sol = self.pedir(self.ana)
        r = self.ejecutar(sol, follow=True)
        self.assertContains(r, 'Hoy no se puede eliminar')
        self.assertTrue(CustomUser.objects.get(pk=self.ana.user_id).is_active)
        sol.refresh_from_db()
        self.assertEqual(sol.estado, SolicitudSupresion.ABIERTA)
        self.assertEqual(len(mail.outbox), 0)

    def test_sin_marcar_la_confirmacion_no_se_elimina(self):
        sol = self.pedir(self.beto)
        r = self.ejecutar(sol, confirmo='', follow=True)
        self.assertContains(r, 'Marca la casilla')
        self.assertTrue(CustomUser.objects.filter(pk=self.beto.user_id).exists())

    def test_otro_agente_habilitado_no_puede(self):
        sol = self.pedir(self.beto)
        otro = crear_agente('10000004-3', Ticket.PRIVACIDAD)
        entrar_soporte(self.client, otro)
        self.assertEqual(self.ejecutar(sol).status_code, 404)
        self.assertTrue(CustomUser.objects.filter(pk=self.beto.user_id).exists())

    def test_se_exige_post_y_sesion_de_soporte(self):
        sol = self.pedir(self.beto)
        self.assertEqual(self.client.get(reverse('supresion_ejecutar', args=[sol.ticket_id])).status_code, 405)
        self.client.logout()
        self.assertEqual(self.ejecutar(sol).status_code, 302)  # al login
        self.assertTrue(CustomUser.objects.filter(pk=self.beto.user_id).exists())

    def test_una_solicitud_resuelta_no_se_resuelve_dos_veces(self):
        self.consumir_paquete(self.ana)
        sol = self.pedir(self.ana)
        self.ejecutar(sol)
        self.assertEqual(self.ejecutar(sol).status_code, 404)  # el ticket ya esta cerrado
        with self.assertRaises(solicitud.SolicitudError):
            solicitud.ejecutar(sol, self.agente)

    def test_el_profesor_se_recibe_pero_aun_no_se_ejecuta(self):
        sol = self.pedir(self.profe)
        r = self.ejecutar(sol, follow=True)
        self.assertContains(r, 'Todavía no se puede eliminar automáticamente')
        self.assertTrue(CustomUser.objects.get(pk=self.profe.user_id).is_active)


class RechazarTests(ResolverBase):

    def rechazar(self, sol, motivo='Usa primero tus clases pagadas y vuelve a pedirlo.', **extra):
        return self.client.post(reverse('supresion_rechazar', args=[sol.ticket_id]), {'motivo': motivo}, **extra)

    def test_responde_al_usuario_cierra_el_ticket_y_no_toca_la_cuenta(self):
        dar_paquete(self.ana, self.profe)
        sol = self.pedir(self.ana)
        r = self.rechazar(sol)
        self.assertRedirects(r, reverse('panel_soporte'), fetch_redirect_response=False)
        sol.refresh_from_db()
        self.assertEqual((sol.estado, sol.resuelta_por), (SolicitudSupresion.RECHAZADA, self.agente))
        self.assertIn('Usa primero', sol.motivo_rechazo)
        self.assertEqual((sol.ticket.estado, sol.resultado), (Ticket.CERRADO, ''))
        self.assertTrue(Mensaje.objects.get(ticket=sol.ticket).de_soporte)
        self.assertTrue(CustomUser.objects.get(pk=self.ana.user_id).is_active)

    def test_el_usuario_lee_la_respuesta_y_puede_volver_a_pedirlo(self):
        dar_paquete(self.ana, self.profe)
        sol = self.pedir(self.ana)
        self.rechazar(sol)
        self.entrar(self.ana.user.rut)
        self.assertContains(self.client.get(reverse('mi_ticket', args=[sol.ticket_id])), 'Usa primero')
        self.assertContains(self.client.get(reverse('eliminar_cuenta')), 'Enviarme el enlace')

    def test_exige_explicar_el_motivo(self):
        sol = self.pedir(self.beto)
        r = self.rechazar(sol, motivo='   ', follow=True)
        self.assertContains(r, 'Explica por qué')
        sol.refresh_from_db()
        self.assertEqual(sol.estado, SolicitudSupresion.ABIERTA)

    def test_solo_el_agente_asignado_rechaza(self):
        sol = self.pedir(self.beto)
        entrar_soporte(self.client, crear_agente('10000004-3', Ticket.PRIVACIDAD))
        self.assertEqual(self.rechazar(sol).status_code, 404)
