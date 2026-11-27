"""Pruebas de regresión para funciones refactorizadas:

1. user_profesor.views.panel_profesor
2. alumnos.views.custom_login
3. user_profesor.views.regis_tutor

(Se quitaron las de confirmacion, calcular_saldos e iniciar_webpay: usaban el modelo Pago y PlanAlumno, retirados
con SCRUM-85. La confirmacion de pagos vive en test_paquetes y test_qa_pagos.)
"""


from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from alumnos.models import (
    Alumno,
    Asignatura,
    Clase,
    Especialidad,
    Genero,
    Profesor,
    Tutor,
)
from alumnos.roles import ADMIN, PROFESOR

User = get_user_model()


class BaseRefactorTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.genero = Genero.objects.create(descripcion='Otro')
        self.especialidad = Especialidad.objects.create(nombre='Matemáticas')
        self.asignatura = Asignatura.objects.create(nombre='Cálculo I')

        self.u_alumno = User.objects.create_user(
            username='11111111-1',
            rut='11111111-1',
            email='alumno_ref@test.cl',
            password='Password123!',
            rol='alumno',
            first_name='Ana',
        )
        self.alumno = Alumno.objects.create(user=self.u_alumno, nivel_educacion='media')

        self.u_prof = User.objects.create_user(
            username='12345678-5',
            rut='12345678-5',
            email='prof_ref@test.cl',
            password='Password123!',
            rol='profesor',
            first_name='Carlos',
        )
        self.profesor = Profesor.objects.create(
            user=self.u_prof,
            especialidad=self.especialidad,
            titulo_estado=Profesor.TITULO_APROBADO,
        )
        self.clase = Clase.objects.create(
            asignatura=self.asignatura,
            profesor=self.profesor,
            modalidad='online',
        )

    def _login_profesor(self):
        self.client.force_login(self.u_prof)
        session = self.client.session
        session[PROFESOR.clave_sesion] = self.profesor.pk
        session.save()

    def _login_admin(self):
        u_admin = User.objects.create_user(
            username='16000000-7',
            rut='16000000-7',
            email='admin_ref@test.cl',
            password='Password123!',
            rol='admin',
            first_name='Admin',
        )
        tutor = Tutor.objects.create(user=u_admin)
        self.client.force_login(u_admin)
        session = self.client.session
        session[ADMIN.clave_sesion] = tutor.pk
        session.save()
        return u_admin, tutor


class RefactorPanelProfesorTests(BaseRefactorTestCase):
    """Punto 3: user_profesor.views.panel_profesor."""

    def test_panel_profesor_anonimo_redirige(self):
        resp = self.client.get(reverse('panel_profesor'))
        self.assertEqual(resp.status_code, 302)


class RefactorCustomLoginTests(BaseRefactorTestCase):
    """Punto 4: alumnos.views.custom_login."""

    def test_get_login_retorna_200(self):
        resp = self.client.get(reverse('login'))
        self.assertEqual(resp.status_code, 200)

    def test_login_campos_vacios_muestra_error(self):
        resp = self.client.post(reverse('login'), {'username': '', 'password': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Por favor ingrese todos los campos.')

    def test_login_usuario_sin_perfil_muestra_error(self):
        User.objects.create_user(
            username='sinperfil',
            email='sinperfil@test.cl',
            password='Password123!',
            rol='alumno',
        )
        resp = self.client.post(reverse('login'), {'username': 'sinperfil', 'password': 'Password123!'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Tu cuenta no tiene un perfil asignado en el sistema.')

    def test_login_bloquea_tras_5_intentos_fallidos_y_sesion_activa_redirige(self):
        for _ in range(5):
            self.client.post(reverse('login'), {'username': '11111111-1', 'password': 'mala'})
        resp_bloqueo = self.client.post(reverse('login'), {'username': '11111111-1', 'password': 'Password123!'})
        self.assertContains(resp_bloqueo, 'Demasiados intentos fallidos.')

        cache.clear()
        resp_ok = self.client.post(reverse('login'), {'username': '11111111-1', 'password': 'Password123!'})
        self.assertRedirects(resp_ok, reverse('alumno_pag1'), fetch_redirect_response=False)

        # Ya con sesión activa, GET a login redirige al portal
        resp_ya_activo = self.client.get(reverse('login'))
        self.assertRedirects(resp_ya_activo, reverse('alumno_pag1'), fetch_redirect_response=False)


class RefactorRegisTutorTests(BaseRefactorTestCase):
    """Punto 5: user_profesor.views.regis_tutor."""

    def test_no_admin_no_accede_a_regis_tutor(self):
        resp_get = self.client.get(reverse('regis_tutor'))
        self.assertRedirects(resp_get, reverse('login'), fetch_redirect_response=False)

        resp_post = self.client.post(reverse('regis_tutor'), {})
        self.assertEqual(resp_post.status_code, 403)
        self.assertFalse(resp_post.json()['success'])

    def test_admin_ve_formulario_y_valida_errores(self):
        self._login_admin()
        resp_get = self.client.get(reverse('regis_tutor'))
        self.assertEqual(resp_get.status_code, 200)

        from alumnos.utils import validar_rut_chileno
        rut_valido = next(
            f"{n}-{dv}"
            for n in range(15000000, 15000100)
            for dv in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'K']
            if validar_rut_chileno(f"{n}-{dv}")
        )

        resp_menor = self.client.post(reverse('regis_tutor'), {
            'nombre': 'Nuevo Admin',
            'rut': rut_valido,
            'direccion': 'Av Test 123',
            'fecha_nacimiento': '2015-01-01',
            'correo_electronico': 'nuevo_admin@test.cl',
            'telefono': '912345678',
            'genero': str(self.genero.id_genero),
            'password': 'ClaveSegura99!',
            'confirm_password': 'ClaveSegura99!',
        })
        self.assertFalse(resp_menor.json()['success'])
        self.assertIn('18 años', resp_menor.json()['message'])

        resp_distintas = self.client.post(reverse('regis_tutor'), {
            'nombre': 'Nuevo Admin',
            'rut': rut_valido,
            'direccion': 'Av Test 123',
            'fecha_nacimiento': '1990-01-01',
            'correo_electronico': 'nuevo_admin@test.cl',
            'telefono': '912345678',
            'genero': str(self.genero.id_genero),
            'password': 'ClaveSegura99!',
            'confirm_password': 'OtraClave99!',
        })
        self.assertFalse(resp_distintas.json()['success'])
        self.assertIn('no coinciden', resp_distintas.json()['message'])

    def test_admin_crea_nuevo_tutor_exitosamente(self):
        self._login_admin()
        # 12345678-5 ya lo usa self.u_prof; usamos 14000000-0? Validemos primero un RUT válido no usado
        from alumnos.utils import validar_rut_chileno
        rut_valido = next(
            f"{n}-{dv}"
            for n in range(15000000, 15000100)
            for dv in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'K']
            if validar_rut_chileno(f"{n}-{dv}")
        )
        resp = self.client.post(reverse('regis_tutor'), {
            'nombre': 'Tutor Nuevo',
            'rut': rut_valido,
            'direccion': 'Calle Uno 456',
            'fecha_nacimiento': '1990-05-10',
            'correo_electronico': 'tutor_nuevo@test.cl',
            'telefono': '987654321',
            'genero': str(self.genero.id_genero),
            'password': 'ClaveSegura99!',
            'confirm_password': 'ClaveSegura99!',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        nuevo_user = User.objects.get(rut=rut_valido)
        self.assertEqual(nuevo_user.rol, 'admin')
        self.assertTrue(Tutor.objects.filter(user=nuevo_user).exists())
