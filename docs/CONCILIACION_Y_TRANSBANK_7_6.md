# Documentación Técnica: Integración Transbank Webpay Plus y Conciliación Financiera (7.6)

Este documento detalla la resolución técnica, arquitectural y normativa del ítem **7.6 — Completar integración productiva de Transbank**, cumpliendo con las auditorías **S-08, S-17 y F-09** y reutilizando los desarrollos de **SCRUM-88 (Sprint 4)**.

> **Estado del documento (08-nov-2026):** las secciones 3 y 4 describían el carrito antiguo (modelo `Pago`, `iniciar_webpay`, `DesgloseOperacion`), que ya no existe. Se reescribieron con el flujo vigente: la única compra es `comprar_paquete` → `PaqueteClases`.

---

## 1. Salvaguarda Estricta: Prohibición de Cobros Reales

> [!IMPORTANT]
> **Orden de Operación:** En cumplimiento de las directrices académicas y de seguridad del proyecto Capstone, **está estrictamente prohibido procesar cobros reales con dinero de usuarios o tarjetas reales**. El sistema se encuentra configurado y blindado por defecto en entorno de **Integración / Sandbox oficial de Transbank** (tarjetas de prueba `6623`, código de comercio de integración `597055555532`).

---

## 2. Estrategia de Credenciales (Auditoría S-08)

### Arquitectura de Configuración (`lbwus/settings.py` y `alumnos/webpay.py`)
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
3. **Simulación = ambiente de integración:** la simulación es el sandbox oficial de Transbank (tarjetas de prueba, sin cobros reales). No hay un flag de simulación aparte: se retiró `WEBPAY_SIMULACION_ACTIVADA` porque ningún flujo la usaba.
4. **Falla ruidosa:** con `TRANSBANK_PRODUCCION_HABILITADA=True`, si falta `LIVE`, el código de comercio o la llave, el sitio no arranca (`ImproperlyConfigured`). Antes volvía en silencio al ambiente de pruebas y aceptaba tarjetas de prueba como si fueran pagos.

---

## 3. Trazabilidad y Confirmación Fiable (Auditoría S-17 / SCRUM-88)

### Registro de cada compra (`PaqueteClases`, `alumnos/models/pagos.py`)
Cada compra iniciada crea un `PaqueteClases` **pendiente**. Solo pasa a activo cuando Transbank aprueba. Campos de trazabilidad:
- `buy_order`: orden única, `PQ` + 24 caracteres al azar (26 en total, el máximo de Transbank). Se busca por orden y no por sesión: Webpay puede volver sin la cookie.
- `token_ws`: token que entrega Transbank al iniciar. Sirve para preguntarle el estado a Transbank si el alumno no vuelve.
- `monto`, `plan`, `clases`, `tarifa`, `dias`: quedan fijos al comprar; si el profesor cambia su tarifa, lo ya vendido no cambia.
- `estado`: `pendiente`, `activa` o `rechazada`.
- `codigo_autorizacion` y `fecha_pago`: los entrega Transbank al aprobar. **No se guardan los dígitos de la tarjeta.**
- `creada` y `fecha_fin` (vigencia).

No existen `es_simulacion` ni `detalle_carrito`: el ambiente (prueba o real) lo define la configuración, y cada compra es un solo paquete. El `session_id` que pide Transbank se genera al iniciar (`S` + 16 caracteres) y no se guarda.

### Mitigación de Vulnerabilidades de Pago
1. **Zero Trust / Manipulación de Montos (*Price Tampering*):** `comprar_paquete` ignora cualquier monto, precio o cantidad de clases que llegue del navegador. Recalcula el precio en el servidor con `alumnos/paquetes.py` (plan + tarifa del profesor), única fuente de precios.
2. **Validación Cruzada en Callback (`confirmacion` → `registrar_respuesta`):** se aprueba solo con `response_code == 0`, `status == 'AUTHORIZED'` **y** `amount` igual al monto del paquete de esa orden. Una orden desconocida no activa nada.
3. **Idempotencia y Replay:** solo se tocan paquetes pendientes. Un retorno repetido llama de nuevo a `commit()` (Transbank lo rechaza), pero no cambia lo ya resuelto: un rechazado no se reactiva, un activo no extiende su vigencia ni pisa su código de autorización.
4. **Anulaciones y retornos inválidos:** si llega `TBK_TOKEN` (el alumno anuló en Webpay) se muestra "Pago Anulado", no se llama a `commit()` y el paquete queda pendiente: **no hay estado `anulada`**. Si llegan `token_ws` y `TBK_TOKEN` juntos (formulario inválido) tampoco se confirma, como indica la guía de Transbank.
5. **Pagos que no volvieron (`manage.py revisar_pagos_pendientes`, tarea diaria):** a los pendientes de más de 1 hora se les pregunta el estado a Transbank con su `token_ws`. Si estaban pagados se activan con la misma regla del punto 2; si fueron abandonados o fallaron quedan rechazados. Si Transbank no responde, siguen pendientes.

