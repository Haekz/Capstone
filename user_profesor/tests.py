"""Tests del panel del profesor y del acceso de administrador.

Cubren tres bugs verificados explotandolos antes de corregirlos:

1. custom_login() y login_admin() podian dejar la sesion apuntando a un
   perfil Tutor ajeno (Tutor.objects.first()) o a un user.id que no es un
   id_tutor.
2. El panel regalaba $45.000/$36.000 a las cuentas sin inscripciones, y
   solicitar_retiro() dejaba retirar ese dinero inexistente.
3. El grafico de rendimiento rellenaba los meses vacios con [14, 22, 18,
   25, 32] en vez de mostrar 0.
"""

from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from alumnos.models import (
    Alumno,
    Clase,
    Genero,
    Inscripcion,
    Profesor,
    SolicitudRetiro,
    Tutor,
)
from user_profesor.views import PAGO_PROFESOR, VALOR_INSCRIPCION, calcular_saldos


class AccesoAdministradorTests(TestCase):
    """La sesion de admin debe corresponder al perfil del propio usuario."""

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(descripcion='Otro')

        # Tutor legitimo, el primero de la tabla.
        cls.user_ana = User.objects.create_user(
            '20202020-2', password='clave12345', first_name='Ana'
        )
        cls.tutor_ana = Tutor.objects.create(
            user=cls.user_ana, nombre='Ana Primera', rut='20202020-2',
            direccion='C1', fecha_nacimiento=date(1980, 1, 1),
            correo_electronico='ana@lbwus.cl', genero=cls.genero,
        )

        # Usuario con is_staff pero SIN perfil Tutor propio.
        cls.user_beto = User.objects.create_user(
            '30303030-3', password='clave12345', first_name='Beto',
            is_staff=True,
        )

    def test_staff_sin_perfil_no_hereda_un_tutor_ajeno(self):
        """Antes caia en Tutor.objects.first() y operaba como Ana."""
        self.client.post(
            reverse('login'),
            {'username': '30303030-3', 'password': 'clave12345'},
        )

        self.assertNotEqual(
            self.client.session.get('admin_id'),
            self.tutor_ana.id_tutor,
            'La sesion quedo usando el perfil de otra persona.',
        )
        self.assertIsNone(self.client.session.get('admin_id'))

    def test_login_admin_no_guarda_un_user_id_como_admin_id(self):
        """user.id y Tutor.id_tutor son numeraciones distintas."""
        respuesta = self.client.post(
            reverse('login_admin'),
            {'identificador': '30303030-3', 'password': 'clave12345'},
        )

        self.assertFalse(respuesta.json()['success'])
        self.assertIsNone(self.client.session.get('admin_id'))

    def test_tutor_legitimo_entra_con_su_propio_perfil(self):
        respuesta = self.client.post(
            reverse('login_admin'),
            {'identificador': '20202020-2', 'password': 'clave12345'},
        )

        self.assertTrue(respuesta.json()['success'])
        self.assertEqual(
            self.client.session.get('admin_id'), self.tutor_ana.id_tutor
        )

    def test_las_dos_vistas_de_login_coinciden(self):
        """custom_login() y login_admin() deben dejar la misma sesion."""
        self.client.post(
            reverse('login_admin'),
            {'identificador': '20202020-2', 'password': 'clave12345'},
        )
        via_admin = self.client.session.get('admin_id')

        self.client.logout()

        self.client.post(
            reverse('login'),
            {'username': '20202020-2', 'password': 'clave12345'},
        )
        via_custom = self.client.session.get('admin_id')

        self.assertEqual(via_admin, via_custom)


