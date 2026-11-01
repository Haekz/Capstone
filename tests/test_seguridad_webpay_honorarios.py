"""Pagos Webpay Plus: estrategia de credenciales, honorarios y modo simulacion.

SCRUM-85 (31-10-2026): las pruebas 01 a 07 eran del carrito antiguo (`iniciar_webpay`,
"Plan Basico $89.990" y registro `Pago`), que ya no existe: la unica compra es
`comprar_paquete` -> `PaqueteClases`. Se quitaron porque el flujo nuevo ya las cubre:

| Antes | Criterio | Equivalente en el flujo de paquetes |
|---|---|---|
| 01, 02 | monto calculado en el servidor | test_paquetes.CompraTests: test_cobra_el_precio_del_servidor_para_cada_paquete, test_el_precio_enviado_por_el_cliente_se_ignora |
| 03 | buy_order cruzada | test_paquetes.CriteriosSaldosScrum85Tests.test_orden_desconocida_no_activa_ningun_paquete |
| 04 | monto autorizado distinto | test_paquetes.CompraTests.test_monto_autorizado_distinto_al_del_paquete_se_rechaza |
| 05 | replay / idempotencia | Parcial: test_paquetes.CompraTests.test_pago_rechazado_no_da_clases_y_repetir_el_token_no_duplica y test_flujos_funcionales test_08 (no activa dos veces). `confirmacion` vuelve a llamar a commit() en cada retorno; la 05 exigia que no |
| 06 | rechazo de la pasarela | test_paquetes.CompraTests.test_pago_rechazado_no_da_clases_y_repetir_el_token_no_duplica |
| 07 | anulacion con TBK_TOKEN | Parcial: test_flujos_funcionales test_07 y test_paquetes.CriteriosSaldosScrum85Tests.test_compra_anulada_deja_el_paquete_pendiente_y_sin_uso. No hay estado 'anulada': el paquete queda pendiente (no se puede usar) |

Siguen abiertas, sin tocar, porque no son solo pruebas desactualizadas (ver .ia/reportes/sprint4_tareas.md):
- 08: honorarios por `Inscripcion.pago`, campo que esta en la migracion 0007 pero no en el modelo.
- 09: modo simulacion para testers; `WEBPAY_SIMULACION_ACTIVADA` existe en settings pero el flujo de paquetes no lo usa.
"""

import json

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from alumnos.models import Alumno, Asignatura, Clase, Genero, Especialidad, Inscripcion, Pago, SolicitudRetiro
from user_profesor.views import calcular_saldos, VALOR_INSCRIPCION, PAGO_PROFESOR
from alumnos.models import Profesor

User = get_user_model()


class HonorariosYSimulacionTests(TestCase):
    """Pendientes de decision: ver el docstring del modulo."""

    def setUp(self):
        self.client = Client()
        self.url_iniciar = reverse('comprar_paquete')
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

        resp = self.client.post(reverse('iniciar_webpay'), {
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


class EstrategiaCredencialesTransbankTests(SimpleTestCase):
    """Salvaguarda de cobros reales (S-08 / 7.6): vale igual para el flujo de paquetes."""

    def test_10_estrategia_credenciales_salvaguarda_modo_test_por_defecto(self):
        """Por defecto _tx() opera forzosamente en IntegrationType.TEST (Sandbox oficial Transbank), sin cobros reales."""
        from alumnos.views import _tx
        from transbank.common.integration_type import IntegrationType
        from transbank.common.integration_commerce_codes import IntegrationCommerceCodes

        with self.settings(TRANSBANK_PRODUCCION_HABILITADA=False):
            tx = _tx()
            self.assertEqual(tx.options.integration_type, IntegrationType.TEST)
            self.assertEqual(tx.options.commerce_code, IntegrationCommerceCodes.WEBPAY_PLUS)

    def test_11_salvaguarda_impide_cobro_real_si_produccion_no_esta_autorizada(self):
        """Aunque existan credenciales ficticias de producción, si TRANSBANK_PRODUCCION_HABILITADA es False, no se activa LIVE."""
        from alumnos.views import _tx
        from transbank.common.integration_type import IntegrationType
        from transbank.common.integration_commerce_codes import IntegrationCommerceCodes

        with self.settings(
            TRANSBANK_PRODUCCION_HABILITADA=False,
            TRANSBANK_ENVIRONMENT='LIVE',
            TRANSBANK_COMMERCE_CODE='597012345678',
            TRANSBANK_API_KEY='api_key_secreta_real'
        ):
            tx = _tx()
            # La salvaguarda bloquea LIVE y fuerza TEST
            self.assertEqual(tx.options.integration_type, IntegrationType.TEST)
            self.assertEqual(tx.options.commerce_code, IntegrationCommerceCodes.WEBPAY_PLUS)

    def test_12_estrategia_permite_produccion_solo_con_autorizacion_y_credenciales(self):
        """Solo con autorización explícita (TRANSBANK_PRODUCCION_HABILITADA=True) y credenciales LIVE se inicializa el comercio productivo."""
        from alumnos.views import _tx
        from transbank.common.integration_type import IntegrationType

        with self.settings(
            TRANSBANK_PRODUCCION_HABILITADA=True,
            TRANSBANK_ENVIRONMENT='LIVE',
            TRANSBANK_COMMERCE_CODE='597012345678',
            TRANSBANK_API_KEY='api_key_secreta_real'
        ):
            tx = _tx()
            self.assertEqual(tx.options.integration_type, IntegrationType.LIVE)
            self.assertEqual(tx.options.commerce_code, '597012345678')
