# Política de paquetes y flujo financiero (S4-12 / SCRUM-92)

Paquetes **Flexible, Progreso e Intensivo**. Cada regla indica su fuente en el código, para poder verificarla.
Las cifras salen de `alumnos/paquetes.py`, que es la única fuente de precios (planes, Webpay y saldo del profesor).

> **Cómo leerlo.** Las secciones 1 a 5 describen el sistema **tal como está hoy**. La sección 6 recoge las **decisiones del equipo (26-oct-2026)** y lo que falta construir para cumplirlas. La sección 7 es el flujo de caja con esas decisiones.
> Las decisiones son del equipo. La revisión jurídica y contable sigue pendiente y es condición para habilitar transacciones reales (sección 8).

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

## 6. Decisiones del equipo (26-oct-2026) y lo que falta construir

| # | Decisión del equipo | Sistema hoy | Falta |
|---|---|---|---|
| 1 | Devolución de dinero por clases no usadas, **proporcional al precio efectivamente pagado** | No existe | Solicitud, cálculo, anulación o reversa en Webpay y registro |
| 2 | **Retracto de 10 días** desde la contratación y antes del inicio del servicio, sin exclusiones comerciales | No existe | Regla de plazo y devolución total |
| 3 | Cancelación gratis con **24 h** de anticipación. Después: condiciones transparentes y proporcionadas, con excepciones justificadas | Se cancela hasta el inicio, sin plazo | Aplicar las 24 h. **Definir las condiciones posteriores (abierto)** |
| 4 | Clases de 60 min. Vigencias de 30, 60 y 90 días | **Implementado** (`DURACION_CLASE_MIN`, `vigencia_dias`) | Nada |
| 5 | **Prórroga gratuita de 15 días** en Progreso e Intensivo, pedida antes del vencimiento | No existe | Solicitud y extensión de `fecha_fin` |
| 6 | Las clases no usadas **no son ganancia automática** de LBWUS y el vencimiento no limita el derecho a devolución | Se pierden al vencer | Tratarlas como obligación y no cerrar el derecho al vencer |
| 7 | El profesor fija su tarifa desde su panel | **Implementado** | Nada |
| 8 | Descuentos porcentuales sobre la tarifa, redondeo a $1.000, **con aceptación expresa del profesor** | Descuento fijo por plan para todos | Consentimiento del profesor. **Qué pasa si no acepta (abierto)** |
| 9 | Precios de referencia: $15.000, $59.000 y $116.000 | **Implementado** | Nada |
| 10 | Comisión de **15% IVA incluido** sobre el precio final. El profesor recibe el 85% | **Implementado** (`COMISION`) | Nada |
| 11 | Reprogramación gratis, mismo profesor, **máximo 2 por reserva**, con 24 h de aviso y dentro de la vigencia. Las cancelaciones o incumplimientos del profesor no consumen crédito ni cuentan en el límite | Sin límite ni plazo. La cancelación del profesor sí devuelve la clase | Contador de 2, regla de 24 h y registro de incumplimiento del profesor |
| 12 | Planes antiguos dejan de venderse. Se conserva el historial. Solo se ven los tres | `planes.html` ya no los muestra por nombre. El modelo `Suscripcion` los conserva | Revisar que ninguna ruta los siga vendiendo |
| 13 | Términos y Condiciones actualizados: información, derechos de estudiantes y apoderados, menores, privacidad, responsabilidades del profesor. **Revisión jurídica antes de transacciones reales** | Desactualizados (sección 5) | Redacción y revisión jurídica |
| 14 | Liquidación **semanal** al profesor, solo por clases realizadas y conciliadas | El profesor solicita retiro y el admin lo aprueba (`solicitar_retiro`, `aprobar_retiro`) | Liquidación periódica y conciliación |
| 15 | Anulaciones, devoluciones totales y parciales, conciliación de pagos y registro de comisiones | No existe | Depende de lo que permita Transbank |
| 16 | Registrar por separado el efectivo disponible, las obligaciones pendientes y el ingreso devengado | No existe | Reporte financiero (ver ejemplo en la sección 7) |

