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

Decididas al integrar fran-agenda (03-11-2026): un solo flujo de pagos, el de paquetes.
- 08: honorarios por `Inscripcion.pago`. El modelo `Pago` se retiro (migracion 0024); el saldo del
  profesor sale de clases dictadas de paquetes pagados: test_paquetes (test_reserva_futura_no_suma_saldo_hasta_dictarse,
  test_compra_anulada_deja_el_paquete_pendiente_y_sin_uso) y test_retiros.
- 09: modo simulacion para testers. Sigue pendiente: `WEBPAY_SIMULACION_ACTIVADA` existe en settings pero
  el flujo de paquetes no lo usa; mientras tanto se prueba con el sandbox de Transbank (prueba 10).
"""

from django.test import SimpleTestCase


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
