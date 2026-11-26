"""Borrado de videos con 30 dias sin actividad, avisando 7 dias antes (decidido 23-nov).

La regla (user_profesor/limpieza_videos.py): actividad = lo mas reciente entre la subida, el ultimo compartido y la
ultima vez que alguien lo abrio. A los 23 dias se avisa; se borra 7 dias despues del aviso, aunque el alumno tenga
su paquete vigente (por eso el aviso). Un reclamo abierto de Videos de apoyo lo protege. Para simular el paso de los
dias se pasa `ahora` a revisar() y las fechas de la ficha se ponen a mano.
"""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from alumnos.management.commands.tareas_diarias import TAREAS
from alumnos.models import Video
from apoderados.models import Apoderado
from notificaciones.models import Notificacion
from soporte.models import Ticket
from soporte.tickets import abrir_reporte
from tests.test_apoderados import crear_agente, crear_apoderado
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA
from tests.test_ver_videos import RUT_APODERADO, RUT_MENOR, Base
from user_profesor import almacen_videos, limpieza_videos, videoteca

RUT_AGENTE = '10000001-9'


def en(dias, horas=1):
    """Un `ahora` simulado: pasados esos dias (y una hora de margen) desde que se subio el video."""
    return timezone.now() + timedelta(days=dias, hours=horas)


class Reglas(Base):

    def avisos(self, usuario):
        return list(Notificacion.objects.filter(usuario=usuario))

    def ficha(self):
        return videoteca.ficha(self.video)

    def poner(self, **campos):
        Video.objects.filter(pk=self.video).update(**campos)


class BorradoPorInactividadTests(Reglas):

    def setUp(self):
        super().setUp()
        self.compartir(self.ana)  # con paquete vigente de 60 dias

    def test_con_actividad_reciente_no_se_toca(self):
        self.assertEqual(limpieza_videos.revisar(en(22)), (0, 0))
        self.assertIsNone(self.ficha().aviso_borrado)

    def test_a_los_23_dias_avisa_al_profesor_y_a_quien_lo_tiene_pero_no_borra(self):
        self.assertEqual(limpieza_videos.revisar(en(23)), (1, 0))  # beto no tiene el video: no recibe nada
        [aviso_profesor] = self.avisos(self.profe.user)
        [aviso_alumna] = self.avisos(self.ana.user)
        fecha = f'{timezone.localdate(en(30)):%d/%m/%Y}'
        for aviso in (aviso_profesor, aviso_alumna):
            self.assertIn('«Factorización»', aviso.texto)
            self.assertIn(fecha, aviso.texto)
        self.assertEqual(self.avisos(self.beto.user), [])
        self.assertIsNotNone(self.ficha().aviso_borrado)
        self.assertEqual(len(self.r2.objetos), 1)  # sigue todo en R2

    def test_no_avisa_dos_veces(self):
        limpieza_videos.revisar(en(23))
        self.assertEqual(limpieza_videos.revisar(en(25)), (0, 0))
        self.assertEqual(len(self.avisos(self.profe.user)), 1)

    def test_se_borra_7_dias_despues_del_aviso_aunque_el_paquete_siga_vigente(self):
        limpieza_videos.revisar(en(23))
        self.assertEqual(limpieza_videos.revisar(en(29)), (0, 0))  # faltan unas horas
        self.assertEqual(limpieza_videos.revisar(en(31)), (0, 1))
        self.assertIsNone(self.ficha())
        self.assertEqual(self.r2.objetos, {})

    def test_si_el_cron_se_salta_dias_igual_hay_7_dias_de_aviso(self):
        self.assertEqual(limpieza_videos.revisar(en(60)), (1, 0))  # primera vez que corre: avisa, no borra
        self.assertIsNotNone(self.ficha())

    def test_abrirlo_despues_del_aviso_lo_salva(self):
        base = timezone.now()
        self.poner(aviso_borrado=base - timedelta(days=8), ultima_vista=base - timedelta(days=1),
                   subido=base - timedelta(days=40))
        self.assertEqual(limpieza_videos.revisar(base), (0, 0))
        self.assertIsNotNone(self.ficha())

    def test_compartirlo_despues_del_aviso_lo_salva(self):
        base = timezone.now()
        self.poner(aviso_borrado=base - timedelta(days=8), subido=base - timedelta(days=40))
        self.compartir(self.beto)  # ahora: mas nuevo que el aviso
        self.assertEqual(limpieza_videos.revisar(base), (0, 0))
        self.assertIsNotNone(self.ficha())

    def test_un_video_nunca_compartido_tambien_se_avisa_y_se_borra(self):
        solo = self.subir('Sin compartir')
        self.assertEqual(limpieza_videos.revisar(en(23)), (2, 0))  # este y el de setUp
        self.assertEqual(limpieza_videos.revisar(en(31)), (0, 2))
        self.assertIsNone(videoteca.ficha(solo))

    def test_un_reclamo_abierto_lo_protege_hasta_que_se_cierre(self):
        crear_agente(RUT_AGENTE, Ticket.VIDEOS)
        abrir_reporte(self.ana.user, Ticket.VIDEOS, 'Problema con un video de apoyo', f'Video: {self.video}\nNo es de Álgebra.')
        self.assertEqual(limpieza_videos.revisar(en(60)), (0, 0))
        self.assertIsNone(self.ficha().aviso_borrado)
        Ticket.objects.update(estado=Ticket.CERRADO)
        self.assertEqual(limpieza_videos.revisar(en(60)), (1, 0))

    def test_abrir_el_video_anota_la_actividad(self):
        self.assertIsNone(self.ficha().ultima_vista)
        self.entrar(RUT_ANA)
        self.assertEqual(self.client.get(reverse('ver_video', args=[self.video])).status_code, 302)
        self.assertIsNotNone(self.ficha().ultima_vista)

    def test_un_video_que_no_se_puede_ver_no_anota_actividad(self):
        self.entrar(RUT_ANA)
        otro = self.subir('No es de ella')
        self.assertEqual(self.client.get(reverse('ver_video', args=[otro])).status_code, 404)
        self.assertIsNone(videoteca.ficha(otro).ultima_vista)


class AvisoAlApoderadoDelMenorTests(Reglas):

    def test_un_menor_no_recibe_el_aviso_pero_si_su_apoderado(self):
        apoderado = crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO)
        vinculo = crear_menor_vinculado(apoderado, rut=RUT_MENOR)
        self.compartir(vinculo.alumno)
        limpieza_videos.revisar(en(23))
        self.assertEqual(self.avisos(vinculo.alumno.user), [])
        [aviso] = self.avisos(apoderado.user)
        self.assertIn(f'«Factorización» de {vinculo.alumno.user.first_name}', aviso.texto)


class ComandoDiarioTests(Reglas):

    def test_corre_con_las_tareas_diarias(self):
        self.assertIn('borrar_videos_inactivos', TAREAS)

    def test_informa_solo_cantidades(self):
        salida = StringIO()
        call_command('borrar_videos_inactivos', stdout=salida)
        self.assertEqual(salida.getvalue().strip(), 'Avisados: 0. Borrados: 0.')

    @override_settings(R2_CONFIGURADO=False)
    def test_sin_r2_termina_bien_para_no_alertar_todos_los_dias(self):
        almacen_videos.restablecer()
        salida = StringIO()
        call_command('borrar_videos_inactivos', stdout=salida)
        self.assertIn('desactivados', salida.getvalue())