**Puntos que siguen abiertos:**
- Condiciones concretas de cancelación con menos de 24 h (decisión 3).
- Qué ocurre con los paquetes de un profesor que no acepta los descuentos (decisión 8). ¿Solo vende Flexible?
- Quién absorbe la comisión de Transbank cuando hay una devolución. Depende del contrato con el proveedor.
- Qué porcentaje de las compras es crédito y cuál débito o prepago. El cálculo muestra ambos extremos.

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

Las **300 clases son una proyección de partida, no un tope**: el volumen real puede ser mayor. Los valores **por clase y por compra** (tablas anteriores y siguientes) no dependen del volumen. Los totales sí, y se pueden escalar con la tabla "Por cada 100 clases" que sigue a este escenario.

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

**Por cada 100 clases con esa misma mezcla** (para proyectar otro volumen, multiplicar):

| Concepto | Por 100 clases |
|---|---|
| Cobrado | $1.480.667 |
| Comisión de LBWUS (15%) | $222.100 |
| Profesores (85%) | $1.258.567 |
| Transbank en crédito | $40.350 |
| Transbank en débito o prepago | $26.254 |
| Neto de LBWUS (crédito / débito) | $181.750 / $195.846 |

Esta escala solo vale si la mezcla se mantiene. Si con más volumen se venden más Progreso e Intensivo, el precio medio por clase baja. Con tarifa base queda siempre **entre $14.500 y $15.000**, sin importar cuántas clases se vendan.

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
| Todo en débito o prepago | $78.761 | $587.539 | 13,2% |

El neto real queda entre ambos. Es antes de otros costos e impuestos.

### Cómo se registra el dinero cobrado por adelantado

El alumno paga todo el paquete al comprar, pero las clases se dictan durante 60 o 90 días. Hay que separar tres cosas. Ejemplo con un **Intensivo ($116.000) tras 2 de 8 clases realizadas**:

| Concepto | Monto |
|---|---|
| Efectivo cobrado | $116.000 |
| Ingreso ya devengado de LBWUS (2 × $2.175) | $4.350 |
| Por liquidar al profesor (2 × $12.325) | $24.650 |
| Obligación pendiente por 6 clases no dictadas | $87.000 |
| **Suma** | **$116.000** |

Mientras no se dicten las clases, ese dinero es una **obligación**, no un ingreso. Con las decisiones 1 y 6, tampoco pasa a ser ganancia al vencer el paquete.

### Devolución proporcional al precio pagado

Se devuelve lo no usado al **precio por clase efectivamente pagado**, no a la tarifa del profesor:

| Plan | Clases usadas | Devolución |
|---|---|---|
| Progreso | 0 | 4 × $14.750 = $59.000 |
| Progreso | 1 | 3 × $14.750 = $44.250 |
| Progreso | 2 | 2 × $14.750 = $29.500 |
| Intensivo | 0 | 8 × $14.500 = $116.000 |
| Intensivo | 1 | 7 × $14.500 = $101.500 |
| Intensivo | 2 | 6 × $14.500 = $87.000 |

## 8. Pendiente antes del lanzamiento comercial

Fuera del alcance de esta tarea, pero condición para cobrar dinero real. Lo definió el equipo:
- Asesoría **contable y jurídica** sobre el tratamiento tributario, la documentación de las operaciones, la modalidad de intermediación, los contratos con profesores y la protección de datos personales.
- Revisión jurídica de la versión definitiva de los Términos y Condiciones.
- Verificar las tarifas de Transbank con el contrato efectivo.

## 9. Cómo reproducir las cifras

Las funciones de `alumnos/paquetes.py` (`cotizar`, `precio`, `comision`, `pago_profesor`, `iva_incluido`) devuelven los valores de las secciones 1, 2 y 7. Las pruebas están en `tests/test_paquetes.py`. La comisión de Transbank es `monto × tasa × 1,19`, sin mínimos.
