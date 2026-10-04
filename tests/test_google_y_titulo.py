"""Login/registro con Google y titulo profesional del profesor.

Google se simula armando el SocialLogin que entregaria allauth tras el
callback y llamando a complete_login, que es lo que corre en produccion.
"""

import re
import time
from datetime import date, time as hora

from allauth.account.models import EmailAddress
from allauth.core.context import request_context
from allauth.socialaccount.internal.flows.login import complete_login
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sites.models import Site
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from alumnos import codigo_google
from alumnos.models import Alumno, Clase, Genero, Profesor, Tutor

User = get_user_model()
PDF = b'%PDF-1.4 titulo de prueba'


def google_login(correo, uid='g-1', verificado=True, nombre='Gabi Google'):
    from allauth.socialaccount.adapter import get_adapter
    provider = get_adapter().get_provider(None, 'google')
    cuenta = SocialAccount(provider='google', uid=uid,
                           extra_data={'email': correo, 'name': nombre})
    sl = SocialLogin(account=cuenta, user=User(email=correo), provider=provider,
                     email_addresses=[EmailAddress(email=correo, verified=verificado, primary=True)])
    sl.state = {'process': 'login'}
    return sl


class BaseGoogle(TestCase):

    @classmethod
    def setUpTestData(cls):
        app = SocialApp.objects.create(provider='google', name='Google', client_id='x', secret='y')
        app.sites.add(Site.objects.get_current())
        cls.genero = Genero.objects.create(descripcion='Otro')

    def volver_de_google(self, sociallogin):
        """Ejecuta el callback de allauth con la sesion del cliente de prueba."""
        request = RequestFactory().get('/accounts/google/login/callback/')
        request.session = SessionStore(self.client.session.session_key)
        request.user = AnonymousUser()
        request._messages = FallbackStorage(request)
        with request_context(request):
            respuesta = complete_login(request, sociallogin)
        request.session.save()
        self.client.cookies['sessionid'] = request.session.session_key
        return respuesta

    def codigo_enviado(self):
        return re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LoginGoogleTests(BaseGoogle):

    def setUp(self):
        self.client.get(reverse('login'))  # crea la sesion
        self.client.session.save()

    def test_cuenta_registrada_entra_directo_a_su_portal(self):
        u = User.objects.create_user('11111111-1', email='ana@demo.cl', password='x')
        alumno = Alumno.objects.create(user=u, nombre='Ana', rut='11111111-1', nivel_educacion='media',
                                       direccion='C', fecha_nacimiento=date(2000, 1, 1),
                                       correo_electronico='ana@demo.cl', genero=self.genero)

        respuesta = self.volver_de_google(google_login('ANA@demo.cl'))

        self.assertEqual(respuesta.url, reverse('alumno_pag1'))
        self.assertEqual(self.client.session['alumno_id'], alumno.id_alumno)
        self.assertTrue(SocialAccount.objects.filter(user=u, provider='google').exists())
        self.assertTrue(u.has_usable_password(), 'no se debe borrar la clave de la cuenta')
        self.assertEqual(len(mail.outbox), 0)

    def test_correo_nuevo_no_crea_cuenta_y_manda_codigo(self):
        respuesta = self.volver_de_google(google_login('nuevo@demo.cl'))

        self.assertEqual(respuesta.url, reverse('google_verificar'))
        self.assertFalse(User.objects.filter(email='nuevo@demo.cl').exists())
        self.assertEqual(mail.outbox[0].to, ['nuevo@demo.cl'])

    def test_correo_no_verificado_por_google_se_rechaza(self):
        respuesta = self.volver_de_google(google_login('x@demo.cl', verificado=False))
        self.assertEqual(respuesta.url, reverse('login'))
        self.assertEqual(len(mail.outbox), 0)

    def test_completar_sin_codigo_vuelve_a_verificar(self):
        self.volver_de_google(google_login('nuevo@demo.cl'))
        respuesta = self.client.get(reverse('google_completar'))
        self.assertRedirects(respuesta, reverse('google_verificar'))

    def test_codigo_incorrecto_y_limite_de_intentos(self):
        self.volver_de_google(google_login('nuevo@demo.cl'))
        for _ in range(5):
            r = self.client.post(reverse('google_verificar'), {'codigo': '000000'})
        self.assertContains(r, 'código')
        # Ni el codigo correcto sirve despues de agotar los intentos.
        r = self.client.post(reverse('google_verificar'), {'codigo': self.codigo_enviado()})
        self.assertContains(r, 'Demasiados intentos')

    def test_codigo_vencido(self):
        self.volver_de_google(google_login('nuevo@demo.cl'))
        sesion = self.client.session
        sesion[codigo_google.CLAVE]['vence'] = time.time() - 1
        sesion.save()
        r = self.client.post(reverse('google_verificar'), {'codigo': self.codigo_enviado()})
        self.assertContains(r, 'venció')

    def _registrarse(self, **extra):
        self.volver_de_google(google_login('nuevo@demo.cl'))
        self.client.post(reverse('google_verificar'), {'codigo': self.codigo_enviado()})
        datos = dict(nombre='Gabi Google', rut='12345678-5', telefono='912345678',
                     direccion='Santiago', fecha_nacimiento='1995-05-05', genero=self.genero.pk)
        datos.update(extra)
        return self.client.post(reverse('google_completar'), datos)

    def test_registro_completo_como_alumno(self):
        r = self._registrarse(tipo='alumno', nivel_educacion='superior')

        self.assertRedirects(r, reverse('alumno_pag1'), fetch_redirect_response=False)
        user = User.objects.get(email='nuevo@demo.cl')
        self.assertEqual(user.perfil_alumno.rut, '12345678-5')
        self.assertFalse(user.has_usable_password())
        self.assertTrue(SocialAccount.objects.filter(user=user, uid='g-1').exists())
        self.assertNotIn(codigo_google.CLAVE, self.client.session)

    def test_registro_como_profesor_queda_pendiente_de_titulo(self):
        r = self._registrarse(tipo='profesor', especialidad='Química')

        self.assertRedirects(r, reverse('panel_profesor'), fetch_redirect_response=False)
        profesor = User.objects.get(email='nuevo@demo.cl').perfil_profesor
        self.assertEqual(profesor.titulo_estado, Profesor.TITULO_PENDIENTE)

    def test_datos_incompletos_no_crean_cuenta(self):
        r = self._registrarse(tipo='alumno')  # falta nivel_educacion
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email='nuevo@demo.cl').exists())

    def test_rut_ya_usado_no_crea_cuenta(self):
        User.objects.create_user('12345678-5', rut='12345678-5', password='x')
        r = self._registrarse(tipo='alumno', nivel_educacion='media')
        self.assertContains(r, 'RUT ingresado ya está registrado')
        self.assertFalse(User.objects.filter(email='nuevo@demo.cl').exists())

    def test_cuenta_huerfana_previa_se_completa_sin_duplicar(self):
        """Quien entro con Google antes del arreglo quedo sin perfil."""
        huerfano = User.objects.create_user('gabi', email='nuevo@demo.cl')
        SocialAccount.objects.create(user=huerfano, provider='google', uid='g-1')

        self._registrarse(tipo='alumno', nivel_educacion='media')

        self.assertEqual(User.objects.filter(email='nuevo@demo.cl').count(), 1)
        huerfano.refresh_from_db()
        self.assertEqual(huerfano.username, '12345678-5')
        self.assertTrue(hasattr(huerfano, 'perfil_alumno'))

    def test_pantallas_sin_registro_en_curso_vuelven_al_login(self):
        for nombre in ('google_verificar', 'google_completar'):
            self.assertRedirects(self.client.get(reverse(nombre)), reverse('login'))


class TituloProfesorTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        g = Genero.objects.create(descripcion='Otro')
        u = User.objects.create_user('22222222-2', password='clave12345')
        cls.profesor = Profesor.objects.create(
            user=u, nombre='Pedro', rut='22222222-2', especialidad='Mate', direccion='C',
            fecha_nacimiento=date(1990, 1, 1), correo_electronico='p@demo.cl', telefono='9', genero=g)
        ua = User.objects.create_user('33333333-3', password='clave12345')
        cls.tutor = Tutor.objects.create(user=ua, nombre='Tania', rut='33333333-3', direccion='C',
                                         fecha_nacimiento=date(1985, 1, 1), correo_electronico='t@demo.cl', genero=g)
        ual = User.objects.create_user('11111111-1', password='clave12345')
        cls.alumno = Alumno.objects.create(user=ual, nombre='Ana', rut='11111111-1', nivel_educacion='media',
                                           direccion='C', fecha_nacimiento=date(2000, 1, 1),
                                           correo_electronico='a@demo.cl', genero=g)

    def setUp(self):
        import tempfile
        self.media = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        self.media.enable()
        self.addCleanup(self.media.disable)

    def entrar(self, rut):
        self.client.post(reverse('login'), {'username': rut, 'password': 'clave12345'})

    def subir(self, contenido=PDF, nombre='titulo.pdf'):
        return self.client.post(reverse('subir_titulo'),
                                {'titulo': SimpleUploadedFile(nombre, contenido)}).json()

    def test_profesor_nuevo_ve_el_aviso_y_no_aparece_para_alumnos(self):
        self.entrar('22222222-2')
        self.assertContains(self.client.get(reverse('panel_profesor')), 'Sube tu título profesional')

        self.client.logout()
        self.entrar('11111111-1')
        respuesta = self.client.get(reverse('alumno_pag1'))
        self.assertNotIn(self.profesor, respuesta.context['profesores_list'])

    def test_subir_titulo_valido_lo_deja_en_revision(self):
        self.entrar('22222222-2')
        self.assertTrue(self.subir()['success'])
        self.profesor.refresh_from_db()
        self.assertEqual(self.profesor.titulo_estado, Profesor.TITULO_EN_REVISION)
        self.assertTrue(self.profesor.titulo_archivo.name.startswith('titulos/'))

    def test_rechaza_formato_o_contenido_falso(self):
        self.entrar('22222222-2')
        self.assertFalse(self.subir(nombre='virus.exe')['success'])
        self.assertFalse(self.subir(contenido=b'no soy pdf', nombre='falso.pdf')['success'])

    @override_settings(TITULO_MAX_MB=0)
    def test_rechaza_archivo_muy_grande(self):
        self.entrar('22222222-2')
        self.assertIn('MB', self.subir()['message'])

    def test_no_se_asigna_clase_ni_inscribe_sin_titulo_aprobado(self):
        self.entrar('33333333-3')
        r = self.client.post(reverse('crear_clase'), {
            'nombre_curso': 'Algebra', 'modalidad': 'online', 'horario': '10:00',
            'id_profesor': self.profesor.id_profesor}).json()
        self.assertFalse(r['success'])

        clase = Clase.objects.create(nombre_curso='X', modalidad='online', horario=hora(9),
                                     id_profesor=self.profesor)
        self.client.logout()
        self.entrar('11111111-1')
        r = self.client.post(reverse('inscribir_clase'), {'id_clase': clase.id_clase}).json()
        self.assertFalse(r['success'])

    def test_admin_aprueba_y_el_profesor_queda_habilitado(self):
        self.entrar('22222222-2')
        self.subir()
        self.client.logout()

        self.entrar('33333333-3')
        self.assertEqual(self.client.get(reverse('ver_titulo', args=[self.profesor.id_profesor])).status_code, 200)
        self.client.post(reverse('resolver_titulo', args=[self.profesor.id_profesor]), {'decision': 'aprobar'})

        self.profesor.refresh_from_db()
        self.assertTrue(self.profesor.puede_hacer_clases)

    def test_rechazo_exige_motivo_y_permite_resubir(self):
        self.entrar('22222222-2')
        self.subir()
        self.client.logout()
        self.entrar('33333333-3')
        url = reverse('resolver_titulo', args=[self.profesor.id_profesor])
        self.client.post(url, {'decision': 'rechazar'})
        self.profesor.refresh_from_db()
        self.assertEqual(self.profesor.titulo_estado, Profesor.TITULO_EN_REVISION)

        self.client.post(url, {'decision': 'rechazar', 'observacion': 'Ilegible'})
        self.profesor.refresh_from_db()
        self.assertEqual(self.profesor.titulo_estado, Profesor.TITULO_RECHAZADO)

        self.client.logout()
        self.entrar('22222222-2')
        self.assertContains(self.client.get(reverse('panel_profesor')), 'Ilegible')
        self.assertTrue(self.subir()['success'])

    def test_archivo_del_titulo_solo_lo_ven_admins(self):
        self.entrar('22222222-2')
        self.subir()
        url = reverse('ver_titulo', args=[self.profesor.id_profesor])
        self.assertNotEqual(self.client.get(url).status_code, 200)  # el propio profesor
        self.client.logout()
        self.assertNotEqual(self.client.get(url).status_code, 200)  # anonimo
