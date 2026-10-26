"""Pruebas de Seguridad de Pago Webpay Plus, Modo Simulación y Remuneración Docente.

Cubre los criterios de aceptación:
1. El monto se recalcula y valida en el servidor, no se confía en el navegador.
2. Las confirmaciones de Webpay comprueban orden, monto y token y evitan aplicación doble (Idempotencia).
3. La remuneración docente se basa únicamente en transacciones confirmadas.
4. Pruebas de manipulación de montos (tampering), callbacks repetidos (replay attacks) y pagos rechazados/anulados.
5. Modo de simulación de pago para usuarios de prueba / testers sin transacciones reales.
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from alumnos.models import Alumno, Asignatura, Clase, Genero, Especialidad, Inscripcion, Pago, SolicitudRetiro
from user_profesor.views import calcular_saldos, VALOR_INSCRIPCION, PAGO_PROFESOR
from alumnos.models import Profesor

User = get_user_model()


class SeguridadWebpayYHonorariosTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url_iniciar = reverse('iniciar_webpay')
        self.url_confirmacion = reverse('confirmacion')
        self.url_planes = reverse('planes')

        self.genero = Genero.objects.create(descripcion='Otro')
        self.especialidad = Especialidad.objects.create(nombre='Matemáticas')

        # Alumno
        self.u_alumno = User.objects.create_user(
            username='11111111-1',
            rut='11111111-1',
            password='Password123!',
            rol='alumno',
            first_name='AlumnoTest'
        )
        self.alumno = Alumno.objects.create(user=self.u_alumno, nivel_educacion='media')

        # Profesor
        self.u_profesor = User.objects.create_user(
            username='22222222-2',
            rut='22222222-2',
            password='ProfPassword123!',
            rol='profesor',
            first_name='ProfesorTest'
        )
        self.profesor = Profesor.objects.create(user=self.u_profesor, especialidad=self.especialidad)

        # Clase
        self.asignatura = Asignatura.objects.create(nombre='Álgebra Lineal')
        self.clase = Clase.objects.create(
            asignatura=self.asignatura,
            profesor=self.profesor,
            modalidad='online',
            horario='10:00:00'
        )

        self.carrito_oficial = [
            {
                'id': '1',
                'titulo': 'Plan Básico',
                'precio': '89990',
                'periodo': 'mensual',
                'cantidad': 1
            }
        ]
        self.carrito_json = json.dumps(self.carrito_oficial)

    # -------------------------------------------------------------------------
    # 1. VALIDACIÓN Y RECÁLCULO SERVER-SIDE (ZERO TRUST AL NAVEGADOR)
    # -------------------------------------------------------------------------
    @patch('alumnos.views._tx')
    def test_01_monto_se_recalcula_en_servidor_e_ignora_amount_post(self, mock_tx):
        """Si el cliente envía amount='1' o '350', el backend lo ignora y procesa el precio oficial ($89.990)."""
        instancia = MagicMock()
        instancia.create.return_value = {
            'url': 'https://webpay3gint.transbank.cl/test',
            'token': 'tok_seguro_001'
        }
        mock_tx.return_value = instancia

        resp = self.client.post(self.url_iniciar, {
            'carrito': self.carrito_json,
            'amount': '1'  # Intento de pagar $1
        })
        self.assertEqual(resp.status_code, 200)

        # Transbank debe recibir el monto oficial recalculado server-side ($89.990)
        args, _ = instancia.create.call_args
        monto_enviado_a_transbank = args[2]
        self.assertEqual(monto_enviado_a_transbank, 89990)

        # En BD el registro de Pago se crea con $89.990
        pago = Pago.objects.get(buy_order=args[0])
        self.assertEqual(pago.monto, 89990)
        self.assertEqual(pago.estado, Pago.ESTADO_INICIADA)

    def test_02_rechazo_carrito_monto_menor_al_minimo(self):
        """Carritos cuyo monto recalculado sea menor al mínimo de Transbank ($350) son rechazados."""
        carrito_irrisorio = json.dumps([{
            'id': 'custom_gratis',
            'titulo': 'Plan Gratuito',
            'precio': '100',
            'periodo': 'mensual',
            'cantidad': 1
        }])
        resp = self.client.post(self.url_iniciar, {
            'carrito': carrito_irrisorio,
            'amount': '100'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, self.url_planes)

    # -------------------------------------------------------------------------
    # 2. VALIDACIÓN CRUZADA EN CALLBACK (ORDEN, MONTO, TOKEN)
    # -------------------------------------------------------------------------
    @patch('alumnos.views._tx')
    def test_03_confirmacion_valida_buy_order_cruzada(self, mock_tx):
        """Si Transbank retorna un buy_order que no coincide con la orden registrada, se rechaza."""
        pago = Pago.objects.create(
            buy_order='LB1112223',
            session_id='S1112223',
            token_ws='tok_orden_cruzada',
            monto=89990,
            estado=Pago.ESTADO_INICIADA,
            detalle_carrito=self.carrito_oficial
        )

        session = self.client.session
        session['orden_pendiente'] = {
            'buy_order': pago.buy_order,
            'carrito': self.carrito_json,
            'pago_id': pago.id_pago,
            'amount': 89990
        }
        session.save()

        instancia = MagicMock()
        instancia.commit.return_value = {
            'response_code': 0,
            'status': 'AUTHORIZED',
            'buy_order': 'LB_ORDEN_FALSA_999',  # Orden discrepante
            'amount': 89990,
            'authorization_code': '123456',
            'card_detail': {'card_number': '6623'}
        }
        mock_tx.return_value = instancia

        resp = self.client.post(self.url_confirmacion, {'token_ws': 'tok_orden_cruzada'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['aprobado'])

        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.ESTADO_RECHAZADA)

    @patch('alumnos.views._tx')
    def test_04_confirmacion_valida_monto_cruzado(self, mock_tx):
        """Si Transbank retorna un monto diferente al que solicitó el servidor, se rechaza."""
        pago = Pago.objects.create(
            buy_order='LB3334445',
            session_id='S3334445',
            token_ws='tok_monto_discrepante',
            monto=89990,
            estado=Pago.ESTADO_INICIADA,
            detalle_carrito=self.carrito_oficial
        )

        instancia = MagicMock()
        instancia.commit.return_value = {
            'response_code': 0,
            'status': 'AUTHORIZED',
            'buy_order': pago.buy_order,
            'amount': 1000,  # Monto cobrado discrepante
            'authorization_code': '123456',
            'card_detail': {'card_number': '6623'}
        }
        mock_tx.return_value = instancia

        resp = self.client.post(self.url_confirmacion, {'token_ws': 'tok_monto_discrepante'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['aprobado'])

        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.ESTADO_RECHAZADA)

    # -------------------------------------------------------------------------
    # 3. IDEMPOTENCIA Y PREVENCIÓN DE REPLAY ATTACKS / DOBLE APLICACIÓN
    # -------------------------------------------------------------------------
    @patch('alumnos.views._tx')
    def test_05_confirmacion_idempotente_evita_doble_aplicacion_y_replay(self, mock_tx):
        """Si un callback ya fue procesado y aprobado, reintentos con el mismo token devuelven el voucher sin re-ejecutar commit."""
        pago = Pago.objects.create(
            buy_order='LB5556667',
            session_id='S5556667',
            token_ws='tok_idempotencia_777',
            monto=89990,
            estado=Pago.ESTADO_PAGADA,  # Ya pagado
            authorization_code='AUTH_OK_123',
            ultimos_digitos_tarjeta='6623',
            detalle_carrito=self.carrito_oficial
        )

        instancia = MagicMock()
        mock_tx.return_value = instancia

        # Re-envío del mismo token (ej. refrescar página o callback duplicado)
        resp = self.client.post(self.url_confirmacion, {'token_ws': 'tok_idempotencia_777'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['aprobado'])
        self.assertEqual(resp.context['orden'], 'LB5556667')
        self.assertEqual(resp.context['codigo_autorizacion'], 'AUTH_OK_123')

        # NO debe haberse llamado a commit() nuevamente en Transbank
        instancia.commit.assert_not_called()

    # -------------------------------------------------------------------------
    # 4. PAGOS RECHAZADOS Y ANULADOS
    # -------------------------------------------------------------------------
    @patch('alumnos.views._tx')
    def test_06_confirmacion_pago_rechazado_por_pasarela(self, mock_tx):
        """Transacción rechazada por el banco queda registrada como 'rechazada' en la base de datos."""
        pago = Pago.objects.create(
            buy_order='LB8889990',
            session_id='S8889990',
            token_ws='tok_rechazo_banco',
            monto=89990,
            estado=Pago.ESTADO_INICIADA
        )

        instancia = MagicMock()
        instancia.commit.return_value = {
            'response_code': -1,
            'status': 'FAILED',
            'buy_order': pago.buy_order,
            'amount': 89990
        }
        mock_tx.return_value = instancia

        resp = self.client.post(self.url_confirmacion, {'token_ws': 'tok_rechazo_banco'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['aprobado'])

        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.ESTADO_RECHAZADA)

    def test_07_confirmacion_pago_anulado_con_tbk_token(self):
        """Si el usuario cancela en la pasarela, se recibe TBK_TOKEN y la orden queda como 'anulada'."""
        pago = Pago.objects.create(
            buy_order='LB9990001',
            session_id='S9990001',
            token_ws='tok_anulacion_tbk',
            monto=89990,
            estado=Pago.ESTADO_INICIADA
        )

        resp = self.client.post(self.url_confirmacion, {'TBK_TOKEN': 'tok_anulacion_tbk'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['aprobado'])
        self.assertTrue(resp.context['anulado'])

        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.ESTADO_ANULADA)

    # -------------------------------------------------------------------------
    # 5. HONORARIOS DOCENTE BASADOS ÚNICAMENTE EN TRANSACCIONES CONFIRMADAS
    # -------------------------------------------------------------------------
    def test_08_remuneracion_docente_solo_con_transacciones_confirmadas(self):
        """calcular_saldos solo suma remuneración a inscripciones asociadas a un Pago en estado 'pagada'."""
        # 1. Sin inscripciones: saldo 0
        saldos = calcular_saldos(self.profesor)
        self.assertEqual(saldos['disponible'], 0)
        self.assertEqual(saldos['total_ganado'], 0)

        # 2. Inscripción sin pago (o pago pendiente): no debe sumar saldo docente
        inscripcion = Inscripcion.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            estado=Inscripcion.ESTADO_CONFIRMADA,
            pago=None
        )
        saldos_sin_pago = calcular_saldos(self.profesor)
        self.assertEqual(saldos_sin_pago['disponible'], 0)

        # 3. Inscripción con pago en estado 'iniciada' o 'rechazada': saldo sigue siendo 0
        pago_iniciado = Pago.objects.create(
            buy_order='LB_TEST_HON_1',
            monto=VALOR_INSCRIPCION,
            estado=Pago.ESTADO_INICIADA
        )
        inscripcion.pago = pago_iniciado
        inscripcion.save()

        saldos_iniciada = calcular_saldos(self.profesor)
        self.assertEqual(saldos_iniciada['disponible'], 0)

        # 4. Transacción confirmada (estado='pagada'): el profesor recibe su honorario ($12.000)
        pago_iniciado.estado = Pago.ESTADO_PAGADA
        pago_iniciado.save()

        saldos_pagado = calcular_saldos(self.profesor)
        self.assertEqual(saldos_pagado['total_ganado'], VALOR_INSCRIPCION)
        self.assertEqual(saldos_pagado['disponible'], PAGO_PROFESOR)

        # 5. Si el profesor solicita retiro por parte de su dinero disponible
        SolicitudRetiro.objects.create(
            profesor=self.profesor,
            monto=5000,
            estado='aprobado'
        )
        saldos_post_retiro = calcular_saldos(self.profesor)
        self.assertEqual(saldos_post_retiro['disponible'], PAGO_PROFESOR - 5000)

    # -------------------------------------------------------------------------
    # 6. MODO DE SIMULACIÓN DE PAGO PARA USUARIOS DE PRUEBA / TESTERS
    # -------------------------------------------------------------------------
    def test_09_modo_simulacion_de_pago_para_testers(self):
        """Un tester puede simular una transacción aprobada sin contactar a Transbank ni usar dinero real."""
        self.client.force_login(self.u_alumno)

        resp = self.client.post(self.url_iniciar, {
            'carrito': self.carrito_json,
            'simular': '1'  # Flag de simulación
        })

        # Redirige a confirmación con el token simulado
        self.assertEqual(resp.status_code, 302)
        self.assertIn('confirmacion', resp.url)
        self.assertIn('token_ws=sim_', resp.url)

        # Seguir la redirección a confirmación
        resp_conf = self.client.get(resp.url)
        self.assertEqual(resp_conf.status_code, 200)
        self.assertTrue(resp_conf.context['aprobado'])

        # Verificar que el Pago en base de datos quedó como pagado y marcado como simulación
        pago = Pago.objects.filter(es_simulacion=True).latest('created_at')
        self.assertEqual(pago.estado, Pago.ESTADO_PAGADA)
        self.assertEqual(pago.monto, 89990)
        self.assertEqual(pago.alumno, self.alumno)
        self.assertTrue(pago.buy_order.startswith('LB-SIM-'))
