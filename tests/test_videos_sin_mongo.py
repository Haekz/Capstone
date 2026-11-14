"""B2 (13-nov): sin MongoDB configurado no se venden videos.

Los archivos viven en MongoDB (GridFS). Sin MONGODB_URI el profesor no puede subirlos ni el alumno verlos, pero la
compra no lo revisaba: se podia cobrar un agregado o un extra que nadie iba a poder entregar. La regla es una sola,
settings.VIDEOS_A_LA_VENTA (en pruebas la prende lbwus/test_runner.py). El paquete de clases se sigue vendiendo.
Webpay va con mock.
"""

from unittest import mock

from django.contrib.messages import get_messages
from django.test import override_settings
from django.urls import reverse

from alumnos import videos_extra
from alumnos.models import PaqueteClases
from alumnos.models.videos import CompraVideosExtra
from tests.test_agregado_videos import PRECIO_PROGRESO
from tests.test_paquetes import RUT_ANA, Escenario, dar_paquete

NO_DISPONIBLES = 'Los videos de ayuda no están disponibles por ahora'


@override_settings(VIDEOS_A_LA_VENTA=False)
@mock.patch('alumnos.webpay._tx')
class SinVideosALaVentaTests(Escenario):

    def setUp(self):
        self.entrar(RUT_ANA)

    def post(self, tx, ruta, datos):
        tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        return self.client.post(reverse(ruta), datos)

    def assertAviso(self, respuesta):
        self.assertTrue(any(NO_DISPONIBLES in str(m) for m in get_messages(respuesta.wsgi_request)))

    def test_no_cobra_el_agregado(self, tx):
        respuesta = self.post(tx, 'comprar_paquete', {'plan': 'progreso', 'profesor': self.profe.id_profesor,
                                                      'videos': '1'})
        tx.return_value.create.assert_not_called()
        self.assertFalse(PaqueteClases.objects.exists())
        self.assertRedirects(respuesta, reverse('planes'), fetch_redirect_response=False)
        self.assertAviso(respuesta)
        self.assertContains(self.client.get(reverse('planes')), NO_DISPONIBLES)  # Planes lo muestra

    def test_el_paquete_solo_se_sigue_vendiendo(self, tx):
        self.post(tx, 'comprar_paquete', {'plan': 'progreso', 'profesor': self.profe.id_profesor})
        self.assertEqual(tx.return_value.create.call_args.args[2], PRECIO_PROGRESO)
        self.assertEqual(PaqueteClases.objects.get().videos, 0)

    def test_no_cobra_videos_extra(self, tx):
        paquete = dar_paquete(self.ana, self.profe)
        respuesta = self.post(tx, 'comprar_videos_extra', {'paquete': paquete.pk, 'cantidad': '1'})
        tx.return_value.create.assert_not_called()
        self.assertFalse(CompraVideosExtra.objects.exists())
        self.assertAviso(respuesta)

    def test_no_ofrece_videos_extra(self, tx):
        dar_paquete(self.ana, self.profe)
        self.assertEqual(videos_extra.ofertas(self.ana.pk), [])

    def test_planes_no_pregunta_por_el_agregado(self, tx):
        respuesta = self.client.get(reverse('planes'), {'profesor': self.profe.id_profesor})
        self.assertContains(respuesta, 'Comprar Progreso')  # el paquete si se ofrece
        self.assertNotContains(respuesta, 'id="pl-videos"')


class ConVideosALaVentaTests(Escenario):
    """El contraste: con MongoDB configurado (en pruebas, el runner) todo sigue como antes."""

    def test_planes_pregunta_por_el_agregado(self):
        self.entrar(RUT_ANA)
        self.assertContains(self.client.get(reverse('planes'), {'profesor': self.profe.id_profesor}), 'id="pl-videos"')

    def test_ofrece_videos_extra(self):
        dar_paquete(self.ana, self.profe)
        self.assertEqual(len(videos_extra.ofertas(self.ana.pk)), 1)
