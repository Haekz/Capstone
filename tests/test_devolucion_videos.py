"""Devolucion por videos no entregados (fase 6e, decidido 09-nov): soporte la registra desde el ticket de Videos.

Se devuelve a mano: el sistema solo registra el caso (cuanto y por que ticket) y soporte lo marca devuelto cuando
transfiere. Lo que falta = lo contratado (agregado + extras pagados) - lo compartido - lo ya devuelto. El monto lo
calcula el servidor (valor promedio por video x cantidad); soporte nunca lo escribe. Lo devuelto libera el cupo del
profesor, deja de ser atraso y no cambia lo que cobra por lo que si entrego. Solo el agente asignado al ticket.
"""

from django.core.exceptions import ValidationError
from django.urls import reverse

from alumnos import devoluciones_videos
from alumnos.models import PaqueteClases
from alumnos.models.videos import DevolucionVideos
from apoderados.models import Apoderado
from notificaciones.models import Notificacion
from soporte.models import Ticket
from soporte.tickets import abrir_reporte
from tests.test_apoderados import crear_agente, crear_apoderado, entrar_soporte
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_entrega_videos_extra import PENDIENTE, Base
from tests.test_soporte_videos import RUT_AGENTE, RUT_OTRO_AGENTE
from tests.test_ver_videos import RUT_APODERADO, RUT_MENOR
from user_profesor import entregas
from user_profesor.saldos import calcular_saldos