---

## 4. Definición de Liquidación a Profesores y Conciliación Financiera (Auditoría F-09 / S4-09)

### Reglas Económicas Oficiales (`alumnos/paquetes.py`)
- **Comisión de Plataforma LBWUS:** **15 % IVA incluido** sobre lo pagado por el alumno. El IVA contenido (19 %) se calcula con `iva_incluido()`.
- **Pago al profesor:** el **85 %** restante (`pago_profesor()`).
- **Tarifa por clase:** la fija cada profesor entre $10.000 y $50.000, de a $1.000. La tarifa base de referencia es $15.000.
- **Precio del paquete:** clases × tarifa con el descuento del plan, redondeado a $1.000. Con la tarifa base:

| Plan | Clases | Vigencia | Total | LBWUS (15 %) | Profesor (85 %) |
|---|---|---|---|---|---|
| Flexible | 1 | 30 días | $15.000 | $2.250 | $12.750 |
| Progreso | 4 | 60 días | $59.000 | $8.850 | $50.150 |
| Intensivo | 8 | 90 días | $116.000 | $17.400 | $98.600 |

No hay tabla de desglose (`DesgloseOperacion` no existe): comisión, IVA y pago al profesor se calculan cada vez con las funciones de `alumnos/paquetes.py`, para tener una sola fuente.

### Prevención de Fraude y Custodia Preventiva (`user_profesor/saldos.py`)
1. **Solo clases dictadas liberan saldo:** lo cobrado por clases que aún no se dictan queda en custodia. Una reserva futura todavía se puede cancelar.
2. **Excepción acordada (02-nov):** si el alumno cancela con menos de 4 horas, la clase se le paga igual al profesor.
3. **Saldos del profesor** (`calcular_saldos`): `total_ganado`, `disponible` (su 85 % menos retiros aprobados, pagados y en trámite) y `pendiente` (comisión de la plataforma más lo que está en trámite).
4. **Retiros:** mínimo de $10.000 (`liquidacion.MINIMO`); el saldo se acumula hasta alcanzarlo.
5. **Panel del admin** (`admin_portal/metricas.finanzas`): `cobrado`, `comision_estimada`, `ganancia` (comisión de las clases ya dictadas), `por_dictar`, `saldo_profesores`, `retiros_pagados` y `retiros_pendientes`.

---

## 5. Requisitos para la Fase Productiva Real (Futuro Pase a Producción)

Para una eventual puesta en marcha comercial en el mundo real, los pasos externos y administrativos requeridos son:
1. **Constitución Legal:** Contar con personería jurídica comercial y RUT de empresa en Chile.
2. **Contrato de Afiliación:** Suscripción formal del contrato de comercio con Transbank S.A.
3. **Proceso de Homologación:** Ejecución de la pauta de pruebas de integración provista por Transbank (aprobaciones, rechazos, anulaciones, timeouts). Ver la sección 6.
4. **Habilitación Técnica:** Cargar en las variables de entorno de producción las cuatro variables de la sección 2 (`TRANSBANK_PRODUCCION_HABILITADA=True`, `TRANSBANK_ENVIRONMENT=LIVE`, `TRANSBANK_COMMERCE_CODE` y `TRANSBANK_API_KEY` reales). No hay que tocar código.

---

## 6. Checklist de validación con Transbank

> **Cómo leerla:** la armé a partir de la documentación pública de Transbank que conozco, y está **sin confirmar contra la guía vigente** que entregue Transbank con el contrato. Las exigencias pueden cambiar: hay que cotejarla con esa guía antes de enviar nada. La columna "Hoy" describe el estado del código en `main` más la rama `fran-transbank-produccion`. Estados: **Cumple**, **Parcial**, **Falta** y **Pendiente** (depende de una persona o de una decisión).

