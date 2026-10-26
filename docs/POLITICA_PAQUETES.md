# Política de paquetes y flujo financiero (S4-12 / SCRUM-92)

Paquetes **Flexible, Progreso e Intensivo**. Cada regla indica su fuente en el código, para poder verificarla.
Las cifras salen de `alumnos/paquetes.py`, que es la única fuente de precios (planes, Webpay y saldo del profesor).

> **Cómo leerlo.** Las secciones 1 a 5 describen el sistema **tal como está hoy**. La sección 6 recoge las **decisiones del equipo (26-oct-2026)** y lo que falta construir para cumplirlas. La sección 7 es el flujo de caja con esas decisiones.
> La sección 6 sigue la **versión consolidada del 26-oct-2026**, propuesta integral que espera la aprobación del equipo. Nada de este documento certifica cumplimiento legal ni autoriza a recibir pagos reales: antes hay que completar las validaciones de la sección 8.

## 1. Precio según tutor

- Cada profesor define su **tarifa por clase** desde su panel: entre $10.000 y $50.000, en múltiplos de $1.000. Si no define una, es $15.000 (`validar_tarifa`, `Profesor.tarifa`).
- Precio del paquete = `clases × tarifa × (1 − descuento)`, redondeado al $1.000 más cercano (las mitades suben).
- La tarifa, el monto y las clases **quedan fijos al comprar**. Si el profesor cambia su tarifa, solo afecta a ventas futuras (`PaqueteClases`).

| Plan | Clases | Descuento | Vigencia | Precio con tarifa base ($15.000) |
|---|---|---|---|---|
| Flexible | 1 | 0 | 30 días | $15.000 |
| Progreso | 4 | 1/60 | 60 días | $59.000 |
| Intensivo | 8 | 1/30 | 90 días | $116.000 |

## 2. Descuentos

- El descuento lo fija el **plan**, no el profesor, y hoy se aplica a todos los profesores. No existen cupones.
- Es voluntario para el alumno: lo obtiene solo si elige un paquete mayor.
- **Observación:** el "1,7% / 3,3%" es exacto solo con la tarifa base. Como el precio se redondea a $1.000, el descuento real cambia con la tarifa:

| Tarifa | Progreso | Intensivo |
|---|---|---|
| $10.000 | 2,5% | 3,8% |
| $15.000 | 1,7% | 3,3% |
| $20.000 | 1,2% | 3,1% |
| $50.000 | 1,5% | 3,2% |

## 3. Vigencia

- El paquete se activa **solo cuando Webpay aprueba el pago**. La vigencia se cuenta desde ese momento (`_activar_pendientes`).
- Reenviar el mismo pago no lo activa dos veces ni extiende la vigencia (prueba de replay en `test_flujos_funcionales.py`).
- La clase debe comenzar **antes del vencimiento**. Con el paquete vencido no se puede reservar (`test_paquete_vencido_o_sesion_fuera_de_la_vigencia`).
- Hoy las clases sin usar al vencer **se pierden**: no hay prórroga ni devolución. La decisión del equipo cambia esto (sección 6).

## 4. Reprogramación y cancelación

- **Reprogramar** (`reprogramar_inscripcion`): la reserva debe estar activa y no haber empezado. La nueva sesión debe ser del **mismo profesor**, futura, con cupo, no reservada ya por el alumno y dentro de la vigencia. No gasta otra clase. **Hoy no hay límite de veces ni plazo de aviso.**
- **Cancelar** (`cancelar_inscripcion`): se puede mientras la clase no haya empezado. La clase **vuelve al paquete**, porque las usadas se cuentan, no se restan. Si el profesor cancela la sesión, la clase también vuelve al alumno. **Hoy no se exige aviso de 24 horas.**

## 5. Devoluciones y renovación automática (estado actual)

**Devoluciones en dinero: no están implementadas.** Cancelar devuelve la clase al paquete, no el dinero. No hay flujo de reembolso ni reversa en Webpay en el código.

**Sin renovación automática: se cumple.** Evidencia:
- Cada compra es un pago Webpay Plus explícito. No se guarda la tarjeta ni se usa inscripción OneClick.
- El `Procfile` define solo el proceso `web`: no hay tareas programadas ni colas.
- `requirements.txt` no incluye librerías de planificación.

**Los Términos y Condiciones (`terminos_y_condiciones.txt`) contradicen el sistema:**

