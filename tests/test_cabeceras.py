"""SCRUM-93: Content-Security-Policy (Report-Only) y Permissions-Policy (lbwus/cabeceras.py)."""

import re
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from alumnos.models import Genero
from lbwus.cabeceras import CSP, TRANSBANK
from tests.test_especialidad import CLAVE
from tests.test_progreso_alumno import crear_alumno

REPORT_ONLY, OBLIGATORIA = 'Content-Security-Policy-Report-Only', 'Content-Security-Policy'
RUT_ANA = '11111111-1'


def directivas(cabecera):
    return {d.split()[0]: d.split()[1:] for d in (p.strip() for p in cabecera.split(';')) if d}


class CabecerasTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        crear_alumno(RUT_ANA, 'Ana', Genero.objects.create(descripcion='Otro'))

    def portal(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        respuesta = self.client.get(reverse('alumno_pag1'))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def paginas(self):
        return {'publica': self.client.get(reverse('home')), 'portal del alumno': self.portal()}

    def test_las_dos_cabeceras_en_pagina_publica_y_portal(self):
        for nombre, respuesta in self.paginas().items():
            with self.subTest(nombre):
                self.assertIn(REPORT_ONLY, respuesta.headers)
                self.assertNotIn(OBLIGATORIA, respuesta.headers)  # por ahora no bloquea nada
                self.assertIn('Permissions-Policy', respuesta.headers)

    def test_csp_permite_jitsi_y_transbank(self):
        csp = directivas(self.client.get(reverse('home')).headers[REPORT_ONLY])
        for directiva in ('script-src', 'frame-src', 'connect-src'):
            with self.subTest(directiva):
                self.assertIn('https://meet.jit.si', csp[directiva])
        self.assertIn('wss://meet.jit.si', csp['connect-src'])
        for dominio in ('https://webpay3gint.transbank.cl', 'https://webpay3g.transbank.cl'):
            self.assertIn(dominio, csp['form-action'])
        self.assertIn('https://accounts.google.com', csp['form-action'])

    def test_csp_restricciones_fijas(self):
        csp = directivas(self.client.get(reverse('home')).headers[REPORT_ONLY])
        self.assertEqual(csp['frame-ancestors'], ["'none'"])
        self.assertEqual(csp['object-src'], ["'none'"])
        self.assertEqual(csp['base-uri'], ["'self'"])
        self.assertIn('data:', csp['img-src'])
        # Mientras frame-ancestors no se aplica (Report-Only), protege X-Frame-Options.
        self.assertEqual(self.client.get(reverse('home')).headers['X-Frame-Options'], 'DENY')

    def test_permissions_policy(self):
        politica = self.portal().headers['Permissions-Policy']
        permisos = dict(p.strip().split('=', 1) for p in politica.split(','))
        for permiso in ('camera', 'microphone', 'display-capture'):
            with self.subTest(permiso):
                self.assertEqual(permisos[permiso], '(self "https://meet.jit.si")')
        for permiso in ('geolocation', 'payment', 'usb'):
            with self.subTest(permiso):
                self.assertEqual(permisos[permiso], '()')

    @override_settings(CSP_OBLIGATORIA=True)
    def test_csp_obligatoria_con_la_variable(self):
        respuesta = self.client.get(reverse('home'))
        self.assertIn(OBLIGATORIA, respuesta.headers)
        self.assertNotIn(REPORT_ONLY, respuesta.headers)

    def test_tambien_en_redirecciones(self):
        respuesta = self.client.get(reverse('alumno_pag1'))  # anonimo: redirige al login
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(REPORT_ONLY, respuesta.headers)


class InventarioOrigenesTests(TestCase):
    """Si una plantilla carga un script, estilo o iframe de otro dominio, la CSP debe permitirlo."""

    ETIQUETAS = {
        'script-src': re.compile(r'<script[^>]+src="(https://[^"]+)"', re.I),
        'style-src': re.compile(r'<link[^>]+rel="stylesheet"[^>]+href="(https://[^"]+)"'
                                r'|<link[^>]+href="(https://[^"]+)"[^>]+rel="stylesheet"', re.I),
        'frame-src': re.compile(r'<iframe[^>]+src="(https://[^"]+)"', re.I | re.S),
    }

    def test_todo_origen_externo_de_las_plantillas_esta_en_la_csp(self):
        base = Path(settings.BASE_DIR)
        plantillas = [p for p in base.rglob('*.html')
                      if not {'.venv', 'staticfiles', 'usabilidad'} & set(p.parts)
                      and 'correo' not in p.name]  # los correos no los abre el navegador del sitio
        faltan = []
        for plantilla in plantillas:
            texto = plantilla.read_text(encoding='utf-8', errors='ignore')
            for directiva, patron in self.ETIQUETAS.items():
                for grupos in patron.findall(texto):
                    url = next(g for g in (grupos if isinstance(grupos, tuple) else (grupos,)) if g)
                    partes = urlsplit(url)
                    if f'{partes.scheme}://{partes.netloc}' not in CSP[directiva]:
                        faltan.append(f'{plantilla.relative_to(base)}: {directiva} {url}')
        self.assertEqual(faltan, [])

    def test_transbank_cubre_integracion_y_produccion(self):
        self.assertEqual(set(TRANSBANK), {'https://webpay3gint.transbank.cl', 'https://webpay3g.transbank.cl'})
