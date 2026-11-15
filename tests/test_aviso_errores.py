"""Aviso de errores 500 por correo y direccion de salud. Datos ficticios.

El correo no debe llevar datos de las personas: ni el mensaje del error (los de base de datos traen datos reales),
ni parametros, ni lo enviado, ni nombre o correo de quien navegaba, ni la direccion real (puede llevar un token).
"""
from unittest import mock

from django.core import mail
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import path, reverse

from lbwus import aviso_errores
from lbwus.urls import urlpatterns as urls_del_sitio
from tests.test_soporte_reportes import crear_alumno_adulto

DATO_PERSONAL = 'Rut 12.345.678-5 ya existe'
DESTINOS = ['equipo@lbwus.test', 'respaldo@lbwus.test']


def explota(request, numero):
    raise ValueError(DATO_PERSONAL)


def explota_distinto(request):
    raise KeyError(DATO_PERSONAL)


urlpatterns = urls_del_sitio + [path('explota/<int:numero>/', explota), path('otro-error/', explota_distinto)]


class SaludTests(TestCase):

    def test_responde_ok_sin_iniciar_sesion(self):
        respuesta = self.client.get(reverse('salud'))
        self.assertEqual((respuesta.status_code, respuesta.json()), (200, {'estado': 'ok'}))
        self.assertIn('no-store', respuesta['Cache-Control'])

    @override_settings(SITIO_CLAVE='clave-de-prueba')
    def test_responde_aunque_la_puerta_con_clave_este_activa(self):
        self.assertEqual(self.client.get(reverse('salud')).status_code, 200)
        self.assertEqual(self.client.get(reverse('login')).status_code, 302)  # el resto del sitio si pide la clave

    def test_sin_base_de_datos_dice_503_y_no_cuenta_por_que(self):
        with mock.patch('lbwus.salud.connection') as conexion, self.assertLogs('lbwus.salud', 'WARNING'):
            conexion.cursor.side_effect = OperationalError('password authentication failed for user "secreto"')
            respuesta = self.client.get(reverse('salud'))
        self.assertEqual((respuesta.status_code, respuesta.json()), (503, {'estado': 'sin base de datos'}))
        self.assertNotIn('secreto', respuesta.content.decode())

    def test_solo_se_puede_consultar(self):
        self.assertEqual(self.client.head(reverse('salud')).status_code, 200)
        self.assertEqual(self.client.post(reverse('salud')).status_code, 405)


@override_settings(ROOT_URLCONF=__name__, ERRORES_CORREOS=DESTINOS)
class AvisoDeErroresTests(TestCase):

    def setUp(self):
        aviso_errores._ultimo_aviso.clear()
        mail.outbox.clear()
        self.client.raise_request_exception = False  # que el 500 llegue como respuesta, como en el sitio

    def provocar(self, url='/explota/7/?rut=11.111.111-1', datos=None):
        return self.client.post(url, datos or {'clave': 'secreto-123'})

    def test_un_error_500_avisa_a_cada_correo(self):
        self.assertEqual(self.provocar().status_code, 500)
        self.assertEqual(sorted(correo.to[0] for correo in mail.outbox), sorted(DESTINOS))
        correo = mail.outbox[0]
        self.assertEqual(correo.subject, 'Error 500 en explota/<int:numero>/ - LBWUS')
        for dato in ('ValueError', 'POST explota/<int:numero>/', 'en explota', 'nadie con la sesión iniciada'):
            self.assertIn(dato, correo.body)

    def test_el_correo_no_lleva_datos_de_las_personas(self):
        alumno = crear_alumno_adulto().user
        self.client.force_login(alumno)
        self.provocar()
        cuerpo = mail.outbox[0].body
        self.assertIn(f'la cuenta con id {alumno.pk}', cuerpo)  # su id si, para encontrarla
        for dato in (DATO_PERSONAL, '12.345.678-5', '11.111.111-1', 'rut=', 'secreto-123', '/explota/7/',
                     alumno.first_name, alumno.last_name, alumno.email, alumno.rut):
            if not dato:  # un apellido vacio estaria «dentro» de cualquier texto
                continue
            with self.subTest(dato=dato):
                self.assertNotIn(dato, cuerpo)

    def test_el_mismo_error_en_la_misma_pantalla_avisa_una_vez(self):
        self.provocar('/explota/1/')
        self.provocar('/explota/2/')  # otra direccion, misma pantalla
        self.assertEqual(len(mail.outbox), len(DESTINOS))

    def test_otro_error_si_avisa_y_pasados_diez_minutos_vuelve_a_avisar(self):
        self.provocar('/explota/1/')
        self.client.post('/otro-error/')
        self.assertEqual(len(mail.outbox), 2 * len(DESTINOS))
        with mock.patch('lbwus.aviso_errores.time.monotonic', return_value=aviso_errores.time.monotonic() + 601):
            self.provocar('/explota/1/')
        self.assertEqual(len(mail.outbox), 3 * len(DESTINOS))

    @override_settings(ERRORES_CORREOS=[])
    def test_sin_correos_configurados_no_avisa(self):
        self.assertEqual(self.provocar().status_code, 500)
        self.assertEqual(mail.outbox, [])

    def test_lo_que_no_es_un_500_no_avisa(self):
        self.assertEqual(self.client.get('/no-existe-nunca/').status_code, 404)
        self.assertEqual(mail.outbox, [])

    def test_si_el_aviso_falla_el_sitio_responde_igual(self):
        with mock.patch('lbwus.aviso_errores.enviar', side_effect=RuntimeError), \
                mock.patch('logging.raiseExceptions', False):  # sin el ruido de «Logging error» en la consola
            self.assertEqual(self.provocar().status_code, 500)
