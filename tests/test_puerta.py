"""Puerta con clave para todo el sitio (lbwus/puerta.py) y filtro de errores.

Con SITIO_CLAVE vacia el sitio funciona igual que antes. Con SITIO_CLAVE,
todo pide la clave en /puerta/, salvo /puerta/, /static/ y el retorno de
Webpay (confirmacion), que llega desde el dominio de Transbank.
"""

import sys
from unittest.mock import patch

from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.views.debug import get_default_exception_reporter_filter, technical_500_response

from lbwus.puerta import SESION_PUERTA, destino_seguro
from lbwus.reporte_errores import FiltroReporteErrores

# Valor ficticio, solo para las pruebas. La clave real vive en Railway.
CLAVE_PRUEBA = 'clave-ficticia-de-prueba'
URI_PRUEBA = 'mongodb+srv://usuario:secreto@cluster.ficticio/'


def es_redireccion_a_puerta(r):
    return r.status_code == 302 and r['Location'].startswith(reverse('puerta'))


@override_settings(SITIO_CLAVE='')
class SinClaveTests(TestCase):

    def test_el_sitio_funciona_igual(self):
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(SESION_PUERTA, self.client.session)

    def test_puerta_sin_clave_redirige_al_destino(self):
        r = self.client.get(reverse('puerta'), {'next': '/accounts/login/'})
        self.assertRedirects(r, '/accounts/login/', fetch_redirect_response=False)


@override_settings(SITIO_CLAVE=CLAVE_PRUEBA)
class ConClaveTests(TestCase):

    def _entrar(self, clave, next_='/'):
        return self.client.post(reverse('puerta'), {'clave': clave, 'next': next_})

    def test_inicio_redirige_a_la_puerta_con_next(self):
        r = self.client.get('/')
        self.assertRedirects(r, '/puerta/?next=%2F', fetch_redirect_response=False)

    def test_next_conserva_ruta_y_query(self):
        r = self.client.get('/accounts/login/?a=1&b=2')
        self.assertRedirects(r, '/puerta/?next=%2Faccounts%2Flogin%2F%3Fa%3D1%26b%3D2',
                             fetch_redirect_response=False)

    def test_puerta_muestra_el_formulario(self):
        r = self.client.get(reverse('puerta'), {'next': '/'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'name="csrfmiddlewaretoken"')
        self.assertContains(r, 'type="password"')
        self.assertContains(r, 'alumnos/img/Logo')
        # Pantalla de mantenimiento: es lo que ve cualquier visitante.
        self.assertContains(r, '<title>En mantenimiento — LBWUS</title>', html=True)
        self.assertContains(r, '<h1 class="puerta-title">Sitio en mantenimiento</h1>', html=True)
        self.assertContains(r, 'Estamos realizando mejoras. Si eres parte del equipo, '
                               'ingresa la clave de acceso para continuar.')
        self.assertContains(r, '<i class="bi bi-tools" aria-hidden="true"></i>', html=True)

    def test_clave_incorrecta_no_deja_pasar(self):
        for clave in ['otra', CLAVE_PRUEBA + ' ', CLAVE_PRUEBA.upper(), '']:
            with self.subTest(clave=clave):
                r = self._entrar(clave)
                self.assertEqual(r.status_code, 200)
                if clave:
                    self.assertContains(r, 'Clave incorrecta')
                self.assertNotIn(SESION_PUERTA, self.client.session)
                self.assertTrue(es_redireccion_a_puerta(self.client.get('/')))

    def test_clave_correcta_deja_pasar_y_vuelve_a_next(self):
        r = self._entrar(CLAVE_PRUEBA, '/accounts/login/?a=1')
        self.assertRedirects(r, '/accounts/login/?a=1', fetch_redirect_response=False)
        self.assertIs(self.client.session[SESION_PUERTA], True)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get(reverse('login')).status_code, 200)

    def test_next_externo_se_ignora(self):
        for externo in ['https://evil.cl/', '//evil.cl/', 'http:evil.cl',
                        'javascript:alert(1)', '\\\\evil.cl', 'login']:
            with self.subTest(next=externo):
                self.client = Client()
                r = self._entrar(CLAVE_PRUEBA, externo)
                self.assertRedirects(r, '/', fetch_redirect_response=False)

    def test_destino_seguro(self):
        self.assertEqual(destino_seguro('/profesor/panel?x=1'), '/profesor/panel?x=1')
        for malo in [None, '', 'https://evil.cl', '//evil.cl', '/\\evil.cl', 'evil']:
            with self.subTest(destino=malo):
                self.assertEqual(destino_seguro(malo), '/')

    def test_puerta_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        r = cliente.post(reverse('puerta'), {'clave': CLAVE_PRUEBA, 'next': '/'})
        self.assertEqual(r.status_code, 403)
        self.assertNotIn(SESION_PUERTA, cliente.session)

    def test_confirmacion_de_webpay_no_queda_bloqueada(self):
        url = reverse('confirmacion')
        self.assertFalse(es_redireccion_a_puerta(self.client.get(url)))
        tx = patch('alumnos.views._tx').start()
        self.addCleanup(patch.stopall)
        tx.return_value.commit.return_value = {'response_code': -1, 'status': 'FAILED'}
        r = self.client.post(url, {'token_ws': 'token-ficticio'})
        self.assertFalse(es_redireccion_a_puerta(r))
        tx.return_value.commit.assert_called_once_with('token-ficticio')

    def test_static_no_queda_bloqueado(self):
        r = self.client.get('/static/puerta.css')
        self.assertFalse(es_redireccion_a_puerta(r))

    def test_cerrar_sesion_no_vuelve_a_pedir_la_clave(self):
        self._entrar(CLAVE_PRUEBA)
        self.client.get(reverse('logout_alumno'))
        self.assertIs(self.client.session.get(SESION_PUERTA), True)
        self.assertEqual(self.client.get('/').status_code, 200)


