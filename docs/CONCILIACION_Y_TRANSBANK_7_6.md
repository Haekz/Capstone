# 💳 Documentación Técnica: Integración Transbank Webpay Plus y Conciliación Financiera (7.6)

Este documento detalla la resolución técnica, arquitectural y normativa del ítem **7.6 — Completar integración productiva de Transbank**, cumpliendo estrictamente con las auditorías **S-08, S-17 y F-09** y reutilizando los desarrollos de **SCRUM-88 (Sprint 4)**.

---

## 🔒 1. Salvaguarda Estricta: Prohibición de Cobros Reales

> [!IMPORTANT]
> **Orden de Operación:** En cumplimiento de las directrices académicas y de seguridad del proyecto Capstone, **está estrictamente prohibido procesar cobros reales con dinero de usuarios o tarjetas reales**. El sistema se encuentra configurado y blindado por defecto en entorno de **Integración / Sandbox oficial de Transbank** (tarjetas de prueba `6623`, código de comercio de integración `597055555532`).

---

## 🏛️ 2. Estrategia de Credenciales (Auditoría S-08)

### Arquitectura de Configuración (`lbwus/settings.py` y `alumnos/views.py`)
Para evitar la filtración de credenciales en el repositorio de código fuente y permitir la inyección segura de parámetros mediante variables de entorno, se definió la siguiente estrategia:

```python
# Variables leídas desde el entorno
TRANSBANK_PRODUCCION_HABILITADA = os.environ.get('TRANSBANK_PRODUCCION_HABILITADA', 'False').lower() in ('true', '1')
TRANSBANK_COMMERCE_CODE = os.environ.get('TRANSBANK_COMMERCE_CODE', '').strip()
TRANSBANK_API_KEY = os.environ.get('TRANSBANK_API_KEY', '').strip()
TRANSBANK_ENVIRONMENT = os.environ.get('TRANSBANK_ENVIRONMENT', 'TEST').upper()
```

### Mecanismo de Fallback y Candado de Seguridad (`_tx()`)
La función de conexión a la pasarela `_tx()` implementa un candado estricto:
1. **Bloqueo por Defecto:** Si `TRANSBANK_PRODUCCION_HABILITADA` es `False` (valor por defecto), el sistema **fuerza incondicionalmente** el modo `IntegrationType.TEST` utilizando los `IntegrationCommerceCodes.WEBPAY_PLUS` oficiales de Transbank.
2. **Protección Anti-Accidentes:** Aunque existan variables de entorno residuales o credenciales cargadas por error, si el flag de producción no está autorizado explícitamente, jamás se establecerá conexión productiva con dinero real.
3. **Modo Simulación Interno:** Se mantiene el flag `simular=1` (`WEBPAY_SIMULACION_ACTIVADA = True`) para que desarrolladores y testers validen el flujo de compra extremo a extremo sin interactuar con los servidores externos de Transbank.

---

## 🛡️ 3. Trazabilidad y Confirmación Fiable (Auditoría S-17 / SCRUM-88)

### Modelo de Datos de Auditoría (`Pago`)
Cada intención de pago crea un registro en el modelo `Pago` (`alumnos/models.py`) con los siguientes campos de trazabilidad:
- `buy_order`: Identificador único de orden (prefijo `LB-` o `LB-SIM-`).
- `session_id`: Identificador de sesión web del usuario.
- `token_ws`: Token unívoco emitido por Transbank (o token simulado).
- `monto`: Monto en CLP validado.
- `estado`: Estados controlados: `'iniciada'`, `'pagada'`, `'rechazada'`, `'anulada'`.
- `authorization_code`: Código de autorización emitido por el adquirente.
- `ultimos_digitos_tarjeta`: Enmascaramiento de tarjeta (e.g. `6623`).
- `es_simulacion`: Booleano que discrimina transacciones reales vs pruebas locales.
- `detalle_carrito`: Copia inmutable en formato JSON de los ítems adquiridos.