| Dice | El sistema hace |
|---|---|
| "La suscripción se realiza de manera mensual" (§4) | Compra única por paquete, sin cobro recurrente |
| Planes Básico, Medio y Superior (§4) | Flexible, Progreso e Intensivo (los anteriores quedan solo como historial en el modelo `Suscripcion`) |
| Sin aviso de 24 h la sesión "no será reembolsable ni reprogramable" (§5) | Se puede cancelar y reprogramar hasta que empiece |

## 6. Política consolidada (26-oct-2026) y lo que falta construir

Sigue los puntos 1 a 11 de la versión consolidada del equipo. Los puntos 12 a 15 están en las secciones 8 y 9.

| # | Política consolidada | Sistema hoy | Falta construir |
|---|---|---|---|
| 1 | **Devoluciones y retracto.** Devolución total si no usó ninguna clase; proporcional al precio pagado (con su descuento) si usó parte. No se descuentan multas ni costos de Transbank. Retracto de 10 días cuando sea aplicable, antes de la prestación. Si Webpay no permite devolver directamente, un procedimiento alternativo autorizado y documentado | No existe | Solicitudes de devolución total y parcial, su estado y la trazabilidad de los montos devueltos |
| 2 | **Cancelaciones.** Gratis con 24 h de anticipación, recuperando el crédito. Con menos de 24 h: **una excepción gratuita por paquete**. Cancelaciones tardías injustificadas reiteradas: registro de incidencias y posible revisión administrativa de reservas futuras, con criterios objetivos. **Sin multas, retenciones ni pérdida automática de créditos.** Las clases canceladas no cuentan como realizadas ni generan pago al profesor ni comisión | Se cancela hasta el inicio, sin plazo. La clase cancelada no se consume (`consumidas()`) | Regla de 24 h, contador de la excepción por paquete y registro de incidencias |
| 3 | **Vigencia.** Clases de 60 min. Vigencia de 30, 60 y 90 días desde la confirmación de la compra. **Prórroga gratuita única de 15 días** en Progreso e Intensivo, pedida antes del vencimiento. Vencido el paquete no se reserva, pero lo no realizado **no pasa a ser ingreso** de LBWUS y se puede pedir su devolución proporcional. Si el vencimiento se debe al profesor o a la plataforma, LBWUS ofrece una solución | Duración y vigencias **implementadas** (`DURACION_CLASE_MIN`, `vigencia_dias`). Las clases vencidas se pierden | Prórroga única y tratamiento de lo vencido como obligación |
| 4 | **Términos y Condiciones** reescritos: precios, descuentos, vigencias, cancelaciones, reprogramaciones, devoluciones, retracto, responsabilidades de profesores, reclamos, datos personales, menores y apoderados. Revisión jurídica antes de pagos reales y **aceptación expresa al contratar** | Desactualizados (sección 5). La compra **no muestra ni pide aceptar** los Términos; el pie de página los marca como "próximamente" | Redacción, revisión jurídica, publicación y aceptación en el flujo de compra |
| 5 | **Tarifas y descuentos voluntarios.** Tarifa del profesor desde su panel. Cada profesor decide **por paquete** si ofrece Progreso e Intensivo; si no, ese paquete no se puede contratar y queda Flexible. Descuentos de ≈1,67% y ≈3,33% sobre la tarifa, redondeo a $1.000. Precios de referencia: $15.000, $59.000 y $116.000. Los cambios solo afectan compras futuras | Tarifa, descuentos, redondeo, precios y condiciones fijas al comprar: **implementado**. Todos los profesores ofrecen los tres paquetes | Opción del profesor por paquete y ocultar el paquete no ofrecido |
| 6 | **Comisión** de 15% IVA incluido sobre el precio final; 85% bruto para el profesor. LBWUS asume sus costos de procesamiento sin cambiar la comisión del profesor. El 15% **no es ingreso neto** | **Implementado** (`COMISION`) | Nada en el cálculo |
| 7 | **Reprogramación:** **máximo 2 por clase contratada**, dentro de la vigencia y normalmente con el mismo profesor. **Cancelar y volver a reservar con el mismo crédito cuenta como reprogramación.** Lo causado por el profesor, por LBWUS o por circunstancias justificadas no cuenta. El límite no puede impedir devoluciones | Sin límite ni plazo. Ya impide reservar dos veces la misma sesión | Contador por clase, historial de cada cambio y registro de su causa. **Ojo:** los créditos no tienen identidad propia (se cuentan, no se registran uno a uno), así que seguir "el mismo crédito" entre una cancelación y una nueva reserva requiere diseñarlo |
| 8 | **Planes antiguos** (Básico, Medio, Superior y suscripciones) se dejan de vender. Solo Flexible, Progreso e Intensivo, sin suscripciones obligatorias ni renovación automática. Se conserva el historial | `planes.html` ya no los muestra por nombre. El modelo `Suscripcion` conserva el historial. No hay renovación automática (sección 5) | Verificar que ninguna ruta permita contratarlos |
| 9 | **Transbank:** 2,29% y 1,49% + IVA como referencia, con mínimos y sujeto a contrato. LBWUS absorbe los costos de procesamiento y anulación sin descontarlos de las devoluciones. Registrar operaciones aprobadas, rechazadas, anuladas y reembolsadas, y conciliarlas | Solo registra pagos aprobados y rechazados (`_activar_pendientes`) | Estados de anulación y reembolso, conciliación y registro del costo del proveedor |
| 10 | **Pagos a profesores:** liquidación semanal propuesta de las clases realizadas y conciliadas. Lo pendiente, cancelado, no realizado o en reclamo no se liquida. Separar lo cobrado, las obligaciones pendientes y lo devengado. Confirmar que el proveedor permite administrar y transferir fondos a los profesores | El profesor solicita retiro y el admin lo aprueba (`solicitar_retiro`, `aprobar_retiro`) | Liquidación semanal, conciliación y reporte de lo cobrado, pendiente y devengado (ejemplo en la sección 7) |
| 11 | **Proyección:** 300 clases el primer año (132 / 26 / 8) y 50% crédito / 50% débito o prepago. **Son supuestos**, no datos observados; se reemplazan con ventas reales | No aplica | Nada: los escenarios de medios de pago (todo crédito, 50/50, todo débito) ya están en la sección 7 |

