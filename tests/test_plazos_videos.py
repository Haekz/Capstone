"""Plazos del agregado de videos (fase 5a): aviso al profesor 3 dias antes de cada fecha y ticket a soporte si se atrasa.

Politica (docs/POLITICA_PAQUETES.md, seccion 12). Corre a diario dentro de tareas_diarias. El ticket se abre como
conversacion a nombre del profesor: soporte lo atiende en su pantalla de siempre y el profesor puede responder.
Los paquetes se arman relativos a hoy: Progreso tiene fechas limite el dia 30 (2 videos) y el 60 (4 en total).
"""

from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from alumnos import paquetes
from alumnos.management.commands.tareas_diarias import TAREAS
from alumnos.models import PaqueteClases
from alumnos.models.videos import VideoCompartido
from notificaciones.models import Notificacion
from soporte.models import Ticket
from tests.test_paquetes import Escenario
from user_profesor import plazos_videos


class PlazosVideosTests(Escenario):

    def paquete(self, dia, alumno=None, profesor=None):
        """Paquete Progreso con agregado de 4 videos, que hoy va en su dia ``dia`` (comprado hace ``dia`` dias)."""
        inicio = timezone.now() - timedelta(days=dia)
        return PaqueteClases.objects.create(
            alumno=alumno or self.ana, profesor=profesor or self.profe, plan='progreso', clases=4, tarifa=15000,
            monto=59000, videos=4, monto_videos=4 * paquetes.PRECIO_VIDEO, dias=60,
            buy_order=f'PQ{PaqueteClases.objects.count():024d}', estado=PaqueteClases.ESTADO_ACTIVA,
            fecha_fin=inicio + timedelta(days=60))

    def compartir(self, paquete, cuantos):
        VideoCompartido.objects.bulk_create(
            [VideoCompartido(paquete=paquete, video_id=f'{paquete.pk:012d}{n:012d}') for n in range(cuantos)])

    def avisos(self, profesor=None):
        return list(Notificacion.objects.filter(usuario=(profesor or self.profe).user).values_list('texto', flat=True))

    def tickets(self):
        return Ticket.objects.filter(categoria=Ticket.VIDEOS, titulo=plazos_videos.TITULO_ATRASO)

    # --- aviso 3 dias antes ---
    def test_avisa_al_profesor_3_dias_antes_de_la_fecha(self):
        self.paquete(dia=27)
        self.assertEqual(plazos_videos.revisar(), (1, 0))
        [aviso] = self.avisos()
        self.assertIn('3 días para compartir 2 videos con Ana', aviso)
        [correo] = mail.outbox
        self.assertEqual(correo.to, [self.profe.user.email])

    def test_solo_ese_dia(self):
        for dia in (26, 28):
            self.paquete(dia=dia)
        self.assertEqual(plazos_videos.revisar(), (0, 0))
        self.assertEqual(self.avisos(), [])

    def test_si_ya_cumplio_esa_fecha_avisa_de_la_siguiente(self):
        self.compartir(self.paquete(dia=27), 2)  # ya entrego los 2 del dia 30
        self.assertEqual(plazos_videos.revisar(), (0, 0))
        self.compartir(self.paquete(dia=57, alumno=self.beto), 2)  # al dia 57 le faltan 2 para el dia 60
        self.assertEqual(plazos_videos.revisar(), (1, 0))
        self.assertIn('2 videos con Beto', self.avisos()[0])

    # --- ticket por atraso ---
    def test_si_se_atrasa_abre_un_ticket_a_su_nombre_para_soporte(self):
        self.paquete(dia=31)
        self.assertEqual(plazos_videos.revisar(), (0, 1))
        [ticket] = self.tickets()
        self.assertEqual((ticket.autor, ticket.estado), (self.profe.user, Ticket.ABIERTO))
        self.assertTrue(ticket.es_conversacion)  # soporte lo atiende en la pantalla de conversacion
        self.assertIn('Ana', ticket.descripcion)
        self.assertIn('faltan 2', ticket.descripcion)

    def test_no_repite_el_ticket_mientras_siga_abierto(self):
        self.paquete(dia=31)
        plazos_videos.revisar()
        self.assertEqual(plazos_videos.revisar(), (0, 0))
        self.assertEqual(self.tickets().count(), 1)

    def test_un_solo_ticket_por_profesor_con_todos_sus_atrasos(self):
        self.paquete(dia=31)
        self.paquete(dia=35, alumno=self.beto)
        self.paquete(dia=31, profesor=self.otro)
        self.assertEqual(plazos_videos.revisar(), (0, 2))
        mio = self.tickets().get(autor=self.profe.user)
        self.assertIn('Ana', mio.descripcion)
        self.assertIn('Beto', mio.descripcion)

    def test_si_ya_compartio_no_hay_atraso(self):
        self.compartir(self.paquete(dia=31), 2)
        self.assertEqual(plazos_videos.revisar(), (0, 0))

    def test_un_paquete_vencido_ya_no_se_revisa(self):
        self.paquete(dia=61)
        self.assertEqual(plazos_videos.revisar(), (0, 0))

    # --- dentro de las tareas diarias ---
    def test_corre_en_las_tareas_diarias(self):
        self.assertIn('avisar_entregas_videos', TAREAS)
        self.paquete(dia=27)
        salida = StringIO()
        call_command('avisar_entregas_videos', stdout=salida)
        self.assertIn('Avisos: 1. Tickets: 0.', salida.getvalue())
