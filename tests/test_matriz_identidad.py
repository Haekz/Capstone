"""S4-11: matriz de pruebas de identidad y permisos (alumno, profesor y administrador).

Cada prueba es una fila de docs/MATRIZ_IDENTIDAD.md. Lo que ya cubren otros archivos
(portales por rol, decorador con usuario desactivado, anonimo, 5 intentos por usuario)
no se repite aqui: la matriz los referencia.

Los hallazgos S-03, S-05, S-06 y S-07 del informe de seguridad estan cerrados: cada
prueba describe el comportamiento SEGURO y pasa. Si aparece un hallazgo nuevo, su
prueba se marca con unittest.expectedFailure hasta corregirlo.
"""

from datetime import date

from allauth.account.adapter import get_adapter as adaptador_de_cuentas
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core import mail
from django.core.cache import cache
from django.core.management.sql import emit_post_migrate_signal
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from admin_portal.forms import AdminAlumnoForm
from alumnos.forms import AlumnoForm
from alumnos.google_adapter import entrar_al_portal
from alumnos.models import Alumno, Especialidad, Genero, Tutor
from apoderados.forms import RegistroApoderadoForm
from tests.test_google_y_titulo import BaseGoogle, google_login

User = get_user_model()
CLAVE = 'clave12345'
CLAVE_SEGURA = 'Pelicano-Verde-2026'
BLOQUEO = 'Demasiados intentos fallidos'


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

    def test_next_interno_vuelve_ahi_y_externo_va_al_portal(self):
        """6e: volver a la pagina que pidio el login (p. ej. reportar un pago). Solo rutas
        internas: un next a otro dominio seria una redireccion abierta."""
        casos = {'/soporte/mis-tickets/nuevo/?pago=LB1': '/soporte/mis-tickets/nuevo/?pago=LB1',
                 'https://malo.cl/x': reverse('alumno_pag1'), '//malo.cl/x': reverse('alumno_pag1')}
        for siguiente, destino in casos.items():
            with self.subTest(next=siguiente):
                respuesta = self.client.post(reverse('login'), {'username': '12345678-5', 'password': CLAVE,
                                                                'next': siguiente})
                self.assertRedirects(respuesta, destino, fetch_redirect_response=False)
                self.client.logout()

    def test_el_formulario_conserva_solo_un_next_interno(self):
        self.assertContains(self.client.get(reverse('login'), {'next': '/soporte/mis-tickets/'}),
                            'name="next" value="/soporte/mis-tickets/"')
        self.assertNotContains(self.client.get(reverse('login'), {'next': 'https://malo.cl'}), 'name="next"')


class S03ClaveInicialTests(TestCase):

    def test_alumno_creado_por_admin_no_entra_con_su_rut(self):
        datos = {
            'nombre': 'Creada por admin', 'rut': '12345678-5', 'direccion': 'C',
            'fecha_nacimiento': '2000-01-01', 'correo_electronico': 'nueva@demo.cl',
            'nivel_educacion': 'media',
        }
        # Sin clave, o con el RUT como clave, el admin no puede crear la cuenta (S4-02).
        for clave in ('', '12345678-5'):
            with self.subTest(clave=clave):
                form = AdminAlumnoForm(data={**datos, 'password': clave, 'confirm_password': clave})
                self.assertFalse(form.is_valid())
        form = AdminAlumnoForm(data={**datos, 'password': CLAVE_SEGURA, 'confirm_password': CLAVE_SEGURA})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.client.post(reverse('login'), {'username': '12345678-5', 'password': '12345678-5'})

        self.assertNotIn('alumno_id', self.client.session,
                         'S-03: el alumno creado por el admin entra con su RUT como contraseña')


class Seg3ClaveIgualAlRutTests(BaseIdentidad):
    """Seg-3: los registros de alumno, profesor, administrador y apoderado rechazan la clave igual
    al RUT (con o sin puntos) o al correo. Antes validaban sin usuario y pasaban."""

    RUT, CORREO = '11111111-1', 'nuevo@demo.cl'
    CLAVES = ('11111111-1', '11.111.111-1', 'nuevo@demo.cl')

    def datos(self, clave, **extra):
        return {'nombre': 'Nueva Persona', 'rut': self.RUT, 'direccion': 'Calle 1',
                'fecha_nacimiento': '1990-01-01', 'correo_electronico': self.CORREO,
                'telefono': '911111111', 'genero': self.genero.id_genero,
                'password': clave, 'confirm_password': clave, **extra}

    def comprobar_registro(self, url, **extra):
        for clave in self.CLAVES:
            with self.subTest(clave=clave):
                self.assertFalse(self.client.post(url, self.datos(clave, **extra)).json()['success'])
                self.assertFalse(User.objects.filter(username=self.RUT).exists())
        respuesta = self.client.post(url, self.datos(CLAVE_SEGURA, **extra))  # control: el resto es valido
        self.assertTrue(respuesta.json()['success'], respuesta.json())

    def test_registro_de_profesor(self):
        fisica = Especialidad.objects.create(nombre='Física')
        self.comprobar_registro(reverse('regis_prof'), especialidad=fisica.pk)

    def test_crear_administrador(self):
        Tutor.objects.create(user=crear_usuario('33333333-3', self.genero))
        self.entrar('33333333-3')
        self.comprobar_registro(reverse('regis_tutor'))

    def test_registro_de_alumno(self):
        for clave in self.CLAVES:
            with self.subTest(clave=clave):
                form = AlumnoForm(data=self.datos(clave, nivel_educacion='media'))
                self.assertIn('password', form.errors)
        self.assertTrue(AlumnoForm(data=self.datos(CLAVE_SEGURA, nivel_educacion='media')).is_valid())

    def test_registro_de_apoderado(self):
        """Ademas compara con el nombre: el apoderado lo hacia antes de usar el helper comun."""
        datos = {'nombre': 'Nueva Persona', 'rut': self.RUT, 'correo': self.CORREO}
        for clave in self.CLAVES + ('Nueva Persona',):
            with self.subTest(clave=clave):
                form = RegistroApoderadoForm(data={**datos, 'password': clave, 'confirmar_password': clave})
                self.assertIn('password', form.errors)
        form = RegistroApoderadoForm(data={**datos, 'password': CLAVE_SEGURA, 'confirmar_password': CLAVE_SEGURA})
        self.assertNotIn('password', form.errors)  # control (faltan el carnet y otros campos: no importan aqui)


