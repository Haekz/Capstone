"""Entrega de videos (agregado de videos, fase 3a): el profesor ve a quién le debe videos y se los comparte.

Reglas (decididas 08-nov): comparte videos de SU biblioteca, solo a paquetes vigentes y suyos, sin pasar de los que
el alumno pagó, y nunca el mismo video dos veces al mismo alumno (si renueva, contenido nuevo). Las fechas límite
salen del plan (alumnos/paquetes.py). Mongo en memoria (mongomock); Webpay no interviene.
"""

from datetime import datetime, timedelta, timezone as utc

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from types import SimpleNamespace

from alumnos import paquetes
from alumnos.models import PaqueteClases
from alumnos.models.videos import VideoCompartido
from comunidad import mongo
from comunidad.tests.base import MongoTestCase
from tests.test_paquetes import RUT_ANA, RUT_OTRO, RUT_PROFE, Escenario
from tests.test_videoteca import archivo
from user_profesor import entregas, videoteca

INICIO = datetime(2026, 11, 1, 12, 0, tzinfo=utc.utc)


class FechasDeEntregaTests(SimpleTestCase):

    def fechas(self, plan):
        return [(f.day + (f.month - 11) * 30, n) for f, n in paquetes.fechas_entrega(paquetes.POR_CODIGO[plan], INICIO)]

    def test_cada_fecha_pide_los_videos_acumulados(self):
        self.assertEqual(self.fechas('flexible'), [(15, 1)])
        self.assertEqual(self.fechas('progreso'), [(31, 2), (31 + 30, 4)])
        self.assertEqual(self.fechas('intensivo')[-1][1], 6)

    def test_el_ultimo_acumulado_es_todo_lo_comprado(self):
        for plan in paquetes.PLANES:
            with self.subTest(plan=plan.codigo):
                self.assertEqual(paquetes.fechas_entrega(plan, INICIO)[-1][1], plan.videos)


