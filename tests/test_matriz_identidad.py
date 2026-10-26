"""S4-11: matriz de pruebas de identidad y permisos (alumno, profesor y administrador).

Cada prueba es una fila de docs/MATRIZ_IDENTIDAD.md. Lo que ya cubren otros archivos
(portales por rol, decorador con usuario desactivado, anonimo, 5 intentos por usuario)
no se repite aqui: la matriz los referencia.

Las pruebas con @hallazgo_abierto describen el comportamiento SEGURO y hoy fallan:
son los hallazgos S-03, S-05, S-06 y S-07 del informe de seguridad, que siguen abiertos.
Cuando se corrija uno, unittest avisara "unexpected success": ahi se quita el decorador.

Para ver el fallo real de cada hallazgo (evidencia):
    VER_HALLAZGOS=1 python manage.py test tests.test_matriz_identidad
"""

import os
import unittest
from datetime import date

from allauth.account.adapter import get_adapter as adaptador_de_cuentas
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from admin_portal.forms import AdminAlumnoForm
from alumnos.models import Alumno, Genero, Tutor
from tests.test_google_y_titulo import BaseGoogle, google_login

User = get_user_model()
CLAVE = 'clave12345'
BLOQUEO = 'Demasiados intentos fallidos'

hallazgo_abierto = (lambda prueba: prueba) if os.environ.get('VER_HALLAZGOS') else unittest.expectedFailure


def crear_usuario(rut, genero, **extra):
    datos = dict(password=CLAVE, rut=rut, first_name='Prueba', email=f'{rut}@demo.cl',
                 direccion='C', fecha_nacimiento=date(2000, 1, 1), genero=genero)
    datos.update(extra)
    return User.objects.create_user(rut, **datos)


class BaseIdentidad(TestCase):
    """Alumna activa con RUT 12345678-5 y caché de intentos limpia."""

    def setUp(self):
        cache.clear()
        self.genero = Genero.objects.create(descripcion='Otro')
        self.user = crear_usuario('12345678-5', self.genero, rol='alumno', email='ana@demo.cl')
        Alumno.objects.create(user=self.user, nivel_educacion='media')

    def entrar(self, username, password=CLAVE, **cabeceras):
        return self.client.post(reverse('login'), {'username': username, 'password': password}, **cabeceras)


class LoginTests(BaseIdentidad):

    def test_entra_con_rut_rut_con_puntos_o_correo(self):
        for identificador in ('12345678-5', '12.345.678-5', 'ANA@demo.cl'):
            with self.subTest(identificador=identificador):
                respuesta = self.entrar(identificador)
                self.assertRedirects(respuesta, reverse('alumno_pag1'), fetch_redirect_response=False)
                self.client.logout()

    def test_usuario_desactivado_no_inicia_sesion(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        respuesta = self.entrar('12345678-5')
        self.assertContains(respuesta, 'RUT/Correo o contraseña incorrectos')
        self.assertNotIn('alumno_id', self.client.session)


class S03ClaveInicialTests(TestCase):

    @hallazgo_abierto
    def test_alumno_creado_por_admin_no_entra_con_su_rut(self):
        form = AdminAlumnoForm(data={
            'nombre': 'Creada por admin', 'rut': '12345678-5', 'direccion': 'C',
            'fecha_nacimiento': '2000-01-01', 'correo_electronico': 'nueva@demo.cl',
            'nivel_educacion': 'media',
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.client.post(reverse('login'), {'username': '12345678-5', 'password': '12345678-5'})

        self.assertNotIn('alumno_id', self.client.session,
                         'S-03: el alumno creado por el admin entra con su RUT como contraseña')


class S05LimiteDeIntentosTests(BaseIdentidad):

    def test_el_contador_por_ip_bloquea_tras_15_fallos(self):
        for i in range(15):
            self.entrar(f'nadie{i}@demo.cl', 'mala', HTTP_X_FORWARDED_FOR='203.0.113.1')
        respuesta = self.entrar('otro@demo.cl', 'mala', HTTP_X_FORWARDED_FOR='203.0.113.1')
        self.assertContains(respuesta, BLOQUEO)

    @hallazgo_abierto
    def test_escribir_el_rut_de_otra_forma_no_reinicia_el_contador(self):
        for _ in range(5):
            self.entrar('12.345.678-5', 'mala')

        self.entrar('12345678-5')

        self.assertNotIn('alumno_id', self.client.session,
                         'S-05: tras 5 fallos con 12.345.678-5, entra escribiendo 12345678-5')

    @hallazgo_abierto
    def test_cambiar_x_forwarded_for_no_reinicia_el_contador_por_ip(self):
        for i in range(15):
            self.entrar(f'nadie{i}@demo.cl', 'mala', HTTP_X_FORWARDED_FOR='203.0.113.1')

        respuesta = self.entrar('otro@demo.cl', 'mala', HTTP_X_FORWARDED_FOR='203.0.113.2')

        self.assertContains(respuesta, BLOQUEO,
                            msg_prefix='S-05: cambiando X-Forwarded-For el cliente evita el bloqueo por IP')


class S06RegistroAbiertoTests(TestCase):

    @hallazgo_abierto
    def test_el_registro_propio_de_allauth_esta_cerrado(self):
        request = RequestFactory().get(reverse('account_signup'))
        self.assertFalse(adaptador_de_cuentas(request).is_open_for_signup(request),
                         'S-06: /accounts/signup/ acepta registros (no hay ACCOUNT_ADAPTER que lo cierre)')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GoogleConSesion(BaseGoogle):

    def setUp(self):
        self.client.get(reverse('login'))  # crea la sesion
        self.client.session.save()


class S06CuentaHuerfanaTests(GoogleConSesion):

    @hallazgo_abierto
    def test_completar_con_google_anula_la_clave_previa(self):
        # Cuenta sin perfil creada antes por otra persona con el correo de la victima.
        User.objects.create_user('atacante', email='nuevo@demo.cl', password='clave-del-atacante')
        # Import local: en el modulo, el runner volveria a correr las pruebas de esa clase.
        from tests.test_google_y_titulo import LoginGoogleTests
        LoginGoogleTests._registrarse(self, tipo='alumno', nivel_educacion='media')
        self.client.logout()

        self.client.post(reverse('login'), {'username': 'nuevo@demo.cl', 'password': 'clave-del-atacante'})

        self.assertNotIn('alumno_id', self.client.session,
                         'S-06: la clave previa de la cuenta huérfana sigue sirviendo tras completarla con Google')


class S07CuentasDesactivadasTests(BaseIdentidad):

    @hallazgo_abierto
    def test_admin_desactivado_con_sesion_no_entra_a_crear_administradores(self):
        admin = crear_usuario('33333333-3', self.genero)
        Tutor.objects.create(user=admin)
        self.entrar('33333333-3')
        User.objects.filter(pk=admin.pk).update(is_active=False)

        respuesta = self.client.get(reverse('regis_tutor'))

        self.assertRedirects(respuesta, reverse('login'), fetch_redirect_response=False,
                             msg_prefix='S-07: un admin desactivado con sesión abierta entra a crear administradores')


class S07GoogleTests(GoogleConSesion):

    @hallazgo_abierto
    def test_cuenta_desactivada_no_entra_con_google(self):
        user = crear_usuario('12345678-5', self.genero, rol='alumno', email='ana@demo.cl', is_active=False)
        Alumno.objects.create(user=user, nivel_educacion='media')

        self.volver_de_google(google_login('ana@demo.cl'))

        self.assertNotIn('alumno_id', self.client.session,
                         'S-07: una cuenta desactivada entra a su portal con Google')