class S05LimiteDeIntentosTests(BaseIdentidad):

    def test_el_contador_por_ip_bloquea_tras_15_fallos(self):
        for i in range(15):
            self.entrar(f'nadie{i}@demo.cl', 'mala', HTTP_X_FORWARDED_FOR='203.0.113.1')
        respuesta = self.entrar('otro@demo.cl', 'mala', HTTP_X_FORWARDED_FOR='203.0.113.1')
        self.assertContains(respuesta, BLOQUEO)

    def test_escribir_el_rut_de_otra_forma_no_reinicia_el_contador(self):
        for _ in range(5):
            self.entrar('12.345.678-5', 'mala')

        self.entrar('12345678-5')

        self.assertNotIn('alumno_id', self.client.session,
                         'S-05: tras 5 fallos con 12.345.678-5, entra escribiendo 12345678-5')

    def test_cambiar_x_forwarded_for_no_reinicia_el_contador_por_ip(self):
        for i in range(15):
            self.entrar(f'nadie{i}@demo.cl', 'mala', HTTP_X_FORWARDED_FOR='203.0.113.1')

        respuesta = self.entrar('otro@demo.cl', 'mala', HTTP_X_FORWARDED_FOR='203.0.113.2')

        self.assertContains(respuesta, BLOQUEO,
                            msg_prefix='S-05: cambiando X-Forwarded-For el cliente evita el bloqueo por IP')

    @override_settings(CONFIAR_X_FORWARDED_FOR=True)
    def test_detras_del_proxy_solo_cuenta_la_ip_que_agrega_el_proxy(self):
        # El proxy (Railway) agrega la IP real al final; lo anterior lo escribe el cliente.
        for i in range(15):
            self.entrar(f'nadie{i}@demo.cl', 'mala', HTTP_X_FORWARDED_FOR=f'10.0.0.{i}, 198.51.100.7')

        respuesta = self.entrar('otro@demo.cl', 'mala', HTTP_X_FORWARDED_FOR='10.9.9.9, 198.51.100.7')

        self.assertContains(respuesta, BLOQUEO,
                            msg_prefix='S-05: detras del proxy, falsear el inicio de X-Forwarded-For evita el bloqueo')

    def test_migrate_crea_la_tabla_de_la_cache_compartida(self):
        # Sin la tabla, el contador compartido entre procesos falla al primer login.
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE lbwus_cache_table')

        emit_post_migrate_signal(verbosity=0, interactive=False, db='default')

        self.assertIn('lbwus_cache_table', connection.introspection.table_names())


class S06RegistroAbiertoTests(TestCase):

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

    def test_admin_desactivado_con_sesion_no_entra_a_crear_administradores(self):
        admin = crear_usuario('33333333-3', self.genero)
        Tutor.objects.create(user=admin)
        self.entrar('33333333-3')
        User.objects.filter(pk=admin.pk).update(is_active=False)

        respuesta = self.client.get(reverse('regis_tutor'))

        self.assertRedirects(respuesta, reverse('login'), fetch_redirect_response=False,
                             msg_prefix='S-07: un admin desactivado con sesión abierta entra a crear administradores')


class S07GoogleTests(GoogleConSesion):

    def test_cuenta_desactivada_no_entra_con_google(self):
        user = crear_usuario('12345678-5', self.genero, rol='alumno', email='ana@demo.cl', is_active=False)
        Alumno.objects.create(user=user, nivel_educacion='media')

        self.volver_de_google(google_login('ana@demo.cl'))

        self.assertNotIn('alumno_id', self.client.session,
                         'S-07: una cuenta desactivada entra a su portal con Google')

    def test_cuenta_huerfana_desactivada_no_recibe_codigo(self):
        # Sin perfil, sin el rechazo temprano iria al flujo de completar registro.
        User.objects.create_user('huerfana', email='ana@demo.cl', password=CLAVE, is_active=False)

        self.volver_de_google(google_login('ana@demo.cl'))

        self.assertEqual(len(mail.outbox), 0, 'S-07: se envio un codigo a una cuenta desactivada')

    def test_desactivada_a_ultima_hora_no_abre_sesion(self):
        # entrar_al_portal es la ultima puerta: tambien la usa google_views al completar el registro.
        user = crear_usuario('12345678-5', self.genero, rol='alumno', email='ana@demo.cl', is_active=False)
        Alumno.objects.create(user=user, nivel_educacion='media')
        request = RequestFactory().get('/')
        request.session = SessionStore()
        request.user = AnonymousUser()
        request._messages = FallbackStorage(request)

        respuesta = entrar_al_portal(request, user)

        self.assertEqual(respuesta.url, reverse('login'))
        self.assertNotIn('_auth_user_id', request.session)