### A. Comportamiento del flujo (pauta de pruebas en integración)
Se ejecuta a mano en el ambiente de integración, guardando capturas de cada caso. Tarjetas de prueba según la documentación pública (confirmar vigencia): VISA `4051 8856 0044 6623` (aprobada), Mastercard `5186 0595 5959 0568` (rechazada); CVV `123`; en el formulario del banco, RUT `11.111.111-1` y clave `123`.

| Caso | Qué debe pasar | Hoy |
|---|---|---|
| Pago aprobado | Paquete activo, comprobante con datos | **Cumple** (con pruebas automáticas) |
| Pago rechazado | Paquete rechazado, mensaje claro y opción de reportar | **Cumple** |
| Alumno anula en Webpay (`TBK_TOKEN`) | "Pago Anulado", sin cargo, sin `commit()` | **Cumple** |
| `token_ws` y `TBK_TOKEN` juntos | No se confirma | **Cumple** |
| Alumno no vuelve (timeout) | Se resuelve consultando a Transbank | **Parcial**: está hecho (`revisar_pagos_pendientes`); falta probarlo a mano en integración |
| Monto distinto al de la orden | Se rechaza | **Cumple** |
| Retorno repetido | No cambia lo ya resuelto | **Cumple** |
| Anulación o devolución de un pago aprobado (`refund`) | Flujo completo | **Falta** (decisión de negocio pendiente) |

### B. Comprobante de pago
Transbank pide que el comprobante muestre ciertos datos. Esto es lo que recuerdo; confirmarlo en la guía:

| Dato | Hoy |
|---|---|
| Nombre del comercio y URL del sitio | **Falta**: no aparece en el comprobante |
| Número de orden de compra | **Cumple** |
| Código de autorización | **Cumple** |
| Fecha y hora de la transacción | **Cumple** |
| Monto | **Cumple** |
| Últimos 4 dígitos de la tarjeta | **Cumple**: se muestran al volver de Webpay; no se guardan en la base |
| Descripción del bien o servicio | **Cumple** (plan, clases y profesor) |
| Tipo de pago (débito, crédito o prepago) y número de cuotas | **Falta**: no aparece. Transbank lo entrega en la respuesta de `commit()`; sería un cambio chico en `confirmacion` |

El comprobante solo se ve al volver de Webpay: no hay forma de reabrirlo después. Si Transbank lo exige, habría que agregar una pantalla de "mis compras".

### C. Información al comprador
| Requisito | Hoy |
|---|---|
| Logo de Webpay visible donde se paga | **Falta**: no hay logo ni mención de Webpay en las páginas de compra |
| Política de devoluciones y anulaciones publicada | **Parcial**: está en los Términos y Condiciones; falta la validación de la abogada (Ley 19.496) |
| Datos de contacto del comercio | **Parcial**: hay formulario de contacto; falta definir razón social, RUT, domicilio y correo del responsable |
| Precios en pesos chilenos, con IVA | **Parcial**: los precios están en pesos; si el precio al alumno incluye IVA y cómo se declara lo define el contador |
| Sitio solo por HTTPS | **Cumple** (`SECURE_SSL_REDIRECT`; el retorno sale con `https`) |

### D. Operación
| Requisito | Hoy |
|---|---|
| Credenciales fuera del código | **Cumple**: variables de entorno |
| Producción no se activa a medias | **Cumple**: el sitio no arranca si falta algo |
| Conciliar lo cobrado con lo que informa Transbank | **Parcial**: se guardan orden, monto, código de autorización y fecha; falta un reporte que cruce ambos lados |
| Tarea diaria `revisar_pagos_pendientes` programada en Railway | **Pendiente**: falta programarla |
| Plazo de conservación de los registros de pago | **Pendiente**: definir con el contador y la abogada |

### E. Antes de cargar las llaves reales
1. Contrato firmado y código de comercio real entregado por Transbank.
2. Todas las filas **Falta** y **Parcial** anteriores resueltas, o aceptadas por escrito.
3. Pauta A ejecutada en integración, con capturas guardadas.
4. Cargar las cuatro variables en Railway y hacer **una compra real de monto mínimo** con una tarjeta propia. Verificar el comprobante, el código de autorización guardado y la aparición del pago en el portal de Transbank.
5. Anotar la fecha del paso a producción en `docs/DECISIONES_SOPORTE_Y_PAGOS.md`.
