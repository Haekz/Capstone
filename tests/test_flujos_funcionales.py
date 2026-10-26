"""Validaciones funcionales de flujos clave de LBWUS y Cobertura de Seguridad del Pago (Sprint 3).

Cubre:
1. Seguridad del flujo de pago Webpay Plus (Transbank):
   - (La compra y el price tampering de los paquetes: tests/test_paquetes.py.)
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

from alumnos.models import Alumno, Genero, PaqueteClases

User = get_user_model()


class SeguridadPagoWebpayTests(TestCase):
    """Pruebas de seguridad, validación de montos y rechazos en la pasarela Webpay Plus."""

    def setUp(self):
        self.client = Client()
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
    def test_08_seguridad_replay_attack_no_activa_dos_veces(self, mock_tx):
        """
        Ataque de repetición (Replay Attack): el pedido vive en la base, no en la sesión.
        Re-enviar el mismo token no vuelve a activar el paquete ni extiende su vigencia.
        """
        alumno = Alumno.objects.get(user__rut='44444444-4')
        PaqueteClases.objects.create(alumno=alumno, plan='flexible', clases=1, tarifa=15000,
                                     monto=15000, dias=30, buy_order='LB7778889')

        instancia_mock = MagicMock()
        instancia_mock.commit.return_value = {
            'response_code': 0,
            'status': 'AUTHORIZED',
            'amount': 15000,  # el monto del paquete: si no coincide, se rechaza
            'buy_order': 'LB7778889'
        }
        mock_tx.return_value = instancia_mock

        # 1. Primera confirmación legítima
        resp1 = self.client.post(self.url_confirmacion, {'token_ws': 'token_unico_abc'})
        self.assertEqual(resp1.status_code, 200)

        paquete = PaqueteClases.objects.get()
        self.assertEqual(paquete.estado, PaqueteClases.ESTADO_ACTIVA)
        vence = paquete.fecha_fin

        # 2. Intento de replay con el mismo cliente y token
        self.client.post(self.url_confirmacion, {'token_ws': 'token_unico_abc'})
        paquete.refresh_from_db()
        self.assertEqual(paquete.fecha_fin, vence)
        self.assertEqual(PaqueteClases.objects.vigentes().count(), 1)

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
