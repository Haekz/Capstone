"""Cloudflare R2 para los archivos de video (user_profesor/almacen_videos.py), con boto3 de verdad y sin red.

Firmar un enlace no consulta a R2 (se calcula con la clave), asi que se prueba el enlace real: apunta al bucket,
vence en DURACION_ENLACE_SEG y no lleva la clave secreta. Ademas: sin las variables R2_* no hay cliente; la pagina
de error oculta las claves; y la CSP deja pasar el video desde R2 (si no, al hacerla obligatoria se bloquearia).
"""

import importlib
from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase, override_settings

from lbwus import cabeceras
from lbwus.reporte_errores import FiltroReporteErrores
from user_profesor import almacen_videos

R2 = dict(R2_ACCOUNT_ID='cuenta123', R2_ACCESS_KEY_ID='id-de-prueba', R2_SECRET_ACCESS_KEY='secreto-de-prueba',
          R2_BUCKET='lbwus-videos', R2_ENDPOINT='https://cuenta123.r2.cloudflarestorage.com', R2_CONFIGURADO=True)


class AlmacenVideosTests(SimpleTestCase):

    def setUp(self):
        almacen_videos.restablecer()
        self.addCleanup(almacen_videos.restablecer)

    @override_settings(**R2)
    def test_el_enlace_es_privado_del_bucket_y_vence(self):
        enlace = almacen_videos.enlace('64b7f0c2a1b2c3d4e5f60718')
        partes = urlsplit(enlace)
        consulta = parse_qs(partes.query)
        self.assertEqual((partes.scheme, partes.netloc), ('https', 'cuenta123.r2.cloudflarestorage.com'))
        self.assertEqual(partes.path, '/lbwus-videos/videos/64b7f0c2a1b2c3d4e5f60718.mp4')
        self.assertEqual(consulta['X-Amz-Expires'], ['7200'])  # 2 horas (decidido 23-nov): el numero, no la constante
        self.assertEqual(consulta['X-Amz-Algorithm'], ['AWS4-HMAC-SHA256'])
        self.assertNotIn('secreto-de-prueba', enlace)  # va la firma, nunca la clave

    @override_settings(R2_CONFIGURADO=False)
    def test_sin_las_variables_no_hay_cliente(self):
        with self.assertRaises(almacen_videos.AlmacenNoConfigurado):
            almacen_videos.enlace('64b7f0c2a1b2c3d4e5f60718')

    @override_settings(**R2)
    def test_la_pagina_de_error_oculta_las_claves(self):
        ajustes = FiltroReporteErrores().get_safe_settings()
        for nombre in ('R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY'):
            with self.subTest(nombre=nombre):
                self.assertNotIn('prueba', str(ajustes[nombre]))

    def test_la_csp_deja_pasar_el_video_desde_r2(self):
        self.addCleanup(importlib.reload, cabeceras)  # vuelve a la CSP de los settings normales
        with override_settings(R2_ENDPOINT=R2['R2_ENDPOINT']):
            importlib.reload(cabeceras)
        self.assertIn(R2['R2_ENDPOINT'], cabeceras.CSP['media-src'])
        with override_settings(R2_ENDPOINT=''):
            importlib.reload(cabeceras)
        self.assertEqual(cabeceras.CSP['media-src'], ("'self'", 'https://commondatastorage.googleapis.com'))