class FiltroReporteErroresTests(SimpleTestCase):

    @override_settings(MONGODB_URI=URI_PRUEBA, SITIO_CLAVE=CLAVE_PRUEBA)
    def test_oculta_mongodb_uri_y_sitio_clave(self):
        filtro = get_default_exception_reporter_filter()
        self.assertIsInstance(filtro, FiltroReporteErrores)
        seguros = filtro.get_safe_settings()
        self.assertEqual(seguros['MONGODB_URI'], filtro.cleansed_substitute)
        self.assertEqual(seguros['SITIO_CLAVE'], filtro.cleansed_substitute)
        # Lo que Django ya ocultaba sigue oculto.
        self.assertEqual(seguros['SECRET_KEY'], filtro.cleansed_substitute)
        # Lo demas se sigue mostrando.
        self.assertNotEqual(seguros['MONGODB_DB'], filtro.cleansed_substitute)

    def test_la_clave_enviada_a_la_puerta_no_sale_en_el_reporte(self):
        # Tambien con DEBUG=True: el filtro original solo oculta el POST con
        # DEBUG=False, y Railway todavia corre con DEBUG=True.
        from lbwus.puerta import puerta
        for debug in (False, True):
            with self.subTest(DEBUG=debug), override_settings(DEBUG=debug, SITIO_CLAVE='otra'):
                request = RequestFactory().post('/puerta/', {'clave': CLAVE_PRUEBA, 'next': '/'})
                request.session = {}
                puerta(request)
                post = get_default_exception_reporter_filter().get_post_parameters(request)
                self.assertEqual(post['clave'], FiltroReporteErrores.cleansed_substitute)
                self.assertEqual(post['next'], '/')

    @override_settings(DEBUG=True, SITIO_CLAVE=CLAVE_PRUEBA, MONGODB_URI=URI_PRUEBA)
    def test_la_pagina_de_error_no_muestra_las_claves(self):
        # Los valores van en constantes del modulo: el traceback muestra el
        # codigo fuente de esta funcion y un literal aqui daria falso positivo.
        request = RequestFactory().post('/puerta/', {'clave': CLAVE_PRUEBA})
        request.sensitive_post_parameters = ['clave']
        try:
            raise RuntimeError('error de prueba')
        except RuntimeError:
            html = technical_500_response(request, *sys.exc_info()).content.decode()
        self.assertIn('error de prueba', html)
        self.assertIn('MONGODB_URI', html)
        self.assertNotIn(CLAVE_PRUEBA, html)
        self.assertNotIn(URI_PRUEBA, html)


@override_settings(SITIO_CLAVE='', SITIO_DOMINIOS_CORREO=['duocuc.cl'],
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PuertaPorCorreoTests(TestCase):

    def _pedir(self, correo):
        return self.client.post(reverse('puerta'), {'accion': 'correo', 'correo': correo, 'next': '/'})

    def _codigo(self):
        from django.core import mail
        return mail.outbox[-1].body.split('es: ')[1][:6]

    def test_sin_sesion_redirige_a_la_puerta(self):
        self.assertTrue(es_redireccion_a_puerta(self.client.get('/')))

    def test_correo_de_otro_dominio_no_recibe_codigo(self):
        from django.core import mail
        r = self._pedir('alguien@gmail.com')
        self.assertContains(r, 'Solo pueden entrar')
        self.assertEqual(len(mail.outbox), 0)

    def test_dominio_parecido_no_pasa(self):
        from django.core import mail
        self._pedir('x@duocuc.cl.evil.com')
        self._pedir('x@evil.com@duocuc.cl')
        self.assertEqual(len(mail.outbox), 0)

    def test_flujo_completo(self):
        r = self._pedir('Ana@DuocUC.cl')
        self.assertContains(r, 'ana@duocuc.cl')
        r = self.client.post(reverse('puerta'), {'accion': 'codigo', 'codigo': self._codigo(), 'next': '/'})
        self.assertRedirects(r, '/', fetch_redirect_response=False)
        self.assertTrue(self.client.session[SESION_PUERTA])
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_codigo_incorrecto(self):
        self._pedir('ana@duocuc.cl')
        r = self.client.post(reverse('puerta'), {'accion': 'codigo', 'codigo': '000000', 'next': '/'})
        self.assertContains(r, 'no es correcto')
        self.assertNotIn(SESION_PUERTA, self.client.session)

    def test_bloqueo_tras_cinco_intentos(self):
        self._pedir('ana@duocuc.cl')
        codigo = self._codigo()
        for _ in range(5):
            self.client.post(reverse('puerta'), {'accion': 'codigo', 'codigo': '000000'})
        r = self.client.post(reverse('puerta'), {'accion': 'codigo', 'codigo': codigo})
        self.assertContains(r, 'Demasiados intentos')
        self.assertNotIn(SESION_PUERTA, self.client.session)
