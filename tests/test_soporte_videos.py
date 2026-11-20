"""Soporte ve y retira un video reportado desde su ticket de Videos de apoyo (fase 5e, decidido 09-nov).

Mismo patron que el horario (agenda/views_soporte.py): el detalle del ticket muestra un panel con los videos que
nombra el reclamo, pero solo los que de verdad se compartieron con ese estudiante (un id ajeno se ignora). Ver: el
agente asignado o un lider. Retirar: solo el agente asignado; queda como mensaje de soporte en el ticket (registro y
aviso al que reclamo) y se avisa al profesor. El retirado deja de verse, de pagarse y de ocupar cupo (fase 5d).
"""

from django.urls import reverse

from alumnos.models.videos import VideoCompartido
from apoderados.models import Apoderado
from notificaciones.models import Notificacion
from soporte.models import Ticket
from soporte.tickets import abrir_reporte
from tests.test_apoderados import crear_agente, crear_apoderado, entrar_soporte
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA
from tests.test_ver_videos import RUT_APODERADO, RUT_MENOR, Base, cuerpo

RUT_AGENTE, RUT_OTRO_AGENTE, RUT_LIDER = '10000001-9', '10000002-7', '10000003-5'


class SoporteVideosTests(Base):

    def setUp(self):
        super().setUp()
        self.agente = crear_agente(RUT_AGENTE, Ticket.VIDEOS)  # el unico habilitado: se le asigna el ticket
        self.compartir(self.ana)
        self.ticket = self.reclamo(self.ana.user, self.video)
        entrar_soporte(self.client, self.agente)

    def reclamo(self, autor, video, estudiante=None):
        return abrir_reporte(autor, Ticket.VIDEOS, 'Problema con un video de apoyo',
                             f'Video: {video}\nNo es de Álgebra.', estudiante=estudiante)

    def ver(self, video=None, ticket=None):
        return self.client.get(reverse('soporte_ver_video', args=[(ticket or self.ticket).pk, video or self.video]))

    def retirar(self, video=None, ticket=None):
        return self.client.post(reverse('soporte_retirar_video', args=[(ticket or self.ticket).pk, video or self.video]))

    def retirados(self):
        return VideoCompartido.objects.filter(retirado__isnull=False).count()

    def test_el_detalle_del_ticket_muestra_el_video_para_verlo_y_retirarlo(self):
        pagina = self.client.get(reverse('soporte_reporte', args=[self.ticket.pk]))
        self.assertContains(pagina, reverse('soporte_ver_video', args=[self.ticket.pk, self.video]))
        self.assertContains(pagina, reverse('soporte_retirar_video', args=[self.ticket.pk, self.video]))

    def test_el_agente_lo_ve_para_revisarlo(self):
        self.assertEqual(cuerpo(self.ver()), self.contenido)

    def test_al_retirarlo_queda_en_el_ticket_se_avisa_al_profesor_y_el_alumno_ya_no_lo_ve(self):
        with self.captureOnCommitCallbacks(execute=True):  # el aviso al profesor sale al confirmar el retiro
            respuesta = self.retirar()
        self.assertRedirects(respuesta, reverse('soporte_reporte', args=[self.ticket.pk]), fetch_redirect_response=False)
        self.assertEqual(self.retirados(), 1)
        [mensaje] = self.ticket.mensajes.all()
        self.assertTrue(mensaje.de_soporte)
        self.assertIn('Retiramos el video', mensaje.texto)
        [aviso] = Notificacion.objects.filter(usuario=self.profe.user)
        self.assertIn('Ana', aviso.texto)
        self.assertIn('2 días hábiles', aviso.texto)
        self.entrar(RUT_ANA)
        self.assertEqual(self.client.get(reverse('videos_alumno')).json()['videos'], [])

    def test_no_se_retira_dos_veces(self):
        self.retirar()
        self.assertEqual(self.retirar().status_code, 404)
        self.assertEqual(self.ticket.mensajes.count(), 1)

    def test_un_id_ajeno_en_el_reclamo_se_ignora(self):
        ajeno = self.subir('De otro alumno')
        self.compartir(self.beto, ajeno)
        ticket = self.reclamo(self.ana.user, ajeno)
        self.assertNotContains(self.client.get(reverse('soporte_reporte', args=[ticket.pk])),
                               reverse('soporte_ver_video', args=[ticket.pk, ajeno]))
        self.assertEqual(self.ver(ajeno, ticket).status_code, 404)
        self.assertEqual(self.retirar(ajeno, ticket).status_code, 404)
        self.assertEqual(self.retirados(), 0)

    def test_retira_solo_el_agente_asignado_y_el_lider_puede_verlo(self):
        otro = crear_agente(RUT_OTRO_AGENTE, Ticket.VIDEOS)
        entrar_soporte(self.client, otro)
        self.assertEqual(self.ver().status_code, 404)
        self.assertEqual(self.retirar().status_code, 404)
        lider = crear_agente(RUT_LIDER, lider=True)
        entrar_soporte(self.client, lider)
        self.assertEqual(self.ver().status_code, 200)
        self.assertEqual(self.retirar().status_code, 404)  # el lider, reasignandoselo antes
        self.assertEqual(self.retirados(), 0)

    def test_retirar_es_solo_por_post(self):
        url = reverse('soporte_retirar_video', args=[self.ticket.pk, self.video])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_el_reclamo_del_apoderado_por_su_estudiante(self):
        apoderado = crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO)
        menor = crear_menor_vinculado(apoderado, rut=RUT_MENOR).alumno
        self.compartir(menor)
        ticket = self.reclamo(apoderado.user, self.video, estudiante=menor)
        self.assertEqual(self.retirar(ticket=ticket).status_code, 302)
        self.assertEqual(VideoCompartido.objects.get(paquete__alumno=menor).retirado is not None, True)
        self.assertIsNone(VideoCompartido.objects.get(paquete__alumno=self.ana).retirado)  # el de Ana no se toca
