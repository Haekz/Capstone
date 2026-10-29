from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from django.core.management import call_command
from django.contrib.messages.storage.fallback import FallbackStorage
from io import StringIO
from allauth.socialaccount.models import SocialAccount, SocialLogin
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse

from alumnos.models import Genero, Alumno, Tutor
from admin_portal.forms import AdminAlumnoForm
from alumnos.backends import normalizar_rut_canonico, obtener_identificador_rate_limit
from alumnos.google_adapter import LbwusSocialAdapter, LbwusAccountAdapter

User = get_user_model()


class SeguridadAccesoS402Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.factory = RequestFactory()
        self.genero = Genero.objects.create(descripcion='Femenino')

        # Usuario alumno activo
        self.alumno_user = User.objects.create_user(
            username='11111111-1',
            rut='11111111-1',
            email='alumno@test.com',
            password='ClaveSegura_2026!#',
            rol='alumno',
            is_active=True
        )
        self.alumno = Alumno.objects.create(
            user=self.alumno_user,
            nivel_educacion='superior'
        )

        # Usuario alumno inactivo
        self.inactivo_user = User.objects.create_user(
            username='22222222-2',
            rut='22222222-2',
            email='inactivo@test.com',
            password='ClaveSegura_2026!#',
            rol='alumno',
            is_active=False
        )
        self.alumno_inactivo = Alumno.objects.create(
            user=self.inactivo_user,
            nivel_educacion='media'
        )

        # Usuario tutor/admin de negocio (sin is_staff)
        self.tutor_user = User.objects.create_user(
            username='33333333-3',
            rut='33333333-3',
            email='tutor@test.com',
            password='ClaveSegura_2026!#',
            rol='admin',
            is_active=True,
            is_staff=False
        )
        self.tutor = Tutor.objects.create(user=self.tutor_user)

        # Usuario administrador técnico staff
        self.staff_user = User.objects.create_user(
            username='44444444-4',
            rut='44444444-4',
            email='staff@test.com',
            password='ClaveSegura_2026!#',
            rol='admin',
            is_active=True,
            is_staff=True,
            is_superuser=True
        )

    def tearDown(self):
        cache.clear()

    # =========================================================================
    # SUBTAREA 1: Creación de alumnos con contraseña segura (S-03 / S-06)
    # =========================================================================

    def test_creacion_alumno_rechaza_password_igual_a_rut(self):
        data = {
            'nombre': 'Carlos Tapia',
            'rut': '12.345.678-5',
            'direccion': 'Alameda 100',
            'fecha_nacimiento': '2002-05-10',
            'correo_electronico': 'carlos@test.com',
            'telefono': '912345678',
            'genero': self.genero.id_genero,
            'nivel_educacion': 'superior',
            'password': '12.345.678-5',
            'confirm_password': '12.345.678-5',
        }
        form = AdminAlumnoForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)
        self.assertTrue(any('RUT' in err for err in form.errors['password']))

    def test_creacion_alumno_rechaza_password_igual_a_rut_sin_puntos(self):
        data = {
            'nombre': 'Carlos Tapia',
            'rut': '12.345.678-5',
            'direccion': 'Alameda 100',
            'fecha_nacimiento': '2002-05-10',
            'correo_electronico': 'carlos@test.com',
            'telefono': '912345678',
            'genero': self.genero.id_genero,
            'nivel_educacion': 'superior',
            'password': '123456785',
            'confirm_password': '123456785',
        }
        form = AdminAlumnoForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_creacion_alumno_rechaza_password_mismatched(self):
        data = {
            'nombre': 'Carlos Tapia',
            'rut': '12.345.678-5',
            'direccion': 'Alameda 100',
            'fecha_nacimiento': '2002-05-10',
            'correo_electronico': 'carlos@test.com',
            'telefono': '912345678',
            'genero': self.genero.id_genero,
            'nivel_educacion': 'superior',
            'password': 'ClaveSegura_2026!#',
            'confirm_password': 'OtraPasswordDiferente1#',
        }
        form = AdminAlumnoForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('confirm_password', form.errors)

    def test_creacion_alumno_password_segura_exitosa(self):
        data = {
            'nombre': 'Carlos Tapia',
            'rut': '12.345.678-5',
            'direccion': 'Alameda 100',
            'fecha_nacimiento': '2002-05-10',
            'correo_electronico': 'carlos.tapia@test.com',
            'telefono': '912345678',
            'genero': self.genero.id_genero,
            'nivel_educacion': 'superior',
            'password': 'SuperClaveSegura_2026!#',
            'confirm_password': 'SuperClaveSegura_2026!#',
        }
        form = AdminAlumnoForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        alumno_creado = form.save()
        user_creado = alumno_creado.user

        self.assertFalse(user_creado.check_password('12.345.678-5'))
        self.assertFalse(user_creado.check_password('12345678-5'))
        self.assertFalse(user_creado.check_password('123456785'))
        self.assertTrue(user_creado.check_password('SuperClaveSegura_2026!#'))

    # =========================================================================
    # SUBTAREA 2: Auditoría y Saneamiento de Cuentas Antiguas (S-03)
    # =========================================================================

    def test_auditar_cuentas_antiguas_detecta_y_resetea(self):
        vulnerable_user = User.objects.create_user(
            username='15555555-5',
            rut='15555555-5',
            email='vulnerable@test.com',
            password='15555555-5',
            rol='alumno'
        )

        out = StringIO()
        call_command('auditar_cuentas_rut', '--dry-run', stdout=out)
        salida_dry = out.getvalue()
        self.assertIn('Cuentas vulnerables detectadas: 1', salida_dry)
        self.assertTrue(vulnerable_user.has_usable_password())

        out_reset = StringIO()
        call_command('auditar_cuentas_rut', '--forzar-reseteo', stdout=out_reset)
        salida_reset = out_reset.getvalue()
        self.assertIn('Cuentas con reseteo forzado aplicado: 1', salida_reset)

        vulnerable_user.refresh_from_db()
        self.assertFalse(vulnerable_user.has_usable_password())

    # =========================================================================
    # SUBTAREA 3: Rate Limiting no eludible por formato de RUT (S-05 / S-07)
    # =========================================================================

    def test_normalizacion_rut_canonico(self):
        self.assertEqual(normalizar_rut_canonico('11.111.111-1'), '11111111-1')
        self.assertEqual(normalizar_rut_canonico('11111111-1'), '11111111-1')
        self.assertEqual(normalizar_rut_canonico('111111111'), '11111111-1')
        self.assertEqual(normalizar_rut_canonico('12.345.678-k'), '12345678-K')
        self.assertEqual(normalizar_rut_canonico('12345678K'), '12345678-K')
        self.assertEqual(normalizar_rut_canonico('user@email.com'), 'user@email.com')

    def test_rate_limiting_acumula_variaciones_de_rut(self):
        url = reverse('login')
        variantes = [
            '11.111.111-1',
            '11111111-1',
            '111111111',
            ' 11.111.111-1 ',
        ]

        # 4 intentos iniciales con diferentes variantes de RUT
        for rut_var in variantes:
            resp = self.client.post(url, {'username': rut_var, 'password': 'ClaveIncorrecta123!'})
            self.assertEqual(resp.status_code, 200)
            self.assertIn('RUT/Correo o', resp.content.decode('utf-8', errors='ignore'))

        # 5to intento fallido
        resp5 = self.client.post(url, {'username': '11111111-1', 'password': 'ClaveIncorrecta123!'})
        self.assertEqual(resp5.status_code, 200)

        # 6º intento con otra variante distinta y clave correcta:
        # Debe estar bloqueado temporalmente por haber alcanzado el límite de 5 intentos fallidos compartidos
        resp6 = self.client.post(url, {'username': '111111111', 'password': 'ClaveSegura_2026!#'})
        self.assertEqual(resp6.status_code, 200)
        self.assertIn('bloqueado temporalmente', resp6.content.decode('utf-8', errors='ignore'))

    def test_ip_confiable_previene_spoofing(self):
        url = reverse('login')
        # Intentos con cabecera X-Forwarded-For manipulada por el cliente
        for i in range(16):
            self.client.post(
                url,
                {'username': f'usuario_{i}@test.com', 'password': 'bad'},
                HTTP_X_FORWARDED_FOR=f'192.168.1.{i}',
                REMOTE_ADDR='10.0.0.1'
            )

        # La IP real REMOTE_ADDR es 10.0.0.1 y superó 15 intentos -> debe bloquearse
        resp = self.client.post(
            url,
            {'username': 'otro@test.com', 'password': 'bad'},
            REMOTE_ADDR='10.0.0.1'
        )
        self.assertIn('bloqueado temporalmente', resp.content.decode('utf-8', errors='ignore'))

    # =========================================================================
    # SUBTAREA 4: Cierre de Registro Allauth (S-15)
    # =========================================================================

    def test_allauth_signup_cerrado(self):
        adapter = LbwusAccountAdapter()
        request = self.factory.get('/accounts/signup/')
        self.assertFalse(adapter.is_open_for_signup(request))

        resp = self.client.get('/accounts/signup/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('closed', resp.content.decode('utf-8', errors='ignore').lower())

        # Probar que un POST tampoco registre usuarios
        resp_post = self.client.post('/accounts/signup/', {'username': 'hacker', 'password': 'bad'})
        self.assertEqual(resp_post.status_code, 200)
        self.assertFalse(User.objects.filter(username='hacker').exists())

    # =========================================================================
    # SUBTAREA 5: Cuentas Desactivadas y Google OAuth (S-16)
    # =========================================================================

    def test_cuenta_desactivada_rechazo_login_local(self):
        url = reverse('login')
        resp = self.client.post(url, {'username': '22222222-2', 'password': 'ClaveSegura_2026!#'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('incorrectos', resp.content.decode('utf-8', errors='ignore'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_cuenta_desactivada_rechazo_google_oauth(self):
        adapter = LbwusSocialAdapter()
        request = self.factory.get('/accounts/google/login/callback/')
        request.session = self.client.session
        setattr(request, '_messages', FallbackStorage(request))

        social_account = SocialAccount(provider='google', uid='google_12345')
        sociallogin = SocialLogin(user=self.inactivo_user, account=social_account)
        email_address = EmailAddress(user=self.inactivo_user, email='inactivo@test.com', verified=True, primary=True)
        sociallogin.email_addresses = [email_address]

        with self.assertRaises(ImmediateHttpResponse) as cm:
            adapter.pre_social_login(request, sociallogin)

        # Debe redirigir al login y NO autenticar al usuario inactivo
        self.assertEqual(cm.exception.response.url, reverse('login'))

    # =========================================================================
    # SUBTAREA 6: Aseguramiento de /admin/ (Django Admin)
    # =========================================================================

    def test_admin_django_acceso_restringido_a_staff(self):
        # 1. Alumno no puede acceder a /admin/
        self.client.force_login(self.alumno_user)
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/admin/login/', resp.url)

        # 2. Tutor de negocio sin is_staff tampoco puede acceder a /admin/
        self.client.force_login(self.tutor_user)
        resp_tutor = self.client.get('/admin/')
        self.assertEqual(resp_tutor.status_code, 302)
        self.assertIn('/admin/login/', resp_tutor.url)

        # 3. Solo staff/superusuario activo tiene acceso directo a /admin/
        self.client.force_login(self.staff_user)
        resp_staff = self.client.get('/admin/')
        self.assertEqual(resp_staff.status_code, 200)
