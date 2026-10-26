from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.cache import cache

from alumnos.models import (
    Alumno, Profesor, Tutor, Clase, Asignatura,
    SolicitudRetiro, Banco, Genero, Reporte, Especialidad
)

User = get_user_model()


class SeguridadBlindajeTests(TestCase):
    """
    Suite de verificación del blindaje de seguridad:
    1. Rate limiting / Anti fuerza bruta en Login
    2. Protección CSRF y exigencia de POST en acciones críticas de Admin
    3. Prevención de Price Tampering en pasarela Webpay
    4. Inmutabilidad del RUT en perfiles de usuario
    5. Invalidación de sesiones con cuentas inactivas (is_active=False)
    """

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(descripcion='Masculino')
        cls.especialidad = Especialidad.objects.create(nombre='Matemáticas')

        # Admin
        cls.u_admin = User.objects.create_user(
            username='11111111-1', rut='11111111-1', password='AdminPassword123!',
            rol='admin', first_name='Admin'
        )
        cls.tutor = Tutor.objects.create(user=cls.u_admin)

        # Profesor
        cls.u_prof = User.objects.create_user(
            username='22222222-2', rut='22222222-2', password='ProfPassword123!',
            rol='profesor', first_name='Profesor'
        )
        cls.profesor = Profesor.objects.create(user=cls.u_prof, especialidad=cls.especialidad)

        # Alumno
        cls.u_alum = User.objects.create_user(
            username='33333333-3', rut='33333333-3', password='AlumPassword123!',
            rol='alumno', first_name='Alumno'
        )
        cls.alumno = Alumno.objects.create(user=cls.u_alum, nivel_educacion='media')

        # Asignatura y Clase
        cls.asignatura = Asignatura.objects.create(nombre='Cálculo I')
        cls.clase = Clase.objects.create(
            asignatura=cls.asignatura,
            profesor=cls.profesor,
            modalidad='online',
            horario='10:00:00'
        )

        # Banco y Solicitud de Retiro de prueba
        cls.banco = Banco.objects.create(nombre='Banco Estado')
        cls.solicitud = SolicitudRetiro.objects.create(
            profesor=cls.profesor,
            monto=15000,
            banco=cls.banco,
            tipo_cuenta='Cuenta Rut',
            numero_cuenta='22222222'
        )

        # Reporte de prueba
        cls.reporte = Reporte.objects.create(
            remitente=cls.u_alum,
            descripcion='Problema con el audio en clase'
        )

    def setUp(self):
        cache.clear()

    def _login_admin(self):
        self.client.force_login(self.u_admin)
        s = self.client.session
        s['admin_id'] = self.tutor.id_tutor
        s.save()

    def _login_profesor(self):
        self.client.force_login(self.u_prof)
        s = self.client.session
        s['profesor_id'] = self.profesor.id_profesor
        s.save()

    def _login_alumno(self):
        self.client.force_login(self.u_alum)
        s = self.client.session
        s['alumno_id'] = self.alumno.id_alumno
        s.save()

    # ----------------------------------------------------
    # 1. RATE LIMITING EN LOGIN (ANTI FUERZA BRUTA)
    # ----------------------------------------------------
    def test_01_rate_limiting_login_bloquea_tras_5_intentos_fallidos(self):
        """Tras 5 intentos fallidos, el 6to intento queda bloqueado por cooldown de seguridad."""
        url_login = reverse('login')
        rut_objetivo = '33333333-3'

        for i in range(5):
            resp = self.client.post(url_login, {
                'username': rut_objetivo,
                'password': f'clave_erronea_{i}'
            })
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, 'RUT/Correo o contraseña incorrectos')

        # El sexto intento debe ser rechazado por rate limit
        resp_bloqueado = self.client.post(url_login, {
            'username': rut_objetivo,
            'password': 'AlumPassword123!'  # Incluso con la clave correcta
        })
        self.assertEqual(resp_bloqueado.status_code, 200)
        self.assertContains(resp_bloqueado, 'Demasiados intentos fallidos')

    # ----------------------------------------------------
    # 2. ACCIONES CRÍTICAS DE ADMIN EXIGEN POST (ANTI CSRF)
    # ----------------------------------------------------
    def test_02_eliminar_clase_por_get_es_rechazado_con_405(self):
        """Un enlace GET no puede eliminar clases (requiere POST)."""
        self._login_admin()
        url = reverse('eliminar_clase', args=[self.clase.id_clase])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Clase.objects.filter(pk=self.clase.pk).exists())

    def test_03_eliminar_clase_por_post_elimina_correctamente(self):
        """Un admin legítimo vía POST sí puede eliminar la clase."""
        self._login_admin()
        url = reverse('eliminar_clase', args=[self.clase.id_clase])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Clase.objects.filter(pk=self.clase.pk).exists())

    def test_04_aprobar_y_rechazar_retiro_por_get_rechazado_con_405(self):
        """Aprobación o rechazo de fondos vía GET es rechazado con HTTP 405."""
        self._login_admin()
        url_aprobar = reverse('aprobar_retiro', args=[self.solicitud.id_solicitud])
        url_rechazar = reverse('rechazar_retiro', args=[self.solicitud.id_solicitud])

        self.assertEqual(self.client.get(url_aprobar).status_code, 405)
        self.assertEqual(self.client.get(url_rechazar).status_code, 405)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'pendiente')

    def test_05_resolver_reporte_por_get_rechazado_con_405(self):
        """Resolver reporte vía GET es rechazado con HTTP 405."""
        self._login_admin()
        url = reverse('resolver_reporte', args=[self.reporte.id_reporte])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.reporte.refresh_from_db()
        self.assertEqual(self.reporte.estado, 'pendiente')

    # ----------------------------------------------------
    # 3. WEBPAY: PREVENCIÓN DE PRICE TAMPERING
    # ----------------------------------------------------
    # El price tampering del carrito ya no existe: los paquetes se cobran con el
    # precio del servidor (tests.test_paquetes.CompraTests, test_el_precio_enviado_
    # por_el_cliente_se_ignora).

    # ----------------------------------------------------
    # 4. INMUTABILIDAD DEL RUT EN PERFIL DE PROFESOR
    # ----------------------------------------------------
    def test_07_profesor_no_puede_modificar_su_rut(self):
        """Un profesor no puede modificar su RUT a través de actualizar_perfil_prof."""
        self._login_profesor()
        url = reverse('actualizar_perfil_prof')
        resp = self.client.post(url, {
            'nombre': 'Profesor Modificado',
            'rut': '99999999-9',  # Intento de cambiar su RUT
            'especialidad': self.especialidad.pk,
            'direccion': 'Calle Falsa 123',
            'correo_electronico': 'nuevo@correo.cl',
            'telefono': '987654321',
            'genero': self.genero.pk
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['success'])
        self.assertIn('RUT no puede ser modificado', resp.json()['message'])
        self.u_prof.refresh_from_db()
        self.assertEqual(self.u_prof.rut, '22222222-2')

    # ----------------------------------------------------
    # 5. INHABILITACIÓN DE SESIÓN CON CUENTA INACTIVA
    # ----------------------------------------------------
    def test_08_usuario_con_is_active_false_es_expulsado_por_decorador(self):
        """Si un usuario es desactivado (is_active=False), el decorador de rol invalida su sesión."""
        self._login_alumno()
        url_panel = reverse('alumno_pag1')

        # Estando activo, entra normalmente (código 200)
        resp_activo = self.client.get(url_panel)
        self.assertEqual(resp_activo.status_code, 200)

        # Administrador desactiva la cuenta del usuario
        self.u_alum.is_active = False
        self.u_alum.save()

        # El siguiente request debe ser expulsado al login y limpiar la sesión
        resp_inactivo = self.client.get(url_panel)
        self.assertEqual(resp_inactivo.status_code, 302)
        self.assertIn(reverse('login'), resp_inactivo['Location'])
