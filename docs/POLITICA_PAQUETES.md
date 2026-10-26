# Política de paquetes y flujo financiero (S4-12 / SCRUM-92)

Paquetes **Flexible, Progreso e Intensivo**. Cada regla indica su fuente en el código, para poder verificarla.
Las cifras salen de `alumnos/paquetes.py`, que es la única fuente de precios (planes, Webpay y saldo del profesor).

> **Estado:** la columna "Equipo" de la sección 6 está en blanco a propósito. Una regla no queda validada hasta que el equipo la firme.

## 1. Precio según tutor

- Cada profesor define su **tarifa por clase**: entre $10.000 y $50.000, en múltiplos de $1.000. Si no define una, es $15.000 (`validar_tarifa`).
- Precio del paquete = `clases × tarifa × (1 − descuento)`, redondeado al $1.000 más cercano (las mitades suben).
- La tarifa, el monto y las clases **quedan fijos al comprar**. Si el profesor cambia su tarifa, solo afecta a ventas futuras (`PaqueteClases`).

| Plan | Clases | Descuento | Vigencia | Precio con tarifa base ($15.000) |
|---|---|---|---|---|
| Flexible | 1 | 0 | 30 días | $15.000 |
| Progreso | 4 | 1/60 | 60 días | $59.000 |
| Intensivo | 8 | 1/30 | 90 días | $116.000 |

## 2. Descuentos voluntarios

- El descuento lo fija el **plan**, no el profesor. No existen cupones ni descuentos configurables por tutor.
- Es voluntario para el alumno: lo obtiene solo si elige libremente un paquete mayor. Nada se aplica automáticamente.
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
- Las clases sin usar al vencer **se pierden**: el sistema no tiene extensión ni devolución. Ver sección 6.

## 4. Reprogramación y cancelación

- **Reprogramar** (`reprogramar_inscripcion`): la reserva debe estar activa y no haber empezado. La nueva sesión debe ser del **mismo profesor**, futura, con cupo, no reservada ya por el alumno y dentro de la vigencia. No gasta otra clase. No hay límite de veces ni plazo de aviso.
- **Cancelar** (`cancelar_inscripcion`): se puede mientras la clase no haya empezado. La clase **vuelve al paquete**, porque las usadas se cuentan, no se restan. Si el profesor cancela la sesión, la clase también vuelve al alumno.
- **El sistema no exige aviso de 24 horas.** Ver sección 5.

## 5. Devoluciones y renovación automática

**Devoluciones en dinero: no están implementadas.** Cancelar devuelve la clase al paquete, no el dinero. No hay flujo de reembolso ni reversa en Webpay en el código.

**Sin renovación automática: se cumple.** Evidencia:
- Cada compra es un pago Webpay Plus explícito. No se guarda la tarjeta ni se usa inscripción OneClick.
- El `Procfile` define solo el proceso `web`: no hay tareas programadas ni colas.
- `requirements.txt` no incluye librerías de planificación.

**Los Términos y Condiciones (`terminos_y_condiciones.txt`) contradicen el sistema:**

| Dice | El sistema hace |
|---|---|
| "La suscripción se realiza de manera mensual" (§4) | Compra única por paquete, sin cobro recurrente |
| Planes Básico, Medio y Superior (§4) | Flexible, Progreso e Intensivo (los anteriores quedan como modelo `Suscripcion`) |
| Sin aviso de 24 h la sesión "no será reembolsable ni reprogramable" (§5) | Se puede cancelar y reprogramar hasta que empiece |

## 6. Reglas para validar por el equipo

| # | Regla | Estado en el sistema | Equipo |
|---|---|---|---|
| 1 | Precio según tarifa del tutor ($10.000–$50.000) | Implementado | |
| 2 | Descuento fijo por plan, voluntario para el alumno | Implementado | |
| 3 | Vigencia 30 / 60 / 90 días desde el pago aprobado | Implementado | |
| 4 | Reprogramar sin costo, mismo profesor, dentro de la vigencia | Implementado | |
| 5 | Cancelar hasta el inicio devuelve la clase al paquete | Implementado | |
| 6 | Sin renovación automática | Cumple por diseño | |
| 7 | Devolución de dinero por clases no usadas o vencidas | **Sin definir ni implementar** | |
| 8 | Plazo mínimo de aviso para cancelar (hoy ninguno; los Términos dicen 24 h) | **Inconsistente** | |
| 9 | ¿Qué ocurre con las clases vencidas? (hoy se pierden) | **Sin definir** | |
| 10 | Actualizar los Términos y Condiciones a esta política | **Pendiente** | |

## 7. Cambio del precio promedio y flujo de caja

**Antes:** valor fijo de $15.000 por clase, con $12.000 para el profesor (constantes `VALOR_INSCRIPCION` y `PAGO_PROFESOR` del código anterior). Eso equivale a una comisión de 20%.
**Ahora:** precio según plan y tarifa, y comisión de **15%, IVA incluido**. El profesor recibe el 85%.

**Precio promedio por clase** (tarifa base $15.000). Depende de qué planes se vendan:

| Mezcla de ventas (ejemplo) | Ticket medio | Precio medio por clase | Variación |
|---|---|---|---|
| Todo Flexible | $15.000 | $15.000 | 0% |
| 50% Flexible / 30% Progreso / 20% Intensivo | $48.400 | $14.667 | −2,2% |
| 20% Flexible / 40% Progreso / 40% Intensivo | $73.000 | $14.600 | −2,7% |
| Todo Intensivo | $116.000 | $14.500 | −3,3% |

Las mezclas son **supuestos de ejemplo**, no datos de ventas reales. Con datos reales se reemplazan.

**Ingreso de LBWUS por clase** (tarifa base): antes $3.000. Ahora $2.250 (Flexible), $2.212,5 (Progreso) y $2.175 (Intensivo). **Baja entre 25% y 27,5%**: pesa más que el descuento por paquete.

**Para actualizar el flujo de caja:**
- **Cobro adelantado:** el alumno paga $59.000 o $116.000 al comprar. Las clases se dictan durante 60 o 90 días. LBWUS cobra antes de deber el pago al profesor.
- **Obligación con el profesor:** se genera clase a clase, cuando se consume (`consumidas()`). Cobro y pago ya no coinciden en el tiempo.
- **Clases vencidas sin usar:** hoy quedan en LBWUS. Si se decide devolverlas (regla 7 y 9), hay que reservarlas como pasivo.
- **IVA:** los precios ya lo incluyen. La función `iva_incluido` calcula el IVA de la comisión (ej.: $359 sobre $2.250).
- **Costo de Webpay:** no está modelado en el código. Falta el dato del equipo (tasa de Transbank) para cerrar el flujo.

## 8. Cómo reproducir las cifras

Las funciones de `alumnos/paquetes.py` (`cotizar`, `precio`, `comision`, `pago_profesor`, `iva_incluido`) devuelven todos los valores de este documento. Las pruebas están en `tests/test_paquetes.py`.
