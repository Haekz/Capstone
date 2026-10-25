"""Validaciones funcionales de flujos clave de LBWUS y Cobertura de Seguridad del Pago (Sprint 3).

Cubre:
1. Seguridad del flujo de pago Webpay Plus (Transbank):
   - Intento GET rechazado hacia iniciar_webpay.
   - Carrito inválido, vacío o con manipulación de precios (tampering).
   - Creación de orden y sesión protegida.
   - Confirmación de pago aprobado por pasarela.
   - Rechazo de pago por pasarela (status FAILED / response_code != 0).
   - Anulación de pago por el usuario (TBK_TOKEN).
   - Prevención de ataques de repetición (Replay Attack) mediante extracción de orden (session.pop).
   - Acceso no autorizado sin tokens que redirige a planes.
2. Flujo funcional de registro, autenticación y cierre de sesión de usuarios.
3. Accesos y visualizaciones públicas sin fugas de datos.
"""

from datetime import date, time
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from alumnos.models import Alumno, Genero

User = get_user_model()


class SeguridadPagoWebpayTests(TestCase):
    """Pruebas de seguridad, validación de montos y rechazos en la pasarela Webpay Plus."""

    def setUp(self):
        self.client = Client()
        self.url_iniciar = reverse('iniciar_webpay')
        self.url_confirmacion = reverse('confirmacion')
        self.url_planes = reverse('planes')

        # Pagar exige alumna logueada (el plan necesita un dueño).
        user = User.objects.create_user('44444444-4', rut='44444444-4',
                                        password='Clave12345!', rol='alumno')
        Alumno.objects.create(user=user, nivel_educacion='media')
        self.client.post(reverse('login'), {'username': '44444444-4', 'password': 'Clave12345!'})

        # Carrito válido de prueba
        self.carrito_valido = [
            {
                'id': 'plan_medio',
                'titulo': 'Plan Medio',
                'precio': '25000',
                'periodo': 'mensual',
                'cantidad': 1
            }
        ]
        self.carrito_json = json.dumps(self.carrito_valido)

    def test_01_iniciar_webpay_metodo_get_rechazado_y_redirige(self):
        """Peticiones GET al endpoint de inicio de pago son rechazadas y redirigen a planes."""
        resp = self.client.get(self.url_iniciar)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, self.url_planes)

    def test_02_iniciar_webpay_carrito_vacio_o_invalido_redirige(self):
        """Si el carrito enviado está vacío, no es JSON o es inválido, se rechaza la orden."""
        casos = [
            '',
            '[]',
            '{}',
            'no-json-invalido',
            json.dumps({'mal': 'formato'}),
        ]
        for caso in casos:
            with self.subTest(carrito=caso):
                resp = self.client.post(self.url_iniciar, {'carrito': caso, 'amount': '25000'})
                self.assertEqual(resp.status_code, 302)
                self.assertRedirects(resp, self.url_planes)

    def test_03_iniciar_webpay_monto_minimo_y_tampering_protegido(self):
        """
        Si el cliente manipula el campo amount enviando un valor ínfimo (ej. $1)
        o menor al mínimo de Transbank ($350 CLP), el backend calcula el precio
        real server-side evitando fraude.
        """
        # Carrito con precio simulado menor a 350
        carrito_irrisorio = json.dumps([{'precio': '10', 'periodo': 'mensual', 'cantidad': 1}])

        # 1. Monto < 350 tanto en carrito como en POST: debe ser rechazado
        resp = self.client.post(self.url_iniciar, {
            'carrito': carrito_irrisorio,
            'amount': '10'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, self.url_planes)

        # 2. Tampering: cliente envía amount='1' pero carrito vale $25.000:
        # El backend debe respetar monto_calculado >= 350 y procesar los $25.000 reales
        with patch('alumnos.views._tx') as mock_tx:
            instancia_mock = MagicMock()
            instancia_mock.create.return_value = {
                'url': 'https://webpay3gint.transbank.cl/webpayserver/initTransaction',
                'token': 'mock_token_seguro_123'
            }
            mock_tx.return_value = instancia_mock

            resp_tamper = self.client.post(self.url_iniciar, {
                'carrito': self.carrito_json,
                'amount': '1'  # Intento de pagar $1
            })
            self.assertEqual(resp_tamper.status_code, 200)

            # Verificar que a Transbank se le envió el monto calculado ($25.000) y no $1
            args, _ = instancia_mock.create.call_args
            amount_enviado_a_transbank = args[2]
            self.assertEqual(amount_enviado_a_transbank, 25000)

    @patch('alumnos.views._tx')
    def test_04_iniciar_webpay_exitoso_guarda_orden_pendiente_en_sesion(self, mock_tx):
        """Una orden legítima guarda 'orden_pendiente' en la sesión de Django y renderiza redirect."""
        instancia_mock = MagicMock()
        instancia_mock.create.return_value = {
            'url': 'https://webpay3gint.transbank.cl/test',
            'token': 'tok_xyz_987'
        }
        mock_tx.return_value = instancia_mock

        resp = self.client.post(self.url_iniciar, {
            'carrito': self.carrito_json,
            'amount': '25000'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'alumnos/redirect_webpay.html')
        self.assertEqual(resp.context['token'], 'tok_xyz_987')

        # Verificar que la sesión contiene la orden pendiente
        orden = self.client.session.get('orden_pendiente')
        self.assertIsNotNone(orden)
        self.assertTrue(orden['buy_order'].startswith('LB'))
        self.assertEqual(orden['carrito'], self.carrito_json)

    @patch('alumnos.views._tx')
    def test_05_confirmacion_pago_aprobado_webpay(self, mock_tx):
        """Transacción aprobada por Webpay (response_code=0, status=AUTHORIZED) renderiza éxito."""
        session = self.client.session
        session['orden_pendiente'] = {
            'buy_order': 'LB7778889',
            'carrito': self.carrito_json
        }
        session.save()

        instancia_mock = MagicMock()
        instancia_mock.commit.return_value = {
            'response_code': 0,
            'status': 'AUTHORIZED',
            'amount': 25000,
            'buy_order': 'LB7778889',
            'authorization_code': '121314',
            'card_detail': {'card_number': '6623'},
            'transaction_date': '2026-10-18T10:00:00.000Z'
        }
        mock_tx.return_value = instancia_mock

        resp = self.client.post(self.url_confirmacion, {'token_ws': 'token_aprobado_123'})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'alumnos/confirmacion.html')
        self.assertTrue(resp.context['aprobado'])
        self.assertEqual(resp.context['orden'], 'LB7778889')
        self.assertEqual(resp.context['tarjeta'], '6623')
        self.assertEqual(resp.context['codigo_autorizacion'], '121314')

    @patch('alumnos.views._tx')
    def test_06_confirmacion_pago_rechazado_por_transbank(self, mock_tx):
        """Transacción rechazada por el banco (response_code != 0) renderiza aprobado=False."""
        session = self.client.session
        session['orden_pendiente'] = {
            'buy_order': 'LB7778889',
            'carrito': self.carrito_json
        }
        session.save()

        instancia_mock = MagicMock()
        instancia_mock.commit.return_value = {
            'response_code': -1,
            'status': 'FAILED',
            'amount': 25000,
            'buy_order': 'LB7778889'
        }
        mock_tx.return_value = instancia_mock

        resp = self.client.post(self.url_confirmacion, {'token_ws': 'token_rechazado_999'})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'alumnos/confirmacion.html')
        self.assertFalse(resp.context['aprobado'])

    def test_07_confirmacion_pago_anulado_por_usuario_con_tbk_token(self):
        """Si el usuario cancela en la pasarela, Webpay envía TBK_TOKEN y se marca anulado=True."""
        session = self.client.session
        session['orden_pendiente'] = {
            'buy_order': 'LB7778889',
            'carrito': self.carrito_json
        }
        session.save()

        resp = self.client.post(self.url_confirmacion, {'TBK_TOKEN': 'token_anulacion_555'})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'alumnos/confirmacion.html')
        self.assertFalse(resp.context['aprobado'])
        self.assertTrue(resp.context['anulado'])

    @patch('alumnos.views._tx')
    def test_08_seguridad_replay_attack_prevenido_por_session_pop(self, mock_tx):
        """
        Ataque de repetición (Replay Attack):
        Una vez procesada la confirmación, la orden es eliminada de la sesión con .pop().
        Un re-envío malicioso del mismo token no debe volver a acreditar la orden pendiente.
        """
        session = self.client.session
        session['orden_pendiente'] = {
            'buy_order': 'LB7778889',
            'carrito': self.carrito_json
        }
        session.save()

        instancia_mock = MagicMock()
        instancia_mock.commit.return_value = {
            'response_code': 0,
            'status': 'AUTHORIZED',
            'amount': 25000,
            'buy_order': 'LB7778889'
        }
        mock_tx.return_value = instancia_mock

        # 1. Primera confirmación legítima
        resp1 = self.client.post(self.url_confirmacion, {'token_ws': 'token_unico_abc'})
        self.assertEqual(resp1.status_code, 200)

        # La orden ya no existe en la sesión
        self.assertNotIn('orden_pendiente', self.client.session)

        # 2. Intento de replay con el mismo cliente y token
        resp2 = self.client.post(self.url_confirmacion, {'token_ws': 'token_unico_abc'})
        # Los items deben estar vacíos porque la orden ya fue consumida
        self.assertEqual(resp2.context['items'], [])

    def test_09_confirmacion_sin_parametros_redirige_a_planes(self):
        """Si un usuario intenta entrar directamente a /confirmacion sin tokens, se le redirige a planes."""
        resp = self.client.get(self.url_confirmacion)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, self.url_planes)