## 7. Cambio del precio promedio y flujo de caja

**Antes:** valor fijo de $15.000 por clase, con $12.000 para el profesor (constantes `VALOR_INSCRIPCION` y `PAGO_PROFESOR` del código anterior). Equivale a una comisión de 20%.
**Ahora:** precio según plan y tarifa, y comisión de **15%, IVA incluido**.

| Por clase (tarifa base) | Paga el alumno | Ingreso de LBWUS | Profesor |
|---|---|---|---|
| Antes | $15.000 | $3.000 (20%) | $12.000 |
| Flexible | $15.000 | $2.250 | $12.750 |
| Progreso | $14.750 | $2.212,5 | $12.537,5 |
| Intensivo | $14.500 | $2.175 | $12.325 |

El ingreso de LBWUS por clase **baja entre 25% y 27,5%**. Pesa más que el descuento por paquete.

### Escenario de referencia del primer año (proyección de 300 clases)

Las **300 clases son una proyección de partida, no un tope**: el volumen real puede ser mayor. Los valores **por clase y por compra** (tablas anteriores y siguientes) no dependen del volumen.

Mezcla inicial del equipo: **132 compras Flexible, 26 Progreso y 8 Intensivo**. Es una distribución de partida, **no son ventas reales**. No incluye devoluciones, prórrogas ni clases vencidas.

| Plan | Compras | Clases | Cobrado | Comisión LBWUS (15%) |
|---|---|---|---|---|
| Flexible | 132 | 132 | $1.980.000 | $297.000 |
| Progreso | 26 | 104 | $1.534.000 | $230.100 |
| Intensivo | 8 | 64 | $928.000 | $139.200 |
| **Total** | **166** | **300** | **$4.442.000** | **$666.300** |

- **Ticket medio:** $26.759 por compra.
- **Precio medio por clase:** $14.807, es decir 1,3% menos que los $15.000 anteriores.
- **Profesores (85%):** $3.775.700.
- **IVA contenido en la comisión de LBWUS:** $106.350 (`iva_incluido`).

### Costo de Transbank (supuesto referencial)

Tasas del equipo: **2,29% + IVA** para crédito y **1,49% + IVA** para débito o prepago. Son referenciales: están sujetas a mínimos y a las condiciones reales del contrato. El cálculo no aplica mínimos. La comisión se cobra sobre el total pagado, incluida la parte del profesor.