class EntregasTests(MongoTestCase, Escenario):

    def setUp(self):
        super().setUp()
        mongo.get_client().options = SimpleNamespace(timeout=None)  # GridFS lo pide; mongomock no lo trae
        self.entrar(RUT_PROFE)
        self.videos = [videoteca.subir(self.profe.id_profesor, self.clase.asignatura_id, f'Video {n}', archivo())
                       for n in range(6)]

    def paquete(self, alumno=None, plan='progreso', videos=4, estado=PaqueteClases.ESTADO_ACTIVA, dias_restantes=60,
                profesor=None, **extra):
        return PaqueteClases.objects.create(
            alumno=alumno or self.ana, profesor=profesor or self.profe, plan=plan, clases=4, tarifa=15000, monto=59000,
            videos=videos, monto_videos=videos * paquetes.PRECIO_VIDEO, dias=60,
            buy_order=f'PQ{PaqueteClases.objects.count():024d}', estado=estado,
            fecha_fin=timezone.now() + timedelta(days=dias_restantes), **extra)

    def compartir(self, paquete, video):
        return self.client.post(reverse('compartir_video'), {'paquete': paquete.pk, 'video': video}).json()

    def entregas(self):
        return self.client.get(reverse('videos_profesor')).json()['entregas']

    def test_lista_a_quien_le_debe_videos_con_la_proxima_fecha(self):
        self.paquete()
        [fila] = self.entregas()
        self.assertEqual((fila['alumno'], fila['plan'], fila['compartidos'], fila['videos'], fila['falta']),
                         ('Ana', 'Progreso', 0, 4, 2))
        self.assertFalse(fila['atrasada'])
        # Solo lo necesario para entregar: de la alumna, el nombre de pila (nada de RUT, correo ni apellido).
        self.assertEqual(set(fila), {'paquete', 'alumno', 'plan', 'compartidos', 'videos', 'falta', 'atrasada', 'proxima'})

    def test_marca_atrasada_la_entrega_cuya_fecha_ya_paso(self):
        self.paquete(dias_restantes=10)  # empezó hace 50 días: el límite del día 30 ya pasó
        self.assertTrue(self.entregas()[0]['atrasada'])

    def test_no_lista_paquetes_ajenos_vencidos_pendientes_ni_sin_videos(self):
        self.paquete(profesor=self.otro)
        self.paquete(alumno=self.beto, dias_restantes=-1)
        self.paquete(alumno=self.beto, estado=PaqueteClases.ESTADO_PENDIENTE)
        self.paquete(alumno=self.beto, videos=0)
        self.assertEqual(self.entregas(), [])

    def test_comparte_y_cuenta(self):
        paquete = self.paquete()
        self.assertTrue(self.compartir(paquete, self.videos[0])['success'])
        self.assertEqual(self.entregas()[0]['compartidos'], 1)
        self.assertTrue(VideoCompartido.objects.filter(paquete=paquete, video_id=self.videos[0]).exists())

    def test_no_comparte_mas_de_los_que_el_alumno_pago(self):
        paquete = self.paquete(videos=2)
        self.assertTrue(self.compartir(paquete, self.videos[0])['success'])
        self.assertTrue(self.compartir(paquete, self.videos[1])['success'])
        r = self.compartir(paquete, self.videos[2])
        self.assertFalse(r['success'])
        self.assertIn('2', r['message'])
        self.assertEqual(VideoCompartido.objects.count(), 2)

    def test_no_repite_un_video_al_mismo_alumno_ni_en_otro_paquete(self):
        paquete = self.paquete()
        self.compartir(paquete, self.videos[0])
        self.assertFalse(self.compartir(paquete, self.videos[0])['success'])
        renovado = self.paquete()
        self.assertFalse(self.compartir(renovado, self.videos[0])['success'])  # renovó: debe ser contenido nuevo
        self.assertTrue(self.compartir(renovado, self.videos[1])['success'])

    def test_el_mismo_video_si_sirve_para_otro_alumno(self):
        self.compartir(self.paquete(), self.videos[0])
        self.assertTrue(self.compartir(self.paquete(alumno=self.beto), self.videos[0])['success'])

    def test_solo_comparte_con_sus_paquetes_y_desde_su_biblioteca(self):
        ajeno = self.paquete(profesor=self.otro)
        self.assertFalse(self.compartir(ajeno, self.videos[0])['success'])
        self.entrar(RUT_OTRO)
        otro_video = videoteca.subir(self.otro.id_profesor, self.clase_otro.asignatura_id, 'Del otro', archivo())
        propio = self.paquete()
        self.entrar(RUT_PROFE)
        self.assertFalse(self.compartir(propio, otro_video)['success'])  # video de otro profesor
        self.assertEqual(VideoCompartido.objects.count(), 0)

    def test_no_comparte_con_paquetes_vencidos_pendientes_ni_sin_agregado(self):
        for datos in ({'dias_restantes': -1}, {'estado': PaqueteClases.ESTADO_PENDIENTE}, {'videos': 0}):
            with self.subTest(datos=datos):
                self.assertFalse(self.compartir(self.paquete(**datos), self.videos[0])['success'])
        self.assertEqual(VideoCompartido.objects.count(), 0)

    def test_datos_raros_no_rompen(self):
        for paquete, video in (('abc', self.videos[0]), ('', ''), (999999, self.videos[0]), (self.paquete().pk, 'no-es-id'),
                               (self.paquete().pk, '0' * 24)):
            with self.subTest(paquete=paquete, video=video):
                r = self.client.post(reverse('compartir_video'), {'paquete': paquete, 'video': video})
                self.assertEqual(r.status_code, 200)
                self.assertFalse(r.json()['success'])

    def test_un_alumno_no_comparte(self):
        paquete = self.paquete()
        self.entrar(RUT_ANA)
        self.client.post(reverse('compartir_video'), {'paquete': paquete.pk, 'video': self.videos[0]})
        self.assertEqual(VideoCompartido.objects.count(), 0)

    def test_la_pestana_trae_la_tarjeta_de_entregas(self):
        pagina = self.client.get(reverse('panel_profesor')).content.decode()
        self.assertIn('id="profe-entregas-card"', pagina)
        self.assertIn(reverse('compartir_video'), pagina)

    def test_el_servicio_avisa_con_validation_error(self):
        with self.assertRaises(ValidationError):
            entregas.compartir(self.profe.id_profesor, 999999, self.videos[0])
