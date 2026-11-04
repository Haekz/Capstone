"""Revision de conversaciones reportadas por el lider (paso C1f, decidido 02-nov). Datos ficticios."""

from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from alumnos.models import CustomUser, PaqueteClases
from mensajes import retencion, revision, servicio, supresion
from mensajes.models import Conversacion, DecisionRetencion, Mensaje
from mensajes.servicio import MensajeError
from soporte.models import Ticket
from tests.test_apoderados import crear_agente
from tests.test_paquetes import Escenario, dar_paquete

TEXTOS = {'alcance': 'Los 3 mensajes del 28-oct.', 'fundamento': 'Posible reclamo del apoderado.',
          'termino': 'Cuando se resuelva el reclamo.'}


class RevisionTests(Escenario):

    def setUp(self):
        self.hoy = timezone.localdate()
        self.lider = crear_agente('10000002-7', Ticket.CONDUCTA, lider=True)
        self.agente = crear_agente('10000001-9', Ticket.CONDUCTA)
        dar_paquete(self.ana, self.profe)
        self.conversacion = servicio.abrir_conversacion(self.ana, self.profe)
        with self.captureOnCommitCallbacks(execute=True):
            servicio.enviar(self.ana.user, self.conversacion, 'Consulta sobre la guia 7')
        self.reporte = servicio.reportar(self.profe.user, self.conversacion, 'Me incomoda.')

    def cerrar_ticket(self, ticket=None):
        Ticket.objects.filter(pk=(ticket or self.reporte.ticket).pk).update(estado=Ticket.CERRADO, cerrado=timezone.now())

    def pendientes(self, hoy=None):
        return list(revision.pendientes(hoy or self.hoy).values_list('pk', flat=True))

    def retenida(self):
        return revision.retenidas().filter(pk=self.conversacion.pk).exists()

    def envejecer(self):
        """Pasa el tiempo: conversacion y mensajes viejos, y sin el paquete vigente que (aparte) tambien
        impediria borrar; asi lo que se prueba es solo la regla del reporte."""
        PaqueteClases.objects.all().delete()
        Conversacion.objects.update(creada=timezone.now() - timedelta(days=400))
        Mensaje.objects.update(creado=timezone.now() - timedelta(days=400))

    # --- estados ---

    def test_con_el_ticket_abierto_esta_retenida_y_no_pendiente(self):
        self.assertEqual(self.pendientes(), [])
        self.assertTrue(self.retenida())

    def test_al_cerrarse_el_ticket_queda_pendiente_y_sigue_retenida(self):
        self.cerrar_ticket()
        self.assertEqual(self.pendientes(), [self.conversacion.pk])
        self.assertTrue(self.retenida())

    def test_una_pendiente_no_se_borra_aunque_sea_vieja(self):
        self.cerrar_ticket()
        self.envejecer()
        self.assertEqual(retencion.borrar_inactivas(), 0)

    # --- liberar ---

    def test_liberar_la_saca_de_pendientes_y_de_retenidas_y_deja_registro(self):
        self.cerrar_ticket()
        decision = revision.liberar(self.lider, self.conversacion)
        self.assertEqual(self.pendientes(), [])
        self.assertFalse(self.retenida())
        self.assertEqual((decision.decision, decision.decidida_por), (DecisionRetencion.LIBERAR, self.lider))

    def test_una_liberada_vuelve_a_la_regla_de_90_dias(self):
        self.cerrar_ticket()
        revision.liberar(self.lider, self.conversacion)
        self.assertEqual(retencion.borrar_inactivas(), 0)  # reciente: se queda
        self.envejecer()
        self.assertEqual(retencion.borrar_inactivas(), 1)  # vieja: se borra
        self.assertFalse(Conversacion.objects.exists())

    # --- conservar ---

    def test_conservar_registra_todo_y_fija_la_revision_a_6_meses(self):
        self.cerrar_ticket()
        decision = revision.conservar(self.lider, self.conversacion, DecisionRetencion.RECLAMACION, **TEXTOS)
        self.assertEqual((decision.motivo, decision.alcance, decision.fundamento, decision.termino),
                         (DecisionRetencion.RECLAMACION, *TEXTOS.values()))
        self.assertEqual(decision.decidida_por, self.lider)
        self.assertEqual(decision.proxima_revision, self.hoy + relativedelta(months=6))
        self.assertEqual(self.pendientes(), [])
        self.assertTrue(self.retenida())

    def test_una_conservada_no_se_borra_aunque_sea_vieja(self):
        self.cerrar_ticket()
        revision.conservar(self.lider, self.conversacion, DecisionRetencion.AUTORIDAD, **TEXTOS)
        self.envejecer()
        self.assertEqual(retencion.borrar_inactivas(), 0)

    def test_conservar_exige_motivo_y_los_tres_textos(self):
        self.cerrar_ticket()
        for campo in TEXTOS:
            with self.assertRaises(MensajeError):
                revision.conservar(self.lider, self.conversacion, DecisionRetencion.OTRO, **{**TEXTOS, campo: '  '})
        with self.assertRaises(MensajeError):
            revision.conservar(self.lider, self.conversacion, 'inventado', **TEXTOS)
        self.assertFalse(DecisionRetencion.objects.exists())

    def test_al_llegar_la_fecha_de_revision_vuelve_a_pendiente(self):
        self.cerrar_ticket()
        revision.conservar(self.lider, self.conversacion, DecisionRetencion.INVESTIGACION, **TEXTOS)
        revisar = self.hoy + relativedelta(months=6)
        self.assertEqual(self.pendientes(revisar - timedelta(days=1)), [])
        self.assertEqual(self.pendientes(revisar), [self.conversacion.pk])
        vencida = revision.pendientes(revisar).get()
        self.assertEqual(revision.pendiente_desde(vencida), revisar)

    def test_pendiente_desde_es_el_cierre_del_ticket(self):
        self.cerrar_ticket()
        self.assertEqual(revision.pendiente_desde(revision.pendientes(self.hoy).get()), self.hoy)

    # --- quien y cuando ---

    def test_solo_un_lider_decide(self):
        self.cerrar_ticket()
        with self.assertRaisesMessage(MensajeError, 'líder'):
            revision.liberar(self.agente, self.conversacion)
        with self.assertRaisesMessage(MensajeError, 'líder'):
            revision.conservar(self.agente, self.conversacion, DecisionRetencion.OTRO, **TEXTOS)
        self.assertFalse(DecisionRetencion.objects.exists())

    def test_no_se_decide_con_el_ticket_abierto(self):
        with self.assertRaisesMessage(MensajeError, 'no está esperando'):
            revision.liberar(self.lider, self.conversacion)

    def test_no_se_decide_dos_veces_seguidas(self):
        self.cerrar_ticket()
        revision.liberar(self.lider, self.conversacion)
        with self.assertRaisesMessage(MensajeError, 'no está esperando'):
            revision.conservar(self.lider, self.conversacion, DecisionRetencion.OTRO, **TEXTOS)

    # --- un reporte posterior reabre ---

    def test_un_reporte_posterior_deja_sin_efecto_la_decision_y_queda_historial(self):
        self.cerrar_ticket()
        revision.liberar(self.lider, self.conversacion)
        nuevo = servicio.reportar(self.ana.user, self.conversacion, 'Ahora me escribe otra cosa.')
        self.assertTrue(self.retenida())  # ticket abierto
        self.assertEqual(self.pendientes(), [])
        self.cerrar_ticket(nuevo.ticket)
        self.assertEqual(self.pendientes(), [self.conversacion.pk])  # la liberacion anterior ya no vale
        revision.conservar(self.lider, self.conversacion, DecisionRetencion.RECLAMACION, **TEXTOS)
        self.assertEqual(self.conversacion.decisiones.count(), 2)  # historial: se conserva la anterior
        self.assertEqual(self.conversacion.decisiones.first().decision, DecisionRetencion.CONSERVAR)

    # --- las otras reglas usan la misma fuente ---

    def test_al_borrar_una_cuenta_con_su_conversacion_liberada_se_borra_todo(self):
        self.cerrar_ticket()
        revision.liberar(self.lider, self.conversacion)
        # La cuenta se seudonimiza por sus pagos (S1); lo que se prueba aqui es que la conversacion no se retiene.
        supresion.suprimir_cuenta(CustomUser.objects.get(pk=self.ana.user_id))
        self.assertFalse(Conversacion.objects.exists())

    def test_al_borrar_una_cuenta_con_su_conversacion_pendiente_se_conserva(self):
        self.cerrar_ticket()
        self.assertFalse(supresion.suprimir_cuenta(CustomUser.objects.get(pk=self.ana.user_id)))
        self.assertTrue(Conversacion.objects.filter(pk=self.conversacion.pk).exists())