| Por compra | Crédito | Débito o prepago | Comisión LBWUS | Neto (crédito / débito) |
|---|---|---|---|---|
| Flexible ($15.000) | $409 | $266 | $2.250 | $1.841 / $1.984 |
| Progreso ($59.000) | $1.608 | $1.046 | $8.850 | $7.242 / $7.804 |
| Intensivo ($116.000) | $3.161 | $2.057 | $17.400 | $14.239 / $15.343 |

| Escenario de 300 clases | Costo Transbank | Neto de LBWUS | % de lo cobrado |
|---|---|---|---|
| Todo en crédito | $121.049 | $545.251 | 12,3% |
| **Supuesto del equipo: 50% crédito y 50% débito o prepago** | $99.905 | $566.395 | 12,8% |
| Todo en débito o prepago | $78.761 | $587.539 | 13,2% |

El 50/50 es un supuesto financiero, no un comportamiento observado. Se reemplaza con datos reales cuando existan. Es antes de otros costos e impuestos.

### Cómo se registra el dinero cobrado por adelantado

El alumno paga todo el paquete al comprar, pero las clases se dictan durante 60 o 90 días. Hay que separar tres cosas. Ejemplo con un **Intensivo ($116.000) tras 2 de 8 clases realizadas**:

| Concepto | Monto |
|---|---|
| Efectivo cobrado | $116.000 |
| Ingreso ya devengado de LBWUS (2 × $2.175) | $4.350 |
| Por liquidar al profesor (2 × $12.325) | $24.650 |
| Obligación pendiente por 6 clases no dictadas | $87.000 |
| **Suma** | **$116.000** |

Mientras no se dicten las clases, ese dinero es una **obligación**, no un ingreso. Con los puntos 1 y 3 de la sección 6, tampoco pasa a ser ganancia al vencer el paquete.

### Devolución proporcional al precio pagado

Se devuelve lo no usado al **precio por clase efectivamente pagado**, no a la tarifa del profesor. Según los puntos 1 y 9 de la sección 6, el estudiante recibe el monto completo y LBWUS absorbe el costo de Transbank:

| Plan | Clases usadas | Devolución |
|---|---|---|
| Progreso | 0 | 4 × $14.750 = $59.000 |
| Progreso | 1 | 3 × $14.750 = $44.250 |
| Progreso | 2 | 2 × $14.750 = $29.500 |
| Intensivo | 0 | 8 × $14.500 = $116.000 |
| Intensivo | 1 | 7 × $14.500 = $101.500 |
| Intensivo | 2 | 6 × $14.500 = $87.000 |

## 8. Validaciones previas al lanzamiento comercial

Fuera del alcance de esta tarea, pero condición para cobrar dinero real:
- **Revisión jurídica (punto 12)** según la Ley N.º 19.496 de Protección de los Derechos de los Consumidores: retracto, proporcionalidad de las restricciones, cancelaciones e inasistencias, devoluciones, responsabilidades de intermediación, y protección de menores y de sus datos. Ninguna regla interna puede restringir derechos irrenunciables.
- **Revisión contable y tributaria (punto 13)** de las comisiones, los documentos tributarios, las obligaciones de los profesores, los pagos anticipados, las devoluciones y el reconocimiento de ingresos, incluidos los costos de Transbank y sus impuestos.
- **Validación operativa de pagos (punto 14):** contrato verificado con el proveedor, conciliación y devolución funcionando, y un procedimiento autorizado para liquidar a profesores. Se prueba con operaciones de prueba: compras, rechazos, anulaciones, devoluciones parciales, clases completadas y escenarios de error.

## 9. Aprobación y trazabilidad

El equipo debe confirmar expresamente que este documento refleja las decisiones comerciales acordadas. Una vez aprobado, es la referencia para actualizar los Términos y Condiciones, el flujo de caja, las reglas del sistema y los criterios de aceptación de las tareas de Jira.

**Aprobadores (punto 15):** Francheska, Franco y Benjamín.
**Estado de aprobación:** pendiente.

La aprobación del equipo **no reemplaza** las revisiones jurídica, contable, tributaria ni contractual necesarias para operar con dinero real.

**Los puntos de este documento son propuestas para aprobación interna. No constituyen certificación de cumplimiento legal ni autorización para recibir pagos reales.**

## 10. Cómo reproducir las cifras

Las funciones de `alumnos/paquetes.py` (`cotizar`, `precio`, `comision`, `pago_profesor`, `iva_incluido`) devuelven los valores de las secciones 1, 2 y 7. Las pruebas están en `tests/test_paquetes.py`. La comisión de Transbank es `monto × tasa × 1,19`, sin mínimos.