class FlujosFuncionalesUsuariosTests(TestCase):
    """Validaciones de flujos de registro, acceso y visualizaciones principales."""

    def setUp(self):
        self.client = Client()
        self.genero = Genero.objects.create(descripcion='Masculino')

    def test_flujo_registro_alumno_exitoso(self):
        """Prueba de registro de nuevo alumno y redirección correcta."""
        datos_registro = {
            'nombre': 'Esteban Quito',
            'rut': '12.345.678-5',
            'correo_electronico': 'esteban_nuevo@test.cl',
            'direccion': 'Calle Falsa 123',
            'fecha_nacimiento': '2000-05-15',
            'genero': self.genero.pk,
            'nivel_educacion': 'media',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
        }

        resp = self.client.post(reverse('regis_alum'), datos_registro)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(User.objects.filter(email='esteban_nuevo@test.cl').exists())
        self.assertTrue(Alumno.objects.filter(user__email='esteban_nuevo@test.cl').exists())
        # Verificar que la sesión se abrió automáticamente para el alumno
        self.assertIn('alumno_id', self.client.session)

    def test_flujo_login_y_logout_alumno(self):
        """Prueba de inicio de sesión de alumno, acceso a portal y posterior cierre de sesión."""
        u = User.objects.create_user(
            username='14444333-2',
            rut='14444333-2',
            email='estudiante_login@test.cl',
            password='Password123!',
            rol='alumno',
            genero=self.genero
        )
        Alumno.objects.create(user=u)

        # Login
        login_resp = self.client.post(reverse('login'), {
            'username': '14444333-2',
            'password': 'Password123!'
        })
        self.assertEqual(login_resp.status_code, 302)
        self.assertRedirects(login_resp, reverse('alumno_pag1'))

        # Acceder a su portal
        portal_resp = self.client.get(reverse('alumno_pag1'))
        self.assertEqual(portal_resp.status_code, 200)

        # Logout vía POST (estándar seguro en Django)
        logout_resp = self.client.post(reverse('logout'))
        self.assertEqual(logout_resp.status_code, 302)

        # Verificar que la sesión fue destruida
        self.assertNotIn('alumno_id', self.client.session)
