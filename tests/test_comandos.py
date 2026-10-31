"""Comandos cargar_catalogos y crear_admin.

crear_admin pide los datos con input() y la contrasena con getpass; aqui se
simulan ambos con unittest.mock.
"""
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from alumnos import catalogos
from alumnos.models import Asignatura, Banco, Especialidad, Genero, Tutor
from alumnos.roles import ADMIN, resolver_rol

User = get_user_model()

RUT = '11.111.111-1'
CLAVE = 'Ornitorrinco-Azul-2026'


class CargarCatalogosTests(TestCase):

    def _cargar(self):
        salida = StringIO()
        call_command('cargar_catalogos', stdout=salida)
        return salida.getvalue()

    def test_crea_los_cuatro_catalogos(self):
        salida = self._cargar()
        self.assertEqual(Genero.objects.count(), len(catalogos.GENEROS))
        self.assertEqual(Especialidad.objects.count(), len(catalogos.ESPECIALIDADES))
        self.assertEqual(Asignatura.objects.count(), len(catalogos.ASIGNATURAS))
        self.assertEqual(Banco.objects.count(), len(catalogos.BANCOS))
        self.assertIn(f'Bancos: {len(catalogos.BANCOS)} creados, 0 ya existían.', salida)

    def test_segunda_ejecucion_no_duplica(self):
        self._cargar()
        salida = self._cargar()
        self.assertEqual(Genero.objects.count(), len(catalogos.GENEROS))
        self.assertEqual(Especialidad.objects.count(), len(catalogos.ESPECIALIDADES))
        self.assertEqual(Asignatura.objects.count(), len(catalogos.ASIGNATURAS))
        self.assertEqual(Banco.objects.count(), len(catalogos.BANCOS))
        self.assertIn(f'Asignaturas: 0 creados, {len(catalogos.ASIGNATURAS)} ya existían.', salida)

    def test_no_borra_ni_modifica_registros_existentes(self):
        propio = Banco.objects.create(nombre='Banco Propio')
        existente = Banco.objects.create(nombre='MACH')
        Genero.objects.create(descripcion='Otro')
        Genero.objects.create(descripcion='Otro')  # descripcion no es unica

        salida = self._cargar()

        self.assertTrue(Banco.objects.filter(pk=propio.pk).exists())
        self.assertEqual(Banco.objects.get(nombre='MACH').pk, existente.pk)
        self.assertEqual(Banco.objects.count(), len(catalogos.BANCOS) + 1)
        self.assertEqual(Genero.objects.filter(descripcion='Otro').count(), 2)
        self.assertIn(f'Bancos: {len(catalogos.BANCOS) - 1} creados, 1 ya existían.', salida)


class CrearAdminTests(TestCase):

    def _crear(self, datos=(RUT, 'Ana', 'Pérez', 'ana@example.com'),
               claves=(CLAVE, CLAVE), *args):
        salida = StringIO()
        with mock.patch('builtins.input', side_effect=list(datos)), \
                mock.patch('getpass.getpass', side_effect=list(claves)) as getpass:
            self.getpass = getpass
            call_command('crear_admin', *args, stdout=salida)
        return salida.getvalue()

    def test_crea_usuario_y_tutor_con_rol_admin(self):
        salida = self._crear()

        user = User.objects.get(rut='11111111-1')
        self.assertEqual(user.username, '11111111-1')
        self.assertEqual(user.rol, 'admin')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password(CLAVE))
        self.assertTrue(Tutor.objects.filter(user=user).exists())
        rol, perfil = resolver_rol(user)
        self.assertEqual(rol, ADMIN)
        self.assertEqual(perfil, user.perfil_tutor)
        self.assertIn('Administrador 11111111-1 creado', salida)
        self.assertNotIn(CLAVE, salida)

    def test_el_admin_creado_inicia_sesion_y_entra_al_dashboard(self):
        self._crear()

        respuesta = self.client.post(
            reverse('login'), {'username': RUT, 'password': CLAVE}
        )
        self.assertRedirects(
            respuesta, reverse('dashboard_admin'), fetch_redirect_response=False
        )
        self.assertEqual(self.client.get(reverse('dashboard_admin')).status_code, 200)

    def test_no_superuser_crea_admin_del_portal_sin_acceso_a_django_admin(self):
        self._crear(
            ('22.222.222-2', 'Luis', 'Soto', 'luis@example.com'),
            (CLAVE, CLAVE), '--no-superuser',
        )
        user = User.objects.get(rut='22222222-2')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(resolver_rol(user)[0], ADMIN)

    def test_rut_existente_no_crea_nada(self):
        User.objects.create_user('11111111-1', rut='11111111-1', password='x')

        with self.assertRaisesMessage(CommandError, 'Ya existe un usuario con ese RUT'):
            self._crear()

        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(Tutor.objects.exists())
        self.getpass.assert_not_called()

    def test_rut_existente_en_otro_formato_no_crea_nada(self):
        User.objects.create_user('otro', rut='111111111', password='x')

        with self.assertRaisesMessage(CommandError, 'Ya existe un usuario con ese RUT'):
            self._crear()

        self.assertEqual(User.objects.count(), 1)

    def test_correo_demasiado_largo_no_crea_nada(self):
        correo = 'a' * 64 + '@' + '.'.join(['b' * 62] * 3) + '.com'
        with self.assertRaisesMessage(CommandError, 'Correo:'):
            self._crear((RUT, 'Ana', 'Pérez', correo))
        self.assertFalse(User.objects.exists())

    def test_correo_existente_no_crea_nada(self):
        User.objects.create_user('otro', email='ANA@example.com', password='x')

        with self.assertRaisesMessage(CommandError, 'Ya existe un usuario con ese correo'):
            self._crear()

        self.assertEqual(User.objects.count(), 1)

    def test_rut_invalido_no_crea_nada(self):
        with self.assertRaisesMessage(CommandError, 'El RUT ingresado no es válido'):
            self._crear(('11.111.111-2', 'Ana', 'Pérez', 'ana@example.com'))
        self.assertFalse(User.objects.exists())

    def test_rechaza_contrasena_debil(self):
        with self.assertRaisesMessage(CommandError, 'Contraseña rechazada'):
            self._crear(claves=('12345678', '12345678'))
        self.assertFalse(User.objects.exists())
        self.assertFalse(Tutor.objects.exists())

    def test_rechaza_contrasenas_distintas(self):
        with self.assertRaisesMessage(CommandError, 'no coinciden'):
            self._crear(claves=(CLAVE, CLAVE + 'x'))
        self.assertFalse(User.objects.exists())

    def test_si_falla_el_tutor_no_queda_el_usuario(self):
        with mock.patch.object(Tutor.objects, 'create', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self._crear()
        self.assertFalse(User.objects.exists())

    def test_la_contrasena_no_es_un_argumento(self):
        with self.assertRaises(CommandError):
            call_command('crear_admin', '--password', CLAVE)