class ReglasTests(Base):

    def setUp(self):
        super().setUp()
        self.agente = crear_agente(RUT_AGENTE, Ticket.VIDEOS)
        self.ticket = self.reclamo(self.ana.user)

    def reclamo(self, autor, estudiante=None):
        return abrir_reporte(autor, Ticket.VIDEOS, 'Mi profesor no entrego los videos', 'No me comparti\u00f3 los videos.',
                             estudiante=estudiante)

    def devolver(self, paquete, cantidad, ticket=None):
        return devoluciones_videos.registrar(ticket or self.ticket, paquete.pk, cantidad, self.agente.user)

    def test_lo_que_falta_es_lo_contratado_menos_lo_compartido(self):
        paquete = self.paquete(videos=4)
        self.compartir(paquete, 1)
        self.assertEqual(devoluciones_videos.sin_entregar(paquete), 3)

    def test_cuentan_los_extra_pagados_y_no_los_pendientes(self):
        paquete = self.paquete(videos=1)
        self.extra(paquete, 2)
        self.extra(paquete, 3, estado=PENDIENTE)
        self.assertEqual(devoluciones_videos.sin_entregar(paquete), 3)

    def test_el_valor_es_el_promedio_de_lo_pagado(self):
        paquete = self.paquete(videos=1)  # $5.000
        self.extra(paquete, 3)  # $13.500: en total $18.500 por 4 videos
        self.assertEqual(devoluciones_videos.valor_por_video(paquete), 18500 // 4)

    def test_el_monto_lo_calcula_el_servidor(self):
        paquete = self.paquete(videos=1)
        self.extra(paquete, 3)
        devolucion = self.devolver(paquete, 2)
        self.assertEqual((devolucion.cantidad, devolucion.monto), (2, 2 * (18500 // 4)))
        self.assertEqual((devolucion.paquete, devolucion.ticket, devolucion.registrada_por, devolucion.devuelta),
                         (paquete, self.ticket, self.agente.user, None))

    def test_no_se_devuelve_mas_de_lo_que_falta(self):
        paquete = self.paquete(videos=3)
        self.compartir(paquete, 1)  # faltan 2
        for cantidad in (0, -1, 3):
            with self.subTest(cantidad=cantidad), self.assertRaises(ValidationError):
                self.devolver(paquete, cantidad)
        self.assertEqual(DevolucionVideos.objects.count(), 0)

    def test_no_se_devuelve_dos_veces_lo_mismo(self):
        paquete = self.paquete(videos=4)
        self.devolver(paquete, 3)
        with self.assertRaises(ValidationError):
            self.devolver(paquete, 2)  # solo queda 1
        self.devolver(paquete, 1)
        self.assertEqual(devoluciones_videos.sin_entregar(paquete), 0)

    def test_solo_paquetes_pagados_del_alumno_del_ticket(self):
        ajeno = self.paquete(videos=2, alumno=self.beto)
        sin_pagar = self.paquete(videos=2)
        PaqueteClases.objects.filter(pk=sin_pagar.pk).update(estado=PaqueteClases.ESTADO_PENDIENTE)
        for paquete in (ajeno, sin_pagar):
            with self.subTest(paquete=paquete.pk), self.assertRaises(ValidationError):
                self.devolver(paquete, 1)
        with self.assertRaises(ValidationError):
            devoluciones_videos.registrar(self.ticket, 'no-es-un-id', 1, self.agente.user)
        self.assertEqual(DevolucionVideos.objects.count(), 0)

    def test_un_paquete_ya_vencido_tambien_se_devuelve(self):
        self.assertEqual(self.devolver(self.paquete(videos=2, dias_restantes=-5), 2).cantidad, 2)

    def test_el_ticket_de_otra_categoria_no_sirve(self):
        otro = abrir_reporte(self.ana.user, Ticket.PAGOS, 'Cobro', 'Me cobraron de mas.')
        with self.assertRaises(ValidationError):
            self.devolver(self.paquete(videos=2), 1, ticket=otro)

    def test_el_apoderado_reclama_por_su_estudiante(self):
        apoderado = crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO)
        menor = crear_menor_vinculado(apoderado, rut=RUT_MENOR).alumno
        ticket = self.reclamo(apoderado.user, estudiante=menor)
        self.assertEqual(self.devolver(self.paquete(videos=2, alumno=menor), 1, ticket=ticket).cantidad, 1)
        with self.assertRaises(ValidationError):
            self.devolver(self.paquete(videos=2), 1, ticket=ticket)  # el paquete de otro alumno no

    # --- efectos en el resto del sistema ---
    def test_lo_devuelto_libera_el_cupo_del_profesor(self):
        paquete = self.paquete(videos=4)
        self.devolver(paquete, 3)  # el profesor ya solo debe 1
        self.compartir(paquete, 1)
        with self.assertRaisesMessage(ValidationError, 'Ya compartiste los 1 videos'):
            entregas.compartir(self.profe.id_profesor, paquete.pk, self.videos[1])

    def test_lo_devuelto_deja_de_ser_atraso(self):
        paquete = self.paquete()
        self.extra(paquete, 2, pagada_hace=15)
        [antes] = entregas.pendientes(self.profe.id_profesor)
        self.assertTrue(antes['atrasada'])
        self.devolver(paquete, 2)
        [despues] = entregas.pendientes(self.profe.id_profesor)
        self.assertEqual((despues['atrasada'], despues['falta'], despues['videos']), (False, 0, 0))

    def test_el_profesor_cobra_lo_mismo_por_lo_que_si_entrego(self):
        paquete = self.paquete(videos=1)
        self.extra(paquete, 3)
        self.compartir(paquete, 2)
        self.devolver(paquete, 2)  # quedaban 2 sin entregar
        self.assertEqual(calcular_saldos(self.profe)['total_ganado'], 2 * (18500 // 4))

    def test_marcar_devuelta_es_una_sola_vez(self):
        devolucion = self.devolver(self.paquete(videos=2), 1)
        devoluciones_videos.marcar_devuelta(self.ticket, devolucion.pk)
        devolucion.refresh_from_db()
        primera = devolucion.devuelta
        self.assertIsNotNone(primera)
        with self.assertRaises(ValidationError):
            devoluciones_videos.marcar_devuelta(self.ticket, devolucion.pk)
        devolucion.refresh_from_db()
        self.assertEqual(devolucion.devuelta, primera)


class SoporteTests(Base):

    def setUp(self):
        super().setUp()
        self.agente = crear_agente(RUT_AGENTE, Ticket.VIDEOS)  # el unico habilitado: se le asigna el ticket
        self.ticket = abrir_reporte(self.ana.user, Ticket.VIDEOS, 'Mi profesor no entrego los videos', 'Faltan videos.')
        self.paquete_ana = self.paquete(videos=4)  # $20.000: $5.000 cada uno
        entrar_soporte(self.client, self.agente)

    def pagina(self):
        return self.client.get(reverse('soporte_reporte', args=[self.ticket.pk]))

    def url(self):
        return reverse('soporte_devolver_videos', args=[self.ticket.pk])

    def devolver(self, cantidad='2', paquete=None, **extra):
        return self.client.post(self.url(), {'paquete': (paquete or self.paquete_ana).pk, 'cantidad': cantidad, **extra})

    def test_el_panel_ofrece_la_devolucion_con_lo_que_falta_y_sus_montos(self):
        pagina = self.pagina()
        self.assertContains(pagina, f'action="{self.url()}"')
        self.assertContains(pagina, '4 videos')
        self.assertContains(pagina, '$20.000')  # los 4

    def test_si_no_falta_ninguno_no_hay_formulario(self):
        self.compartir(self.paquete_ana, 4)
        self.assertNotContains(self.pagina(), self.url())

    def test_al_registrar_queda_en_el_ticket_y_se_avisa_al_profesor(self):
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.devolver('2')
        self.assertRedirects(respuesta, reverse('soporte_reporte', args=[self.ticket.pk]), fetch_redirect_response=False)
        [devolucion] = DevolucionVideos.objects.all()
        self.assertEqual((devolucion.cantidad, devolucion.monto), (2, 10000))
        [mensaje] = self.ticket.mensajes.all()
        self.assertTrue(mensaje.de_soporte)
        self.assertIn('$10.000', mensaje.texto)
        [aviso] = Notificacion.objects.filter(usuario=self.profe.user)
        self.assertIn('Ana', aviso.texto)
        self.assertIn('2 videos', aviso.texto)

    def test_el_monto_no_lo_pone_el_navegador(self):
        self.devolver('2', monto='1', monto_devolucion='1')
        self.assertEqual(DevolucionVideos.objects.get().monto, 10000)

    def test_mas_de_lo_que_falta_no_se_registra_y_se_explica(self):
        respuesta = self.client.post(self.url(), {'paquete': self.paquete_ana.pk, 'cantidad': '5'}, follow=True)
        self.assertEqual(DevolucionVideos.objects.count(), 0)
        self.assertEqual(self.ticket.mensajes.count(), 0)
        self.assertContains(respuesta, 'Solo faltan 4')

    def test_solo_el_agente_asignado(self):
        otro = crear_agente(RUT_OTRO_AGENTE, Ticket.VIDEOS)
        entrar_soporte(self.client, otro)
        self.assertEqual(self.devolver().status_code, 404)
        self.assertEqual(DevolucionVideos.objects.count(), 0)

    def test_solo_en_tickets_de_videos(self):
        pagos = abrir_reporte(self.ana.user, Ticket.PAGOS, 'Cobro', 'Me cobraron de mas.')
        respuesta = self.client.post(reverse('soporte_devolver_videos', args=[pagos.pk]),
                                     {'paquete': self.paquete_ana.pk, 'cantidad': '1'})
        self.assertEqual(respuesta.status_code, 404)

    def test_solo_por_post(self):
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_marcar_devuelta_queda_en_el_ticket_y_no_se_repite(self):
        self.devolver('2')
        devolucion = DevolucionVideos.objects.get()
        url = reverse('soporte_devolucion_hecha', args=[self.ticket.pk, devolucion.pk])
        self.assertContains(self.pagina(), url)  # el boton, mientras este por devolver
        self.assertRedirects(self.client.post(url), reverse('soporte_reporte', args=[self.ticket.pk]),
                             fetch_redirect_response=False)
        devolucion.refresh_from_db()
        self.assertIsNotNone(devolucion.devuelta)
        self.assertEqual(self.ticket.mensajes.count(), 2)  # el de registrar y el de devuelta
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertNotContains(self.pagina(), url)

    def test_no_se_marca_la_devolucion_de_otro_ticket(self):
        self.devolver('1')
        devolucion = DevolucionVideos.objects.get()
        otro = abrir_reporte(self.beto.user, Ticket.VIDEOS, 'Otro reclamo', 'Otro.')
        self.assertEqual(self.client.post(reverse('soporte_devolucion_hecha', args=[otro.pk, devolucion.pk])).status_code, 404)
        devolucion.refresh_from_db()
        self.assertIsNone(devolucion.devuelta)
