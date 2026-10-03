"""Validaciones funcionales de flujos clave de LBWUS.

La idea no es re-testear cada helper aislado, sino recorrer los caminos que
vive el usuario: registro/login por rol, bloqueo de paneles ajenos, logout,
enlaces principales, estados vacios coherentes y salidas claras en acciones.
"""

from datetime import date, time
from unittest.mock import patch

from django.contrib.auth import get_user_model

User = get_user_model()
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Alumno, Clase, Genero, Inscripcion, Profesor, Tutor


class FlujoRolesTests(TestCase):
    """Cada rol debe terminar en su panel y no invadir el de otro."""

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(descripcion='Otro')

        cls.user_alumno = User.objects.create_user(
            '11111111-1', password='clave12345', first_name='Alma'
        )
        cls.alumno = Alumno.objects.create(
            user=cls.user_alumno,
            nombre='Alma Ruiz',
            rut='11111111-1',
            nivel_educacion='media',
            direccion='Calle 1',
            fecha_nacimiento=date(2001, 1, 1),
            correo_electronico='alma@lbwus.cl',
            genero=cls.genero,
        )

        cls.user_prof = User.objects.create_user(
            '22222222-2', password='clave12345', first_name='Bruno'
        )
        cls.profesor = Profesor.objects.create(
            user=cls.user_prof,
            nombre='Bruno Diaz',
            rut='22222222-2',
            especialidad='Matematicas',
            direccion='Calle 2',
            fecha_nacimiento=date(1990, 2, 2),
            correo_electronico='bruno@lbwus.cl',
            telefono='911111111',
            genero=cls.genero,
        )

        cls.user_admin = User.objects.create_user(
            '33333333-3', password='clave12345', first_name='Cami'
        )
        cls.tutor = Tutor.objects.create(
            user=cls.user_admin,
            nombre='Cami Soto',
            rut='33333333-3',
            direccion='Calle 3',
            fecha_nacimiento=date(1985, 3, 3),
            correo_electronico='cami@lbwus.cl',
            genero=cls.genero,
        )

    def _login_alumno(self):
        self.client.post(
            reverse('login'),
            {'username': '11111111-1', 'password': 'clave12345'},
        )

    def _login_profesor(self):
        self.client.post(
            reverse('login_prof'),
            {'identificador': '22222222-2', 'password': 'clave12345'},
        )

    def _login_admin(self):
        self.client.post(
            reverse('login_admin'),
            {'identificador': '33333333-3', 'password': 'clave12345'},
        )

    # -- llegadas al panel correcto ---------------------------------------

    def test_alumno_llega_a_su_portal(self):
        respuesta = self.client.post(
            reverse('login'),
            {'username': '11111111-1', 'password': 'clave12345'},
            follow=True,
        )

        self.assertEqual(respuesta.redirect_chain[-1][0], reverse('alumno_pag1'))
        self.assertEqual(self.client.session.get('alumno_id'), self.alumno.id_alumno)

    def test_profesor_llega_a_su_panel(self):
        respuesta = self.client.post(
            reverse('login_prof'),
            {'identificador': '22222222-2', 'password': 'clave12345'},
        )

        self.assertTrue(respuesta.json()['success'])
        self.assertEqual(
            self.client.session.get('profesor_id'), self.profesor.id_profesor
        )

    def test_admin_llega_a_su_panel(self):
        respuesta = self.client.post(
            reverse('login_admin'),
            {'identificador': '33333333-3', 'password': 'clave12345'},
        )

        self.assertTrue(respuesta.json()['success'])
        self.assertEqual(self.client.session.get('admin_id'), self.tutor.id_tutor)

    # -- no entrar al panel ajeno por URL ---------------------------------

    def test_alumno_no_entra_a_panel_profesor_ni_admin(self):
        self._login_alumno()

        panel_prof = self.client.get(reverse('panel_profesor'))
        panel_admin = self.client.get(reverse('dashboard_admin'))

        self.assertEqual(panel_prof.status_code, 302)
        self.assertEqual(panel_admin.status_code, 302)

    def test_profesor_no_entra_a_panel_alumno_ni_admin(self):
        self._login_profesor()

        panel_alumno = self.client.get(reverse('alumno_pag1'))
        panel_admin = self.client.get(reverse('dashboard_admin'))

        self.assertEqual(panel_alumno.status_code, 302)
        self.assertEqual(panel_admin.status_code, 302)

    def test_admin_no_entra_a_panel_alumno_ni_profesor(self):
        self._login_admin()

        panel_alumno = self.client.get(reverse('alumno_pag1'))
        panel_prof = self.client.get(reverse('panel_profesor'))

        self.assertEqual(panel_alumno.status_code, 302)
        self.assertEqual(panel_prof.status_code, 302)


