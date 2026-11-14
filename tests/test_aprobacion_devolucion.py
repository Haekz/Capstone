"""Aprobacion del administrador para devolver videos a mano (decidido 13-nov, opcion A).

Si Transbank no puede devolver, soporte pide la aprobacion: se escala al admin con un motivo armado por el sistema, el
admin ve el monto y aprueba (queda quien y cuando) y soporte recibe la indicacion como en cualquier caso escalado.
Aqui: pedir y aprobar. Que sin aprobacion no se pueda marcar devuelta esta en test_devolucion_a_mano_requiere_aprobacion.
"""

from django.urls import reverse

from alumnos.models.videos import DevolucionVideos
from soporte.models import Escalamiento, Ticket
from soporte.tickets import abrir_reporte
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_entrega_videos_extra import Base
from tests.test_retiros import RUT_ADMIN, crear_admin, entrar_admin
from tests.test_soporte_videos import RUT_AGENTE, RUT_OTRO_AGENTE


class AprobacionDeDevolucionTests(Base):

    def setUp(self):
        super().setUp()
        self.agente = crear_agente(RUT_AGENTE, Ticket.VIDEOS)
        self.ticket = abrir_reporte(self.ana.user, Ticket.VIDEOS, 'Faltan videos', 'No me los compartio.')
        self.devolucion = DevolucionVideos.objects.create(
            paquete=self.paquete(videos=4), cantidad=2, monto=10000, ticket=self.ticket,
            registrada_por=self.agente.user, error_reembolso='Periodo de anulacion excedido')
        entrar_soporte(self.client, self.agente)
        self.admin = crear_admin()  # solo se crea; el cliente sigue siendo el agente hasta que una prueba entre como admin

    def como_admin(self):
        entrar_admin(self.client, *self.admin)

    def pedir(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('soporte_pedir_aprobacion', args=[self.ticket.pk, self.devolucion.pk]))

    def escalamiento(self):
        return Escalamiento.objects.get(ticket=self.ticket, destino=Escalamiento.AL_ADMIN)

    def aprobar(self, escalamiento):
        self.como_admin()
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('aprobar_devolucion_manual', args=[escalamiento.pk]))

    # ---- soporte pide la aprobacion ----

    def test_soporte_escala_al_admin_con_el_monto_y_el_motivo_de_transbank(self):
        respuesta = self.pedir()
        self.assertRedirects(respuesta, reverse('soporte_reporte', args=[self.ticket.pk]), fetch_redirect_response=False)
        escalamiento = self.escalamiento()
        self.assertIn('$10.000', escalamiento.motivo)
        self.assertIn('2 videos', escalamiento.motivo)
        self.assertIn('Periodo de anulacion excedido', escalamiento.motivo)
        self.assertEqual(escalamiento.autor, self.agente.user)
        self.devolucion.refresh_from_db()
        self.assertEqual(self.devolucion.escalamiento, escalamiento)
        self.assertIsNone(self.devolucion.aprobada)  # pedir no es aprobar

    def test_no_se_pide_dos_veces_mientras_el_admin_no_responde(self):
        self.pedir()
        self.pedir()
        self.assertEqual(Escalamiento.objects.filter(ticket=self.ticket).count(), 1)

    def test_solo_el_agente_asignado_la_pide(self):
        entrar_soporte(self.client, crear_agente(RUT_OTRO_AGENTE, Ticket.VIDEOS))
        self.assertEqual(self.pedir().status_code, 404)
        self.assertFalse(Escalamiento.objects.exists())

    def test_no_se_pide_para_una_devolucion_ya_devuelta(self):
        DevolucionVideos.objects.filter(pk=self.devolucion.pk).update(devuelta=self.devolucion.creada)
        self.assertEqual(self.pedir().status_code, 404)

    # ---- el admin aprueba ----

    def test_el_admin_ve_el_caso_con_el_monto_y_el_boton_de_aprobar(self):
        self.pedir()
        escalamiento = self.escalamiento()
        self.como_admin()
        pagina = self.client.get(reverse('casos_escalados'))
        self.assertContains(pagina, reverse('aprobar_devolucion_manual', args=[escalamiento.pk]))
        self.assertContains(pagina, '$10.000')

    def test_aprobar_deja_quien_y_cuando_y_le_responde_a_soporte(self):
        self.pedir()
        escalamiento = self.escalamiento()
        respuesta = self.aprobar(escalamiento)
        self.assertRedirects(respuesta, reverse('casos_escalados'), fetch_redirect_response=False)
        self.devolucion.refresh_from_db()
        self.assertIsNotNone(self.devolucion.aprobada)
        self.assertEqual(self.devolucion.aprobada_por.rut, RUT_ADMIN)
        escalamiento.refresh_from_db()
        self.assertIsNotNone(escalamiento.indicado)  # soporte recibe la indicacion como siempre
        self.assertIn('$10.000', escalamiento.indicacion)

    def test_no_se_aprueba_dos_veces(self):
        self.pedir()
        escalamiento = self.escalamiento()
        self.aprobar(escalamiento)
        primera = DevolucionVideos.objects.get().aprobada
        self.aprobar(escalamiento)
        self.assertEqual(DevolucionVideos.objects.get().aprobada, primera)

    def test_quien_no_es_admin_no_aprueba(self):
        self.pedir()
        escalamiento = self.escalamiento()  # el cliente sigue siendo el agente de soporte
        self.client.post(reverse('aprobar_devolucion_manual', args=[escalamiento.pk]))
        self.assertIsNone(DevolucionVideos.objects.get().aprobada)

    def test_si_el_admin_responde_otra_cosa_no_queda_aprobada(self):
        self.pedir()
        escalamiento = self.escalamiento()
        self.como_admin()
        self.client.post(reverse('indicar_escalado', args=[escalamiento.pk]), {'indicacion': 'No: revisen el caso.'})
        self.assertIsNone(DevolucionVideos.objects.get().aprobada)