### Mitigación de Vulnerabilidades de Pago
1. **Zero Trust / Manipulación de Montos (*Price Tampering*):** El endpoint `iniciar_webpay` ignora el parámetro `amount` remitido desde el frontend; recalcula el total a cobrar directamente a partir del catálogo oficial del backend (`_precio_item`). Se rechaza cualquier carrito cuyo importe sea menor al mínimo regulado de Transbank ($350 CLP).
2. **Validación Cruzada en Callback (`confirmacion`):** Al retornar de la pasarela, el sistema valida que el `buy_order` y el `amount` reportados por Transbank en el `.commit()` coincidan de forma exacta con la orden guardada en la base de datos y en la sesión del cliente.
3. **Idempotencia y Prevención de Replay Attacks:** Si un callback ya fue procesado y su estado en base de datos es `pagada`, cualquier reintento (por refresco de pantalla o ataque de repetición) devuelve el comprobante sin volver a ejecutar el método `commit()`.
4. **Manejo de Transacciones Fallidas o Anuladas:** Si el usuario presiona "Anular y volver al comercio" en Webpay, se captura el parámetro `TBK_TOKEN` y se actualiza el estado a `anulada`. Si el banco rechaza la transacción (`response_code != 0`), el estado se registra como `rechazada`.

---

## 💼 4. Definición de Liquidación a Tutores y Conciliación Financiera (Auditoría F-09 / S4-09)

### Reglas Económicas Oficiales
- **Comisión de Plataforma LBWUS:** **15% IVA incluido** sobre el precio final pagado por el alumno.
- **Honorario Neto para el Tutor:** **85%** restante del valor final.
- **Tarifa Base de Referencia:** $15.000 CLP por clase individual.
  - *Plan Flexible (1 clase):* Total: $15.000 | LBWUS: $2.250 | Tutor: $12.750.
  - *Plan Progreso (4 clases):* Total: $59.000 | LBWUS: $8.850 | Tutor: $50.150.
  - *Plan Intensivo (8 clases):* Total: $116.000 | LBWUS: $17.400 | Tutor: $98.600.

### Desglose Impositivo y Contabilidad (`DesgloseOperacion`)
El modelo `DesgloseOperacion` registra de manera granular:
- `monto_bruto = comision_lbwus + monto_tutor`
- `comision_lbwus = neto_comision + iva_comision` (donde IVA es el 19% del neto de la comisión).

### Prevención de Fraude y Custodia Preventiva (`calcular_saldos`)
Para evitar retiros de dinero no devengado:
1. **Solo Clases Dictadas Liberan Saldo:** Las clases compradas mediante planes que aún no han sido reservadas o dictadas permanecen en estado **custodia/pendiente**.
2. **No Anticipos sin Ejecución:** El tutor no puede solicitar retiros sobre fondos de planes prepagados hasta que la sesión se confirme como realizada.
3. **Panel Administrativo:** El `dashboard_admin` monitorea en tiempo real las `comisiones_lbwus_totales` devengadas y los `fondos_en_custodia`.

---

## 📋 5. Requisitos para la Fase Productiva Real (Futuro Pase a Producción)

Para una eventual puesta en marcha comercial en el mundo real, los pasos externos y administrativos requeridos son:
1. **Constitución Legal:** Contar con personería jurídica comercial y RUT de empresa en Chile.
2. **Contrato de Afiliación:** Suscripción formal del contrato de comercio con Transbank S.A.
3. **Proceso de Homologación:** Ejecución de la pauta de pruebas de integración provista por Transbank (aprobaciones, rechazos, anulaciones, timeouts).
4. **Habilitación Técnica:** Inyección en las variables de entorno de producción del `TRANSBANK_COMMERCE_CODE` real, `TRANSBANK_API_KEY` real y habilitación de `TRANSBANK_PRODUCCION_HABILITADA=True`.