class FlujoLogoutYCacheTests(TestCase):
    """Cerrar sesion debe bloquear privado incluso con refresh/back."""

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')

        cls.user_alumno = User.objects.create_user('44444444-4', password='clave12345')
        cls.alumno = Alumno.objects.create(
            user=cls.user_alumno, nombre='Dani Luna', rut='44444444-4',
            nivel_educacion='media', direccion='Calle 4',
            fecha_nacimiento=date(2000, 4, 4), correo_electronico='d@lbwus.cl',
            genero=genero,
        )

        cls.user_prof = User.objects.create_user('55555555-5', password='clave12345')
        cls.profesor = Profesor.objects.create(
            user=cls.user_prof, nombre='Eva Mora', rut='55555555-5',
            especialidad='Lenguaje', direccion='Calle 5',
            fecha_nacimiento=date(1991, 5, 5), correo_electronico='e@lbwus.cl',
            telefono='922222222', genero=genero,
        )

        cls.user_admin = User.objects.create_user('66666666-6', password='clave12345')
        cls.tutor = Tutor.objects.create(
            user=cls.user_admin, nombre='Fede Paz', rut='66666666-6',
            direccion='Calle 6', fecha_nacimiento=date(1982, 6, 6),
            correo_electronico='f@lbwus.cl', genero=genero,
        )

    def _entrar(self, user, clave, valor):
        self.client.force_login(user)
        sesion = self.client.session
        sesion[clave] = valor
        sesion.save()

    def test_logout_alumno_bloquea_portal_y_marca_no_store(self):
        self._entrar(self.user_alumno, 'alumno_id', self.alumno.id_alumno)

        antes = self.client.get(reverse('alumno_pag1'))
        self.assertIn('no-store', antes.headers.get('Cache-Control', ''))

        self.client.get(reverse('logout_alumno'))
        despues = self.client.get(reverse('alumno_pag1'))

        self.assertEqual(despues.status_code, 302)
        self.assertIn(reverse('login'), despues['Location'])

    def test_logout_profesor_bloquea_panel_y_marca_no_store(self):
        self._entrar(self.user_prof, 'profesor_id', self.profesor.id_profesor)

        antes = self.client.get(reverse('panel_profesor'))
        self.assertIn('no-store', antes.headers.get('Cache-Control', ''))

        self.client.get(reverse('logout_prof'))
        despues = self.client.get(reverse('panel_profesor'))

        self.assertEqual(despues.status_code, 302)
        self.assertIn(reverse('regis_prof'), despues['Location'])

    def test_logout_admin_bloquea_panel_y_marca_no_store(self):
        self._entrar(self.user_admin, 'admin_id', self.tutor.id_tutor)

        antes = self.client.get(reverse('dashboard_admin'))
        self.assertIn('no-store', antes.headers.get('Cache-Control', ''))

        self.client.get(reverse('logout_admin'))
        despues = self.client.get(reverse('dashboard_admin'))

        self.assertEqual(despues.status_code, 302)
        self.assertIn(reverse('login'), despues['Location'])


class FlujoPrincipalYEstadosTests(TestCase):
    """Enlaces vivos y estados vacios coherentes."""

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        cls.user_prof = User.objects.create_user('77777777-7', password='clave12345')
        cls.profesor = Profesor.objects.create(
            user=cls.user_prof, nombre='Gabi Rios', rut='77777777-7',
            especialidad='Historia', direccion='Calle 7',
            fecha_nacimiento=date(1992, 7, 7), correo_electronico='g@lbwus.cl',
            telefono='933333333', genero=genero,
        )

    def test_paginas_principales_cargan_sin_romper(self):
        for nombre in (
            'home', 'planes', 'servicios', 'nosotros',
            'contactos', 'simulador', 'opcion_user', 'pago',
        ):
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200)

    def test_profesor_nuevo_ve_estado_vacio_coherente(self):
        self.client.force_login(self.user_prof)
        sesion = self.client.session
        sesion['profesor_id'] = self.profesor.id_profesor
        sesion.save()

        contexto = self.client.get(reverse('panel_profesor')).context

        self.assertEqual(contexto['saldo_total'], '$0')
        self.assertEqual(contexto['saldo_disponible'], '$0')
        self.assertEqual(contexto['saldo_pendiente'], '$0')
        self.assertEqual(contexto['dinero_hoy'], '$0')
        self.assertTrue(all(m['cantidad'] == 0 for m in contexto['rendimiento_meses']))