class SaldoProfesorTests(TestCase):
    """Una cuenta sin actividad no puede mostrar ni entregar dinero."""

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(descripcion='Otro')

        cls.user = User.objects.create_user(
            '40404040-4', password='clave12345', first_name='Caro'
        )
        cls.profesor = Profesor.objects.create(
            user=cls.user, nombre='Caro Nueva', rut='40404040-4',
            especialidad='Mate', direccion='C4',
            fecha_nacimiento=date(1990, 5, 5),
            correo_electronico='caro@lbwus.cl', telefono='911111111',
            genero=cls.genero,
        )

    def _entrar(self):
        self.client.force_login(self.user)

        sesion = self.client.session
        sesion['profesor_id'] = self.profesor.id_profesor
        sesion.save()

    def _inscribir(self, cantidad):
        clase = Clase.objects.create(
            nombre_curso='Algebra', modalidad='online',
            horario=time(10, 0), id_profesor=self.profesor,
        )

        for numero in range(cantidad):
            user = User.objects.create_user(f'6000000{numero}-0', password='x')
            alumno = Alumno.objects.create(
                user=user, nombre=f'Alumno {numero}', rut=f'6000000{numero}-0',
                nivel_educacion='media', direccion='C',
                fecha_nacimiento=date(2000, 1, 1),
                correo_electronico=f'al{numero}@lbwus.cl', genero=self.genero,
            )
            Inscripcion.objects.create(id_alumno=alumno, id_clase=clase)

        return clase

    # -- cuenta nueva -----------------------------------------------------

    def test_profesor_nuevo_arranca_en_cero(self):
        saldos = calcular_saldos(self.profesor)

        self.assertEqual(saldos['total_ganado'], 0)
        self.assertEqual(saldos['disponible'], 0)
        self.assertEqual(saldos['pendiente'], 0)

    def test_el_panel_no_muestra_dinero_regalado(self):
        self._entrar()

        contexto = self.client.get(reverse('panel_profesor')).context

        self.assertEqual(contexto['saldo_total'], '$0')
        self.assertEqual(contexto['saldo_disponible'], '$0')
        self.assertEqual(contexto['saldo_pendiente'], '$0')
        self.assertEqual(contexto['saldo_disponible_raw'], 0)

    def test_no_se_puede_retirar_sin_saldo(self):
        self._entrar()

        respuesta = self.client.post(reverse('solicitar_retiro'), {
            'monto': '36000', 'banco': 'Banco Estado',
            'tipo_cuenta': 'Vista', 'numero_cuenta': '1',
        })

        self.assertFalse(respuesta.json()['success'])
        self.assertFalse(
            SolicitudRetiro.objects.filter(id_profesor=self.profesor).exists(),
            'Se registro un retiro sobre dinero que no existe.',
        )

    # -- cuenta con actividad real ----------------------------------------

    def test_el_saldo_refleja_las_inscripciones(self):
        self._inscribir(3)

        saldos = calcular_saldos(self.profesor)

        self.assertEqual(saldos['total_ganado'], 3 * VALOR_INSCRIPCION)
        self.assertEqual(saldos['disponible'], 3 * PAGO_PROFESOR)

    def test_un_retiro_valido_descuenta_el_saldo(self):
        self._inscribir(3)
        self._entrar()

        respuesta = self.client.post(reverse('solicitar_retiro'), {
            'monto': '10000', 'banco': 'Banco Estado',
            'tipo_cuenta': 'Vista', 'numero_cuenta': '1',
        })

        self.assertTrue(respuesta.json()['success'])
        self.assertEqual(
            calcular_saldos(self.profesor)['disponible'],
            3 * PAGO_PROFESOR - 10000,
        )

    def test_no_se_puede_retirar_mas_de_lo_disponible(self):
        self._inscribir(1)
        self._entrar()

        respuesta = self.client.post(reverse('solicitar_retiro'), {
            'monto': '999999', 'banco': 'Banco Estado',
            'tipo_cuenta': 'Vista', 'numero_cuenta': '1',
        })

        self.assertFalse(respuesta.json()['success'])
        self.assertEqual(SolicitudRetiro.objects.count(), 0)


class GraficoRendimientoTests(TestCase):
    """Un mes sin inscripciones vale 0, no un numero inventado."""

    MOCK_ANTIGUO = {14, 22, 18, 25, 32}

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(descripcion='Otro')

        cls.user = User.objects.create_user(
            '70707070-7', password='clave12345', first_name='Dante'
        )
        cls.profesor = Profesor.objects.create(
            user=cls.user, nombre='Dante Rios', rut='70707070-7',
            especialidad='Fisica', direccion='C7',
            fecha_nacimiento=date(1988, 3, 3),
            correo_electronico='dante@lbwus.cl', telefono='922222222',
            genero=cls.genero,
        )

    def _grafico(self):
        self.client.force_login(self.user)

        sesion = self.client.session
        sesion['profesor_id'] = self.profesor.id_profesor
        sesion.save()

        return self.client.get(reverse('panel_profesor')).context[
            'rendimiento_meses'
        ]

    def test_sin_actividad_todos_los_meses_valen_cero(self):
        for mes in self._grafico():
            with self.subTest(mes=mes['mes']):
                self.assertEqual(mes['cantidad'], 0)
                self.assertEqual(mes['porcentaje'], 0)

    def test_no_reaparecen_los_valores_inventados(self):
        """Blinda contra volver a rellenar con mock_values."""
        cantidades = {mes['cantidad'] for mes in self._grafico()}

        self.assertFalse(
            cantidades & self.MOCK_ANTIGUO,
            f'El grafico volvio a mostrar datos simulados: {cantidades}',
        )

    def test_el_mes_en_curso_cuenta_las_inscripciones_reales(self):
        clase = Clase.objects.create(
            nombre_curso='Optica', modalidad='online',
            horario=time(9, 0), id_profesor=self.profesor,
        )
        user = User.objects.create_user('80808080-8', password='x')
        alumno = Alumno.objects.create(
            user=user, nombre='Emi Soto', rut='80808080-8',
            nivel_educacion='media', direccion='C8',
            fecha_nacimiento=date(2001, 1, 1),
            correo_electronico='emi@lbwus.cl', genero=self.genero,
        )
        Inscripcion.objects.create(id_alumno=alumno, id_clase=clase)

        # El ultimo elemento del grafico es el mes en curso.
        self.assertEqual(self._grafico()[-1]['cantidad'], 1)
