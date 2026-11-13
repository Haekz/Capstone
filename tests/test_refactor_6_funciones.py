"""Pruebas de regresión y verificación funcional para las 6 funciones refactorizadas:

1. alumnos.views.confirmacion
2. user_profesor.views.calcular_saldos
3. user_profesor.views.panel_profesor
4. alumnos.views.custom_login
5. user_profesor.views.regis_tutor
6. alumnos.views.iniciar_webpay
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from alumnos.models import (
    Alumno,
    Asignatura,
    Banco,
    Clase,
    Especialidad,
    Genero,
    Inscripcion,
    Pago,
    PaqueteClases,
    PlanAlumno,
    Profesor,
    SolicitudRetiro,
    Tutor,
)
from alumnos.roles import ADMIN, PROFESOR, abrir_sesion_rol
from user_profesor.views import calcular_saldos

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
            horario='10:00:00',
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


class RefactorConfirmacionTests(BaseRefactorTestCase):
    """Punto 1: alumnos.views.confirmacion."""

    def test_confirmacion_sin_tokens_redirige_a_planes(self):
        resp = self.client.get(reverse('confirmacion'))
        self.assertRedirects(resp, reverse('planes'), fetch_redirect_response=False)

    def test_confirmacion_con_tbk_token_anula_pago(self):
        pago = Pago.objects.create(
            buy_order='LB-TBK-1',
            session_id='S-TBK-1',
            token_ws='tok_tbk_1',
            monto=15000,
            estado=Pago.ESTADO_INICIADA,
            usuario=self.u_alumno,
            alumno=self.alumno,
        )
        resp = self.client.post(reverse('confirmacion'), {'TBK_TOKEN': 'tok_tbk_1'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['anulado'])
        self.assertFalse(resp.context['aprobado'])
        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.ESTADO_ANULADA)

    @patch('alumnos.views._tx')
    def test_confirmacion_idempotente_si_ya_pagado_no_llama_commit(self, mock_tx):
        Pago.objects.create(
            buy_order='LB-PAG-1',
            session_id='S-PAG-1',
            token_ws='tok_pagado',
            monto=59000,
            estado=Pago.ESTADO_PAGADA,
            authorization_code='999111',
            ultimos_digitos_tarjeta='1234',
            fecha_transaccion=timezone.now(),
        )
        resp = self.client.get(reverse('confirmacion'), {'token_ws': 'tok_pagado'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['aprobado'])
        self.assertEqual(resp.context['codigo_autorizacion'], '999111')
        mock_tx.return_value.commit.assert_not_called()

    @patch('alumnos.views._tx')
    def test_confirmacion_aprobada_por_transbank_activa_paquete_y_pago(self, mock_tx):
        pago = Pago.objects.create(
            buy_order='LB-OK-1',
            session_id='S-OK-1',
            token_ws='tok_ok_1',
            monto=59000,
            estado=Pago.ESTADO_INICIADA,
            usuario=self.u_alumno,
            alumno=self.alumno,
        )
        paquete = PaqueteClases.objects.create(
            alumno=self.alumno,
            profesor=self.profesor,
            plan='progreso',
            clases=4,
            tarifa=15000,
            monto=59000,
            dias=30,
            buy_order='LB-OK-1',
        )
        mock_tx.return_value.commit.return_value = {
            'response_code': 0,
            'status': 'AUTHORIZED',
            'buy_order': 'LB-OK-1',
            'amount': 59000,
            'authorization_code': '654321',
            'card_detail': {'card_number': '4321'},
            'transaction_date': '2026-11-12T22:00:00Z',
        }

        resp = self.client.post(reverse('confirmacion'), {'token_ws': 'tok_ok_1'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['aprobado'])
        self.assertEqual(resp.context['tarjeta'], '4321')
        self.assertEqual(len(resp.context['items']), 1)

        pago.refresh_from_db()
        paquete.refresh_from_db()
        self.assertEqual(pago.estado, Pago.ESTADO_PAGADA)
        self.assertEqual(paquete.estado, PaqueteClases.ESTADO_ACTIVA)

    @patch('alumnos.views._tx')
    def test_confirmacion_error_transbank_marca_rechazada(self, mock_tx):
        pago = Pago.objects.create(
            buy_order='LB-ERR-1',
            session_id='S-ERR-1',
            token_ws='tok_err_1',
            monto=15000,
            estado=Pago.ESTADO_INICIADA,
        )
        mock_tx.return_value.commit.side_effect = RuntimeError('timeout')

        resp = self.client.get(reverse('confirmacion'), {'token_ws': 'tok_err_1'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['aprobado'])
        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.ESTADO_RECHAZADA)


class RefactorCalcularSaldosTests(BaseRefactorTestCase):
    """Punto 2: user_profesor.views.calcular_saldos."""

    def test_calcular_saldos_inscripciones_planes_y_retiros(self):
        # 1 inscripción confirmada sin paquete => 15.000 ganado, 12.750 tutor
        Inscripcion.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            estado=Inscripcion.ESTADO_CONFIRMADA,
        )
        # 1 PlanAlumno pagado de 4 clases con 2 consumidas => 59.000 ganado, 50.150 tutor (25.075 consumido, 25.075 pendiente)
        pago = Pago.objects.create(
            buy_order='LB-SALDO-1',
            session_id='S-SALDO-1',
            token_ws='tok_saldo_1',
            monto=59000,
            estado=Pago.ESTADO_PAGADA,
            usuario=self.u_alumno,
            alumno=self.alumno,
        )
        PlanAlumno.objects.create(
            alumno=self.alumno,
            profesor=self.profesor,
            tipo_plan=PlanAlumno.PLAN_PROGRESO,
            total_clases=4,
            clases_disponibles=2,
            clases_consumidas=2,
            monto_total=59000,
            comision_lbwus=8850,
            monto_tutor=50150,
            pago=pago,
            estado=PlanAlumno.ESTADO_ACTIVO,
        )
        banco = Banco.objects.create(nombre='Banco Estado')
        retiro_aprobado = SolicitudRetiro.objects.create(
            profesor=self.profesor,
            monto=10000,
            banco=banco,
            tipo_cuenta='Vista',
            numero_cuenta='12345',
            estado='aprobado',
        )
        retiro_pendiente = SolicitudRetiro.objects.create(
            profesor=self.profesor,
            monto=5000,
            banco=banco,
            tipo_cuenta='Vista',
            numero_cuenta='12345',
            estado='pendiente',
        )

        saldos_db = calcular_saldos(self.profesor)
        saldos_lista = calcular_saldos(self.profesor, retiros_lista=[retiro_aprobado, retiro_pendiente])

        self.assertEqual(saldos_db, saldos_lista)
        # total_ganado = 15.000 + 59.000 = 74.000
        self.assertEqual(saldos_db['total_ganado'], 74000)
        # bruto_tutor_acumulado = 12.750 + 25.075 = 37.825; disponible = 37.825 - 10.000 - 5.000 = 22.825
        self.assertEqual(saldos_db['disponible'], 22825)
        # comision = 74.000 - (37.825 + 25.075) = 11.100; pendiente = 11.100 + 25.075 + 5.000 = 41.175
        self.assertEqual(saldos_db['pendiente'], 41175)


class RefactorPanelProfesorTests(BaseRefactorTestCase):
    """Punto 3: user_profesor.views.panel_profesor."""

    def test_panel_profesor_anonimo_redirige(self):
        resp = self.client.get(reverse('panel_profesor'))
        self.assertEqual(resp.status_code, 302)

    def test_panel_profesor_carga_metricas_clases_y_saldos(self):
        Inscripcion.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            estado=Inscripcion.ESTADO_CONFIRMADA,
        )
        self._login_profesor()
        resp = self.client.get(reverse('panel_profesor'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['clases_hoy']), 1)
        self.assertEqual(resp.context['clases_hoy'][0]['alumno'], 'Ana')
        self.assertEqual(resp.context['clases_disponibles'], 7)
        self.assertEqual(len(resp.context['rendimiento_meses']), 5)
        self.assertEqual(resp.context['saldo_disponible_raw'], 12750)
        self.assertEqual(resp.context['dinero_hoy'], '$12.750')


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


class RefactorIniciarWebpayTests(BaseRefactorTestCase):
    """Punto 6: alumnos.views.iniciar_webpay."""

    def test_get_o_carrito_invalido_redirige_a_planes(self):
        self.assertRedirects(self.client.get(reverse('iniciar_webpay')), reverse('planes'), fetch_redirect_response=False)
        self.assertRedirects(
            self.client.post(reverse('iniciar_webpay'), {'carrito': '[]'}),
            reverse('planes'),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.post(reverse('iniciar_webpay'), {'carrito': json.dumps([{'id': 'x', 'precio': '100'}])}),
            reverse('planes'),
            fetch_redirect_response=False,
        )

    @override_settings(WEBPAY_SIMULACION_ACTIVADA=True, USUARIOS_SIMULACION_WEBPAY=['*'])
    def test_iniciar_webpay_simulado_crea_pago_y_redirige(self):
        self.client.force_login(self.u_alumno)
        carrito = [{'id': 'flexible', 'titulo': 'Plan Flexible', 'cantidad': 1}]
        resp = self.client.post(reverse('iniciar_webpay'), {
            'carrito': json.dumps(carrito),
            'simular': '1',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('confirmacion'), resp.url)
        pago = Pago.objects.get(es_simulacion=True)
        self.assertEqual(pago.monto, 15000)
        self.assertEqual(pago.estado, Pago.ESTADO_PAGADA)
        self.assertEqual(self.client.session['orden_pendiente']['pago_id'], pago.id_pago)

    @patch('alumnos.views._tx')
    def test_iniciar_webpay_real_y_falla_pasarela(self, mock_tx):
        mock_tx.return_value.create.return_value = {
            'url': 'https://webpay.test/init',
            'token': 'tok_real_1',
        }
        carrito = [{'id': 'progreso', 'titulo': 'Plan Progreso', 'cantidad': 1}]
        resp = self.client.post(reverse('iniciar_webpay'), {'carrito': json.dumps(carrito)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['token'], 'tok_real_1')
        self.assertEqual(Pago.objects.get(token_ws='tok_real_1').monto, 59000)

        mock_tx.return_value.create.side_effect = RuntimeError('pasarela caída')
        resp_err = self.client.post(reverse('iniciar_webpay'), {'carrito': json.dumps(carrito)})
        self.assertRedirects(resp_err, reverse('planes'), fetch_redirect_response=False)
        self.assertEqual(Pago.objects.filter(estado=Pago.ESTADO_RECHAZADA).count(), 1)