class FlujoAccionesUsuarioTests(TestCase):
    """Reserva, cancelacion, pago y recuperacion deben dejar salida clara."""

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(descripcion='Otro')

        cls.user_alumno = User.objects.create_user('88888888-8', password='clave12345')
        cls.alumno = Alumno.objects.create(
            user=cls.user_alumno, nombre='Hana Sol', rut='88888888-8',
            nivel_educacion='media', direccion='Calle 8',
            fecha_nacimiento=date(2002, 8, 8), correo_electronico='h@lbwus.cl',
            genero=cls.genero,
        )

        cls.user_prof = User.objects.create_user('99999999-9', password='clave12345')
        cls.profesor = Profesor.objects.create(
            user=cls.user_prof, nombre='Ivan Cruz', rut='99999999-9',
            especialidad='Biologia', direccion='Calle 9',
            fecha_nacimiento=date(1990, 9, 9), correo_electronico='i@lbwus.cl',
            telefono='944444444', genero=cls.genero,
        )
        cls.clase = Clase.objects.create(
            nombre_curso='Biologia I', modalidad='online', horario=time(11, 0),
            id_profesor=cls.profesor,
        )

    def _entrar_como_alumno(self):
        self.client.force_login(self.user_alumno)
        sesion = self.client.session
        sesion['alumno_id'] = self.alumno.id_alumno
        sesion.save()

    def test_reserva_exitosa_y_mensaje_claro(self):
        self._entrar_como_alumno()

        respuesta = self.client.post(reverse('inscribir_clase'), {
            'id_clase': self.clase.id_clase,
        })

        self.assertTrue(respuesta.json()['success'])
        self.assertIn('exitosamente', respuesta.json()['message'])
        self.assertTrue(
            Inscripcion.objects.filter(
                id_alumno=self.alumno, id_clase=self.clase,
            ).exists()
        )

    def test_reserva_duplicada_rechaza_y_explica(self):
        self._entrar_como_alumno()
        Inscripcion.objects.create(id_alumno=self.alumno, id_clase=self.clase)

        respuesta = self.client.post(reverse('inscribir_clase'), {
            'id_clase': self.clase.id_clase,
        })

        self.assertFalse(respuesta.json()['success'])
        self.assertIn('Ya estás inscrito', respuesta.json()['message'])

    def test_cancelacion_exitosa_redirige_al_portal(self):
        self._entrar_como_alumno()
        inscripcion = Inscripcion.objects.create(
            id_alumno=self.alumno, id_clase=self.clase,
        )

        respuesta = self.client.get(
            reverse('cancelar_inscripcion', args=[inscripcion.id_inscripcion]),
            follow=True,
        )

        self.assertEqual(respuesta.redirect_chain[-1][0], reverse('alumno_pag1'))
        self.assertFalse(Inscripcion.objects.filter(pk=inscripcion.pk).exists())

    def test_cancelacion_ajena_no_borra_y_da_404(self):
        otro_user = User.objects.create_user('12121212-1', password='x')
        otro_alumno = Alumno.objects.create(
            user=otro_user, nombre='Otra Persona', rut='12121212-1',
            nivel_educacion='media', direccion='Calle 12',
            fecha_nacimiento=date(2003, 1, 1), correo_electronico='o@lbwus.cl',
            genero=self.genero,
        )
        ajena = Inscripcion.objects.create(id_alumno=otro_alumno, id_clase=self.clase)
        self._entrar_como_alumno()

        respuesta = self.client.get(
            reverse('cancelar_inscripcion', args=[ajena.id_inscripcion])
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Inscripcion.objects.filter(pk=ajena.pk).exists())

    def test_pago_sin_monto_valido_vuelve_a_planes(self):
        respuesta = self.client.post(reverse('iniciar_webpay'), {
            'amount': '0', 'carrito': '[]',
        })

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], reverse('planes'))

    @patch('alumnos.views._tx')
    def test_pago_ok_muestra_confirmacion_clara(self, mock_tx):
        mock_tx.return_value.commit.return_value = {
            'response_code': 0,
            'status': 'AUTHORIZED',
            'buy_order': 'LB123',
            'amount': 19990,
            'authorization_code': 'AUTH1',
            'card_detail': {'card_number': '6623'},
            'transaction_date': '2026-09-20T00:00:00Z',
        }
        sesion = self.client.session
        sesion['orden_pendiente'] = {
            'buy_order': 'LB123',
            'carrito': '[{"titulo":"Plan Base","cantidad":1,"precio":"19990"}]',
        }
        sesion.save()

        respuesta = self.client.get(reverse('confirmacion'), {'token_ws': 'tok'})
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('LB123', html)
        self.assertIn('$19.990', html)

    def test_pago_cancelado_tiene_salida_clara(self):
        sesion = self.client.session
        sesion['orden_pendiente'] = {'buy_order': 'LB999', 'carrito': '[]'}
        sesion.save()

        respuesta = self.client.get(reverse('confirmacion'), {'TBK_TOKEN': 'cancel'})
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Pago Anulado', html)
        self.assertIn('No se realizó ningún cargo', html)

    def test_confirmacion_sin_token_no_rompe_y_vuelve_a_planes(self):
        respuesta = self.client.get(reverse('confirmacion'))

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], reverse('planes'))

    def test_recuperacion_de_clave_tiene_salida_clara(self):
        user = User.objects.create_user(
            username='13131313-1', email='reset@lbwus.cl', password='x'
        )
        _ = user

        respuesta = self.client.post(
            reverse('password_reset'),
            {'email': 'reset@lbwus.cl'},
            follow=True,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(mail.outbox)
        self.assertIn('recuperación de contraseña', mail.outbox[0].subject.lower())
        self.assertIn(reverse('password_reset_done'), respuesta.request['PATH_INFO'])
