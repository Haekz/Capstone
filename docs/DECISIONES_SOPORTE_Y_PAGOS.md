# LBWUS: área de soporte y manejo del dinero — contexto y decisiones

Preparado: 29-oct-2026. Solo análisis: todavía no se cambió código por este documento.
Cómo usarlo: marca con `[x]` la opción elegida en la sección 6. "(recomendado)" = sugerencia de Stifler.

---

## 1. Dónde estamos

### Hecho y subido (falta mergear en GitHub, en este orden)
| Orden | Rama | Commit | Contenido |
|---|---|---|---|
| 1 | `fran-soporte-2b1` | `23d1551` | Rol soporte (agente y líder), tickets, asignación automática, el admin deja de ver documentos |
| 1 | `fran-soporte-2b1` | `5c07924` | Textos: "nuestro equipo de soporte revisará…" |
| 2 | `fran-soporte-2b2` | `27ee561` | Plazo de 5 días hábiles de Chile, correos al agente y líderes, cron de atrasados |
| 3 | `fran-contacto` | `97526a9` | El formulario de contacto guarda el mensaje (antes decía "enviado" sin enviar nada) |

Suite completa verde en las tres ramas. Ojo: el `main` local estaba 4 commits atrás del de GitHub; actualizarlo antes de crear ramas nuevas.

### El plan original de 5 pasos (reconstruido)
| Paso | Contenido | Estado |
|---|---|---|
| 1 | Área de soporte: roles, líder, tickets, asignación mixta, admin sin documentos | HECHO (2b-1) |
| 2 | Plazos y avisos | PARCIAL (2b-2). Falta: aviso de retraso al usuario y aviso de documentos por vencer |
| 3 | Nuevas categorías de ticket (pagos, clases y el resto de los reportes) | PENDIENTE |
| 4 | Seguridad y conducta | PENDIENTE |
| 5 | Datos personales | PENDIENTE |

---

## 2. Decisiones ya tomadas

| # | Decisión |
|---|---|
| D1 | Roles de soporte: **agente** y **líder**. |
| D2 | El **admin deja de ver documentos** (carnet, certificados, títulos). |
| D3 | Asignación **mixta**: automática al agente con menos carga y el líder reasigna. |
| D4 | Plazos: **verificaciones (apoderados, títulos) 5 días hábiles**; **pagos y clases 2 días hábiles**. |
| D5 | **Todos los reportes van a soporte.** El admin no atiende casos. |
| D6 | El **admin ve métricas**: ingresos por día, ganancias, resumen de retiros, registros. |
| D7 | **Soporte es la primera capa en pagos**: revisa qué falló y si el usuario se equivocó. No mueve dinero. |
| D8 | **Los retiros de profesores los valida y aprueba siempre el admin.** |
| D9 | Los problemas de retiros van **dentro de la categoría Pagos** (2 días hábiles). |
| D10 | Abren tickets: **alumno, profesor y apoderado**. El público sigue con el formulario de contacto. |
| D11 | Aviso de retraso al usuario **cada 3 días** mientras su ticket está atrasado. |
| D12 | Documentos por vencer (30 días): **avisar al agente asignado**. |
| D13 | Devoluciones de dinero: **flujo completo más adelante**, no ahora. |
| D14 | Primero se hace **2b-3** (los avisos). Los PRs los mergea Francheska en GitHub. |
| D15 | El plan se guarda en `PENDIENTES_LBWUS.md`. |
| D16 | (31-oct, P7) Técnico, conducta y otro: **5 días hábiles**. |
| D17 | (31-oct, P8) Conducta: **solo líderes o agentes habilitados en Conducta**, plazo 2 días y aviso diario de atraso **al equipo**. (01-nov) La disculpa al usuario va cada 3 días hábiles, como el resto: a diario sería insistente. |
| D18 | (31-oct, P9; REVISADA 01-nov) Alumno **menor de edad: no abre tickets** (tampoco por el canal viejo `enviar_reporte`). Califica sus clases; los tickets los abre su apoderado eligiendo al estudiante. Su portal le dice que cuente a su apoderado si algo lo incomodó. |
| D21 | (01-nov) Si un menor califica una clase con **1 o 2 estrellas**, se avisa a su apoderado (sin el comentario) para que abra un ticket si hubo un problema. |
| D22 | (01-nov; CERRADA 02-nov) Línea de ayuda externa en el portal del menor: **147 Fono Niños** (gratuito, 24 h) y **149 Fono Familia** (violencia intrafamiliar, 24 h), de Carabineros, validados en ChileAtiende. Se muestran con enlace para llamar (`tel:`) solo al menor. El `*4141` no se validó y **no se publica**. |
| D23 | (01-nov, paso 6e) Se retira el canal viejo "Soporte / Reportes": ahora todo es ticket. Los reportes viejos **pendientes pasan a tickets** "Otro" de su mismo autor, con plazo desde el despliegue (`manage.py pasar_reportes_a_tickets`, una vez). Los de menores no se pasan: los decide un líder. El usuario conserva su historial de reportes, solo lectura. El admin ya no ve ni resuelve reportes. |
| D19 | (31-oct, P6) Acciones **sin salida de dinero**: las aplica el agente; el sistema valida y deja registro. |
| D20 | (31-oct, P10/P11) "Cada 3 días" = **días hábiles**. Documentos borrados: se avisa al apoderado y los vuelve a subir. |

---

## 3. Hallazgos en el código

### Dinero
| # | Hallazgo | Riesgo |
|---|---|---|
| H1 | `aprobar_retiro` / `rechazar_retiro` **no registran quién** aprobó o rechazó, no piden motivo y permiten **aprobar un retiro ya rechazado**. | Alto: si falta plata, no hay responsable |
| H2 | El profesor **escribe su cuenta bancaria a mano en cada retiro** y **no se verifica que sea suya**. | Alto: con una sesión robada se puede desviar el saldo |
| H3 | El banco se crea desde texto libre (`get_or_create`): "Banco Estadoo" queda como banco nuevo. | Medio |
| H4 | El número de cuenta se guarda **sin cifrar** (los documentos sí van cifrados). | Medio |
| H5 | No existe el estado **"Pagado"**: aprobado no significa que la plata llegó. Sin número de operación ni comprobante. | Alto |
| H6 | Si Webpay rechaza un pago, **no se guarda el motivo** (`response_code`): soporte no puede diagnosticar. | Medio |

### Métricas del admin
| # | Hallazgo |
|---|---|
| H7 | Las **ganancias son inventadas**: `max(inscripciones × 15000, 180000)`, con el precio antiguo y un piso fijo. La ganancia real es la **comisión del 15%** sobre lo pagado (política, punto 6). |
| H8 | **"Ingresos por día" no existe**: Django solo guarda el último login. Hay que registrar cada ingreso. |
| H9 | Los registros solo tienen totales, sin cortes por día, mes o trimestre. |

### Soporte
| # | Hallazgo |
|---|---|
| H10 | `Ticket` solo puede apuntar a un apoderado, un vínculo o un profesor. Hay que ampliarlo para los casos que reporta el usuario. |
| H11 | `Reporte` no tiene categoría: el formulario del alumno la pega como texto dentro de la descripción. |
| H12 | **El profesor y el apoderado no tienen formulario de soporte** (`enviar_reporte` ya acepta profesores). |
| H13 | `Ticket.categoria` tiene `max_length=12`; `datos_personales` mide 16. |
| H14 | La bandeja de contacto quedó en el **admin**; por D5 tiene que pasar a soporte. |
| H15 | A 2b-2 le faltan los avisos al usuario (retraso y documentos por vencer). |

### Otros
| # | Hallazgo |
|---|---|
| H16 | **CSS muerto del carrito**: ~50 reglas sin uso (25 en `alumn_1.css`, 25 en `styles.css`). Sin rama todavía. Necesita revisión visual. |
| H17 | Seguridad S-07: 6 vistas de alumno sin `@alumno_required` (PENDIENTES, punto 1). |

---

## 4. Propuesta

### 4.1 Quién hace qué
| Rol | Hace | No hace |
|---|---|---|
| **Agente de soporte** | Atiende tickets de su categoría, investiga, responde, corrige datos del usuario | Mover dinero, ver documentos de tickets ajenos |
| **Líder de soporte** | Todo lo del agente, más ver todos los tickets, reasignar, supervisar cargas | Ver documentos sin tener el ticket asignado |
| **Admin** | Métricas, aprobar y pagar retiros, planes, clases, usuarios | Atender tickets, ver documentos |

### 4.2 Categorías de ticket
| Categoría | Plazo | Entra por |
|---|---|---|
| Apoderados (verificación) | 5 días hábiles (ya programado) | Automático |
| Títulos (verificación) | 5 días hábiles (ya programado) | Automático |
| **Pagos** (incluye retiros) | **2 días hábiles** | Formulario, botón "reportar pago", pago fallido |
| **Clases** | **2 días hábiles** | Formulario |
| Técnico, conducta, otro, contacto | Por decidir (P7) | Formulario y contacto |

### 4.3 Niveles de riesgo para acciones con dinero
| Nivel | Ejemplos | Quién |
|---|---|---|
| Bajo: sin salida de dinero | Prórroga única de 15 días, excepción por cancelación tardía, devolver una clase al paquete | Por decidir (P6) |
| Medio: sale dinero | Devoluciones (futuro, D13) | Se define junto con el flujo de devoluciones |
| Alto: ejecutar el pago | Transferencia en el banco | Admin, con comprobante |

Principios: quien propone no aprueba; quien aprueba no es quien maneja el banco; los montos los calcula el servidor; todo queda registrado; los estados solo avanzan.

### 4.4 Cómo se le paga al profesor
El sistema **registra** el dinero, no lo mueve: lo mueve el banco, que ya tiene sus propios controles (segunda clave, firma conjunta).

| Opción | Cómo | A favor | En contra |
|---|---|---|---|
| **A. Transferencia manual** (recomendado) para partir | El admin aprueba, transfiere en el portal del banco y registra el número de operación → "Pagado" | Simple, sin integraciones, sirve para ~300 clases al año | No escala con muchos profesores |
| **B. Nómina semanal** (recomendado) para crecer | LBWUS genera la liquidación semanal y el archivo de pago masivo; el admin lo sube y el banco pide doble firma | Estándar en Chile y ya está en la política (punto 10) | Requiere cuenta empresa y el formato del banco |
| C. Pago dividido (Mercado Pago, Transbank Mall) | La plata se reparte al comprar | Sin transferencias | **Choca con la política**: el profesor cobraría antes de dar la clase |

### 4.5 Flujo de retiros
```
Profesor solicita ──► Admin APRUEBA (queda quién y cuándo)
        │                    │
        │                    ▼
        │           Admin transfiere ──► PAGADO (n.º de operación y comprobante)
        │                    │
        │                    └─► El banco devuelve la transferencia
        │                              ▼
        │                     PAGO FALLIDO ──► ticket automático a soporte (Pagos, 2 días)
        │                              └─► soporte corrige los datos ──► vuelve a "Aprobado"
        │
        └─► Admin RECHAZA (motivo obligatorio, visible para el profesor)
                 └─► si el profesor no está de acuerdo ──► abre un ticket de Pagos
```
Rechazado o fallido: la plata vuelve al saldo disponible. Pendiente, aprobado o pagado: descuenta del saldo.

### 4.6 Seguridad de los datos bancarios
| Medida | Para qué |
|---|---|
| La cuenta se registra **una vez en el perfil**, no en cada retiro | Un solo lugar que controlar |
| **Titular = RUT del profesor** | Solo se paga a cuentas propias |
| Si cambia la cuenta: **correo de aviso + 48 h de espera** para retirar | Si no fue él, alcanza a reaccionar |
| Banco desde una **lista cerrada** | Se acaba el texto libre |
| Número de cuenta **cifrado** (mismo Fernet de los documentos) | Mismo estándar que los carnets |
| El admin ve la cuenta **enmascarada** (•••• 4321), salvo al pagar | Mínimo privilegio |

### 4.7 Pagos de alumnos fallidos en Webpay
- **Rechazo normal** (sin fondos, tarjeta bloqueada): mensaje claro + botón **"Reportar problema con este pago"**, que abre el ticket con la orden de compra ya cargada. No se abre un ticket por cada rechazo, porque inundaría a soporte.
- **Error nuestro** (Transbank cobró y el paquete no se activó): **ticket automático**.
- Se guarda el código de respuesta de Transbank. **Nunca** datos de tarjeta.

### 4.8 Panel del admin (solo lectura)
| Métrica | Cortes |
|---|---|
| Registros (alumnos, profesores, apoderados) | Día, mes, trimestre |
| Ingresos a la plataforma | Día, mes, trimestre |
| **Ganancias reales** (comisión del 15% sobre lo pagado) | Día, mes, trimestre |
| Retiros: solicitados, aprobados, pagados, fallidos, por profesor | Día, mes, trimestre |
| Salud del soporte: tickets por categoría, atrasados, tiempo de respuesta | Por decidir (P13) |

---

## 5. Requiere a otras personas (no lo decide el código)
| Tema | Quién |
|---|---|
| Boleta de honorarios: quién la emite a quién y si LBWUS retiene impuesto (15,25% en 2026). Cambia el monto neto del profesor | **Contador** (política, punto 13) |
| Textos de menores, declaraciones v2 y aviso de documentos | **Revisión legal** |
| Cuenta empresa y formato de nómina del banco (si se elige la opción B) | **Banco / finanzas** |
| Crons en Railway (`borrar_documentos_vencidos`, `avisar_tickets_atrasados`) y `DOCUMENTOS_CLAVE` | **Quien despliega** |

---

## 6. Preguntas para decidir

### Pagos a profesores
**P1. ¿Cómo se le paga al profesor?**
- [ ] A. Transferencia manual ahora y B (nómina semanal) después (recomendado)
- [ ] B. Nómina semanal desde el inicio
- [ ] C. Pago dividido (choca con la política)

**P2. ¿El titular de la cuenta tiene que ser el mismo profesor (mismo RUT)?**
- [ ] Sí (recomendado)
- [ ] No

**P3. ¿48 h de espera para retirar después de cambiar la cuenta bancaria?**
- [ ] Sí, 48 h (recomendado)
- [ ] Otro plazo: ____
- [ ] Sin espera

**P4. ¿Cuándo se procesan los retiros?**
- [ ] Cuando el profesor los pide (hoy promete 24 a 48 horas hábiles)
- [ ] Liquidación semanal (política, punto 10)

**P5. Pagos de alumnos rechazados en Webpay:**
- [ ] Botón "reportar" + ticket automático solo si el error es nuestro (recomendado)
- [ ] Ticket automático por cada rechazo
- [ ] Solo el botón "reportar"

### Soporte
**P6. Acciones sin salida de dinero (prórroga, excepción, devolver una clase):**
- [ ] El agente las aplica directo; el sistema valida que correspondan y deja registro (recomendado)
- [ ] Necesitan aprobación del líder

**P7. Plazo para los reportes que no son pagos ni clases (técnico, conducta, otro, contacto):**
- [ ] 5 días hábiles, como las verificaciones (recomendado)
- [ ] 2 días hábiles, como pagos y clases
- [ ] Otro: ____

**P8. Reportes de conducta de un profesor (pueden involucrar a menores):**
- [ ] Solo los ven líderes o agentes habilitados en esa categoría, con prioridad (recomendado)
- [ ] Igual que cualquier ticket

**P9. Alumno menor de edad:**
- [ ] Puede abrir tickets de clases; los de pagos los abre su apoderado (recomendado)
- [ ] Puede abrir cualquier ticket

**P10. "Cada 3 días" del aviso de retraso:**
- [ ] Días hábiles (sin fines de semana ni feriados, como los plazos) (recomendado)
- [ ] Días corridos

**P11. Documentos de apoderados: aviso al agente 5 días antes del borrado (D12). Y cuando se borran:**
- [ ] También se avisa al apoderado, para que sepa que debe volver a subirlos (recomendado)
- [ ] El agente lo gestiona; no se avisa al apoderado

### Admin
**P12. ¿Las ganancias del panel se calculan como la comisión del 15% sobre los pagos aprobados?**
- [ ] Sí (recomendado)
- [ ] Otro criterio: ____

**P13. ¿El admin ve las métricas de soporte (solo números, sin el contenido de los tickets)?**
- [ ] Sí (recomendado)
- [ ] No

### Documentos
**P14. ¿Aceptamos documentos en PDF?** (Hoy se rechazan porque la marca de agua solo funciona sobre imágenes.)
- [ ] Sí: se convierten a imagen al subirlos con `pypdfium2`, y sigue el mismo flujo (recomendado)
- [ ] No, solo JPG o PNG
- [ ] Decidir después, junto con la revisión legal

### Orden de trabajo
**P15. ¿Este orden te sirve?**
- [ ] Sí (recomendado)
- [ ] Cambiarlo: ____

| # | Paso | Contenido |
|---|---|---|
| 0 | Mergear (Francheska) | 2b-1 → 2b-2 → contacto; actualizar `main` local |
| 1 | **2b-3: avisos** | Retraso cada 3 días al usuario; documentos por vencer al agente |
| 2 | **R1: retiros con trazabilidad** | Quién aprueba o rechaza, motivo, estado Pagado con número de operación, estados que solo avanzan (H1, H5) |
| 3 | **3a: pagos y clases** | Categorías de 2 días, `Ticket` ampliado, `Reporte` con categoría, formulario para profesor y apoderado, pago fallido → ticket, código de Transbank |
| 4 | **3b: resto de reportes** | Técnico, conducta, otro y contacto pasan a soporte (D5, P7, P8) |
| 5 | **R2: cuenta bancaria segura** | Sección 4.6 |
| 6 | **Métricas del admin** | Sección 4.8; corrige H7, H8 y H9 |
| 7 | CSS del carrito | PR aparte con capturas antes y después (H16) |
| 8 | Seguridad S-07 | 6 vistas sin decorador (H17) |
| Después | | Nómina semanal, devoluciones, datos personales, PDF y revisión legal |

---

## 7. Respuestas del 29-oct (reemplazan las recomendaciones de la sección 6)

| # | Decisión |
|---|---|
| P1 | Nómina semanal desde el inicio, pagada con transferencias manuales. Cada pago queda vinculado a profesor, monto, clases y comprobante. |
| P2 | Solo cuentas del mismo profesor (mismo RUT). Sin pagos a terceros en el MVP. |
| P3 | 48 h corridas tras cambiar la cuenta: confirmación del cambio, aviso al correo registrado y verificación de identidad. No se paga a la cuenta nueva durante ese plazo. |
| P4 | Liquidación semanal del saldo disponible. La interfaz y la política indican el mismo día de corte y de pago. Se retira la promesa de "24 a 48 horas". |
| P5 | Rechazo normal: mensaje claro, reintentar y botón de ayuda. Ticket automático ante falla técnica o cobro inconsistente. Un pago en estado incierto se verifica antes de permitir otro intento (evita cobros duplicados). |
| P6 | Soporte (personas, no IA) aplica excepciones acotadas por reglas, con motivo y registro. Devoluciones y excepciones fuera de regla: admin autorizado. |
| P7 | Se separan primera respuesta y resolución. Casos normales: primera respuesta en 1 día hábil y resolución en 5. Lo que impide una clase o afecta la seguridad es prioritario. |
| P8 | Conducta: acceso restringido, prioridad, responsable definido y una ruta urgente para casos graves. |
| P9 | El menor puede reportar clases, técnico, conducta y avisar de un problema de pago. Las decisiones económicas las gestiona su apoderado. |
| P10 | Seguimiento cada 3 días hábiles en casos normales; más frecuente en urgentes. |
| P11 | Al borrar documentos se avisa al titular y, cuando corresponda, al apoderado. La eliminación no se aplica por igual a cualquier archivo. |
| P12 | Se muestran por separado: pagos aprobados, comisión estimada, comisión generada por clases realizadas y saldo disponible del profesor. |
| P13 | El admin ve métricas agregadas de soporte (cantidad, tiempos, categorías, pendientes), sin acceso al contenido. |
| P14 | Se acepta PDF con validación y visualización segura. Convertir a imagen sirve para ver, pero el original no se destruye automáticamente. |
| P15 | Orden no aprobado: primero integrar lo revisado y probado; luego coherencia de pagos, saldos y trazabilidad, antes de habilitar retiros. |

### Hallazgos nuevos
| # | Hallazgo |
|---|---|
| H18 | **El saldo del profesor incluye clases reservadas a futuro.** `calcular_saldos` usa `consumidas()` (activas, sin importar la fecha), así que se puede retirar dinero por clases no dictadas. Contradice la política (punto 10). Ya existe `completadas()` (solo sesiones terminadas). |
| H19 | **Los tickets no tienen respuestas.** No hay dónde registrar la primera respuesta ni el seguimiento que pide P7. |
| Dato | Webpay está en modo `IntegrationType.TEST`: hoy no se mueve dinero real. |

### Datos del código para P11
La eliminación a los 30 días solo afecta a `apoderados.Documento` (carnet y certificado o resolución del vínculo). Se cuenta desde que se subió y también se borra al aprobar o rechazar. No toca comprobantes, retiros ni otros archivos. El titular es el apoderado que lo subió.

### Pendiente de decidir
| # | Pregunta | Sugerencia |
|---|---|---|
| N1 | Día de corte y día de pago semanal. ¿Liquidación automática de todo el saldo o el profesor lo pide antes del corte? ¿Monto mínimo? | Corte domingo 23:59, pago martes; automática; sin mínimo |
| N2 | Verificación de identidad al cambiar la cuenta (P3) | Volver a ingresar la contraseña + enlace de confirmación al correo registrado |
| N3 | Qué es urgente y su plazo (P7, P10) | Urgente = impide una clase en las próximas 24 h o seguridad grave. Primera respuesta en 4 h hábiles, seguimiento diario |
| N4 | Plazos de resolución: ¿pagos y clases siguen en 2 días hábiles (D4) y el resto en 5 (P7)? | Sí: urgente / pagos y clases 2 / normal 5 / verificaciones 5; primera respuesta en 1 día hábil para todos |
| N5 | Conducta: ¿quién es el responsable y qué activa la ruta urgente? | Los líderes; aviso inmediato al crear el ticket |
| N6 | PDF: guardar el original cifrado (nunca se envía al navegador) y mostrar una imagen con marca de agua | Original igual de 30 días que hoy; máximo 5 MB y pocas páginas; se rechazan PDF con contraseña |
| N7 | ¿2b-3 (avisos, chico) va antes o después de los pasos de pagos? (D14 vs P15) | Después: manda P15 |

### Orden revisado (por aprobar)
| # | Paso | Objetivo | Listo cuando |
|---|---|---|---|
| 0 | **Integrar** | Mergear lo ya revisado y probado: 2b-1, 2b-2, contacto | Está en `main` y la suite pasa |
| 1 | **Saldos correctos** | El saldo solo cuenta clases dictadas (H18); se separan las cuatro cifras de P12 | Ninguna clase futura suma saldo |
| 2 | **Retiros trazables** | Estados Solicitado, Aprobado, Pagado, Fallido y Rechazado; quién, motivo y comprobante; los estados solo avanzan (H1, H5) | Todo retiro tiene responsable y comprobante |
| 3 | **Cuenta bancaria segura** | P2, P3 y N2 (H2 a H4) | Solo se paga a una cuenta propia, verificada y con 48 h |
| 4 | **Liquidación semanal** | P1, P4 y N1: lista semanal vinculada a clases, sin la promesa de 24 a 48 h | El admin paga desde la lista y registra cada comprobante |
| - | *Habilitar retiros reales* | Requiere los pasos 1 a 4, el contador (sección 5) y Webpay en producción | |
| 5 | **2b-3: avisos** | D11, D12, P10, P11 | Avisos de retraso y de documentos enviados |
| 6 | **3a: tickets de usuarios** | Respuestas (H19), primera respuesta y prioridades (P7, N3, N4), pagos y clases, formulario para los tres roles (D10, P9), Webpay fallido (P5) | Un usuario abre un ticket y recibe respuesta dentro del plazo |
| 7 | **3b: resto de reportes** | Técnico, otro, contacto (H14) y conducta restringida (P8, N5) | El admin ya no recibe reportes |
| 8 | **Métricas del admin** | P12, P13, H7 a H9 | Cifras reales con cortes por día, mes y trimestre |
| 9 | PDF | P14, N6 | Se aceptan PDF y se ven con marca de agua |
| 10 | CSS del carrito | H16 | Capturas antes y después sin diferencias |
| 11 | Seguridad S-07 | H17 | Las 6 vistas exigen su rol |

---

## 8. Respuestas del 29-oct, tarde (cierran N1 a N7)

| # | Decisión |
|---|---|
| N1 | **El profesor elige si cobra semanal o mensual.** Semanal: corte el viernes y pago el lunes. El profesor pide el pago (no es automático). Monto mínimo: $10.000; si tiene menos, se acumula. |
| N2 | Cambio de cuenta bancaria: volver a escribir la contraseña + enlace de confirmación al correo registrado. |
| N3 | Urgente = impide una clase en las próximas 24 h o hay un problema grave de seguridad. Primera respuesta en 4 h hábiles y seguimiento diario. |
| N4 | Resolución: urgente 1 día hábil; pagos y clases 2; casos normales 5; verificaciones 5. Primera respuesta en 1 día hábil para todos. |
| N5 | Conducta: la atienden los líderes, con aviso inmediato al crearse el reporte. |
| N6 | PDF: el original se guarda cifrado y nunca se envía al navegador; se muestra como imagen con marca de agua. Máximo 5 MB, pocas páginas, sin PDF con contraseña. |
| N7 | Primero los pasos de pagos y saldos; los avisos de soporte después. **El orden de la sección 7 queda aprobado.** |

### Hecho
| Paso | Rama | Commit | Estado |
|---|---|---|---|
| 1. Saldos correctos (H18) | `fran-saldos-realizados` | `0e9a82c` | Subido; falta abrir y mergear el PR. 487 pruebas OK |
| 2. Retiros trazables (H5) | `fran-retiros-trazables` | `c8f2b0c` | Local, sin subir. Pendiente -> Aprobado -> Pagado / Rechazado; quien, motivo, n.º de operacion |
| 3a. Cuenta bancaria (H4, P2) | `fran-cuenta-bancaria` | `b0829fc` | Local, sin subir. 534 pruebas OK. Una por profesor, banco de `catalogos.BANCOS`, numero cifrado, retiro guarda solo `•••• 1234`, admin ve el completo solo al pagar |

### Diseño del paso 3b (cambio de cuenta, P3 + N2) — hecho en `fran-cuenta-cambio` (`91a16a4`), local, 539 pruebas OK
- Primera cuenta: se registra directo (como en 3a). Cambiar una existente exige la contraseña.
- El cambio no se aplica al tiro: se manda un enlace firmado al correo registrado (vence en 24 h).
  El enlace lleva los datos nuevos con el numero ya cifrado y la fecha de la ultima modificacion de
  la cuenta: sirve una sola vez y deja de servir si la cuenta cambia por otro lado. Sin tabla nueva.
- Abrir el enlace exige estar con sesion del mismo profesor.
- Al confirmar: se guarda `cambiada_en` y se manda un aviso al correo.
- 48 h corridas sin pagar: `marcar_pagado` lo impide y el admin no ve el numero completo mientras tanto.

### Por decidir (pago mensual) — resuelto: F1 a F5 como se sugiere abajo; lunes feriado = siguiente dia habil (31-oct). Hecho en `fran-ciclo-pago` (4a) y `fran-frecuencia-pago` (4b)
| # | Pregunta | Sugerencia |
|---|---|---|
| F1 | Pago mensual: ¿qué día es el corte y qué día se paga? | Corte el último viernes del mes y pago el lunes siguiente (igual que el semanal) |
| F2 | ¿El profesor pide cada pago, o al elegir la frecuencia ya queda programado? (N1 dice "lo pide") | Lo pide antes del corte de su frecuencia |
| F3 | ¿El mínimo de $10.000 vale para ambas frecuencias? | Sí |
| F4 | Si cambia de frecuencia, ¿desde cuándo rige? | Desde el ciclo siguiente, nunca a mitad de uno |
| F5 | ¿Qué frecuencia tiene un profesor nuevo hasta que elija? | Semanal |

Ojo: `docs/POLITICA_PAQUETES.md` (punto 10) dice liquidación semanal. Hay que actualizarla a "semanal o mensual, a elección del profesor", porque P4 exige que la política y la interfaz digan lo mismo.

## 9. Agenda, cancelaciones y mensajes (02-nov)

### Agenda (reemplaza la idea de que el profesor acepte cada reserva)
- El profesor publica un **horario semanal** (ej. lunes y miercoles de 15 a 19 h). El sistema crea solo
  los bloques de las proximas **4 semanas**: **60 min**, **1 alumno** por bloque.
- El alumno elige un bloque libre y **la asignatura** (si el profesor ensena mas de una). La reserva se
  **confirma sola**: la agenda del profesor se va llenando, sin que tenga que aceptar.

### Cancelar y reagendar
- Alumno, con **4 h o mas** de anticipacion: cancela o reagenda directo (otro bloque libre del mismo
  profesor); la clase vuelve al paquete. "Devolucion" = la clase vuelve al paquete, no dinero.
- Alumno, con **menos de 4 h**: pierde la clase y **el profesor cobra**. No puede reagendar.
- Profesor: si necesita cambiar una hora, lo conversa por mensaje. Si no le responden, puede **cancelar
  con al menos 12 h** de anticipacion; la clase vuelve al alumno y se le avisa para reagendar.

### Avisos
- Al profesor: **correo + notificacion en la plataforma** al reservarle, cancelarle o reagendarle.
- Al alumno (o a su apoderado si es menor): **correo + notificacion** cuando el profesor cancela.

### Mensajes
- Alumno **adulto** <-> profesor: chat en la plataforma.
- Alumno **menor**: **no tiene mensajes**. Habla su **apoderado** con el profesor.
- Se **bloquea** enviar telefonos, correos o direcciones, con filtro **moderado** (solo lo que claramente
  es un contacto; los numeros normales como horas o precios pasan). La segunda defensa es el boton Reportar.
- Si alguien **reporta** una conversacion, **soporte puede leerla** (solo desde el ticket, con registro de quien la abre).
- **Reportar (C1c, 02-nov):** boton "Reportar" en la cabecera del chat, de profesor y de alumno adulto. Abre un
  ticket de **Conducta** (aviso inmediato a los lideres, plazo de 2 dias habiles). La persona cuenta lo que paso con
  sus palabras; el texto de la conversacion **no se copia** al ticket. Un reporte abierto por persona; el otro lado
  puede reportar aparte. Lo lee el agente asignado o un lider (como el resto de los tickets), **nunca el admin**, y
  cada lectura queda registrada (agente y hora). El formulario avisa que soporte podra leerla. La conversacion
  reportada **sigue disponible** para los dos: no se bloquea el chat (decision por defecto, facil de cambiar).
  Abierto: si se borra una cuenta (admin_portal) se borran sus conversaciones aunque esten reportadas; definir
  con asesoria legal antes de C1d.
- **Quien puede escribir:** solo quienes tengan una **reserva o un paquete activo** entre ambos.
- **Decisiones del 02-nov tras la respuesta legal (PAQUETE_LEGAL_LBWUS.md, seccion E). Hechas las tres: la 2
  (968963f), la 3 (353507d) y la 1 en C1f-1 (reglas) y C1f-2 (pantalla y avisos):**
  1. Conversaciones reportadas: ya no "nunca se borran". Al cerrar el ticket quedan en **revision pendiente**
     (se conservan, el lider las ve con recordatorio) hasta que el lider registre una retencion excepcional
     (motivo, alcance, responsable, proxima revision, condicion de termino) o las libere (vuelven a la regla de 90 dias).
  2. Al borrar una cuenta, lo conservado **deja de verse para la otra persona**: solo soporte, desde el ticket.
     Se llama seudonimizacion, no anonimizacion (los mensajes pueden contener datos).
  3. Inactividad = dias desde el **ultimo mensaje** (sin mensajes, desde que se creo). Clases futuras, paquete
     vigente, ticket abierto y retencion siguen impidiendo el borrado.
- **Revision de conversaciones reportadas (C1f-1, 02-nov; `mensajes/revision.py`, modelo `DecisionRetencion`):**
  con un ticket de su reporte abierto se conserva; al cerrarse queda *pendiente* (sigue conservada, espera al lider);
  el lider **libera** (vuelve a la regla de 90 dias) o **conserva** como retencion excepcional, registrando motivo
  (reclamacion, autoridad, investigacion u otro), datos que se conservan, fundamento, condicion de termino, y queda
  su nombre; la proxima revision es a **6 meses** (`MESES_REVISION`) y al llegar vuelve a pendiente. Un reporte
  posterior deja sin efecto la decision. Una fila por decision: el historial se conserva. Solo un lider decide, y
  solo lo que esta pendiente. El borrado automatico y el de cuentas usan la misma regla (`retenidas()`): una
  conversacion liberada ya no se retiene al borrar la cuenta.
- **Pantalla del lider y avisos (C1f-2, 02-nov):** menu "Conversaciones reportadas" solo para lideres
  (`mensajes/views_revision.py`): lista de las que esperan decision y de las conservadas (con motivo y proxima
  revision) y un detalle por conversacion con sus reportes, el enlace para leerla (queda registrado quien la abre),
  los formularios de liberar y de conservar, y el historial de decisiones. Se ven solo nombres de pila. La campanita
  del lider avisa "N conversaciones reportadas por revisar" (urgente tras 3 dias habiles esperando). Recordatorio por
  correo a los lideres (`manage.py avisar_revisiones_pendientes`, cron diario, solo dias habiles): el primer dia
  habil de espera y despues cada 3 dias habiles, un correo por lider con la cantidad, sin nombres ni contenido.
- **Segundo apoderado de un menor ya registrado (A1 a A3, 02-nov, opcion A elegida):** el segundo apoderado
  (con la identidad verificada) pide el vinculo con el RUT del menor, el parentesco y el documento que lo acredita;
  soporte lo verifica como cualquier vinculo (marca "Pedido con el RUT" en su revision) y, mientras esta pendiente,
  no autoriza nada. Privacidad: la busqueda prueba las variantes del RUT y todo fallo (no existe, es adulto, cuenta
  inactiva) responde lo mismo; el nombre del menor no se muestra al que pidio hasta que soporte verifique (tambien
  si lo rechaza). El apoderado ya vinculado recibe un correo de aviso, sin decir quien es, su parentesco ni su
  contacto, y sin poder vetarlo (la decision es de soporte, con documentos). La contrasena del menor la cambia solo
  quien creo la cuenta (su primer vinculo); si ese vinculo se revoca, la maneja soporte. El aviso al adolescente se
  decidio despues (punto siguiente, R2).
- **Apoderados, decisiones del 02-nov (R1 a R5):** (1) al revocarse un vinculo: si lo revoca soporte, el revocado
  recibe el motivo; si estaba verificado, se avisa a los demas apoderados verificados y al adolescente de 14 a 17
  con correo propio, sin el motivo ni quien era (retirar una solicitud pendiente no avisa a nadie). (2) El
  adolescente de 14 a 17 con correo propio tambien se entera si alguien pide ser su apoderado (antes de los 14,
  ningun aviso al estudiante). (3) Puede volver a pedir el vinculo el rechazado y quien se desvinculo solo; si lo
  revoco soporte, por soporte. Se reutiliza el mismo vinculo y su historial (varias revocaciones por vinculo).
  (4) Limites: 5 busquedas sin resultado en 24 h y 3 solicitudes con RUT pendientes a la vez. (5) La clave del
  menor sigue en manos de soporte si el primer vinculo se revoca; quien vuelve con el RUT no la recupera.
- **Borrado de cuenta con conversaciones reportadas (C1e, 03-nov):** antes, eliminar un usuario arrastraba en
  cascada todas sus conversaciones, tambien las reportadas y tambien para la otra persona. Ahora
  (`mensajes/supresion.py`): sin conversaciones reportadas se borra todo como siempre; con alguna, se borran las
  demas conversaciones y los avisos, y **la cuenta se anonimiza en el mismo lugar** ("Cuenta eliminada": sin nombre,
  correo, RUT, telefono, direccion, nacimiento, genero ni foto, desactivada, `CustomUser.suprimida`). Lo reportado
  se conserva, la otra persona lo lee sin poder escribir, soporte lo sigue leyendo y no se borra por inactividad.
  Se aplico en el unico borrado que existe (admin, alumnos). **Abierto:** profesores y apoderados guardan mas datos
  propios (documentos, cuenta bancaria) y habria que anonimizarlos tambien antes de usarla con ellos; los datos de
  clases y pagos de una cuenta anonimizada no se tocan (registros aparte; conservacion por definir con asesoria
  legal); no existe aun un flujo para que el propio usuario pida su supresion. **Ampliado por S1 (punto siguiente).**
- **Borrar una cuenta no borra sus pagos ni sus clases (S1, 02-nov, `107bef3`):** bug del borrado del admin: borrar
  al alumno arrastraba en cascada sus paquetes pagados, suscripciones e inscripciones; se perdia el registro del pago
  y al profesor le bajaban las ganancias hacia atras. Ahora `suprimir_cuenta` **seudonimiza** la cuenta si tiene
  historial de pagos o clases (igual que con conversaciones reportadas) y solo la borra completa si no tiene ni eso
  ni conversaciones retenidas. Los chats no retenidos y los avisos se borran igual. Mensaje del admin actualizado.
  **Abierto:** cuanto tiempo se conserva ese historial (definir con asesoria legal).
- **El usuario pide eliminar su cuenta (E3 de la respuesta legal; app `supresiones`, 03-nov):** desde "Ayuda y soporte"
  > "Eliminar mi cuenta" (alumno, profesor o apoderado adultos; el alumno menor no: su apoderado habla por el).
  Flujo, segun los 6 pasos de la abogada: (1) **constancia**: al confirmar se crea una `SolicitudSupresion` (numero,
  fecha, rol; sin datos personales, sobrevive al borrado de la cuenta) y su ticket de la categoria nueva **Privacidad y
  datos**, con correo de recepcion (numero, fecha y plazo). (2) **identidad proporcional, sin carnet**: sesion abierta +
  enlace firmado al correo registrado (24 h; sirve igual con Google); abrir el enlace solo pregunta, la solicitud se crea
  al confirmar (POST). (3) **evaluar por categoria** (`supresiones/evaluacion.py`, misma regla que `suprimir_cuenta`): que
  se elimina, que se conserva y que **impide eliminar hoy** (clase reservada por dictar, clases pagadas sin usar en
  paquete vigente, plan vigente, otro ticket abierto). (4) **eliminar y restringir**: lo ejecuta el agente asignado
  (no el lider sin reasignarse; no se deshace), solo sin bloqueos y marcando que reviso la evaluacion; usa
  `suprimir_cuenta` (borra completa o seudonimiza). (5) **comunicar el resultado**: correo con lo eliminado y lo
  conservado, a los datos copiados antes de eliminar; si no sale, se avisa al agente. Si hay un bloqueo o no
  corresponde, el agente **rechaza** explicando (queda en el ticket que el usuario lee) y el usuario puede volver a pedirlo.
  (6) **proveedores y respaldos**: sin pasos automaticos; el panel lo recuerda. Decisiones por defecto, faciles de
  cambiar y **por validar con la abogada**: plazo de 10 dias habiles (`Ticket.DIAS_HABILES`), los bloqueos, y que la cuenta
  siga activa mientras se revisa. **Hoy solo se ejecuta para alumnos**: profesores y apoderados pueden pedirlo, pero el
  agente no puede ejecutarlo hasta definir como se seudonimizan sus datos propios (documentos, cuenta bancaria).
  **Al desplegar:** habilitar al menos un agente en la categoria Privacidad (`crear_soporte --categorias privacidad`).
- **Registro de supresiones (E4 de la respuesta legal, 03-nov; `supresiones/registro.py`):** para no reponer en servicio
  a quien ya se elimino si se restaura un respaldo. (1) `registro.eliminar(user)` es el **unico camino** para eliminar una
  cuenta (solicitud del usuario y borrado del admin): anota una huella del RUT y otra del correo y aplica
  `suprimir_cuenta`. Las huellas son **HMAC-SHA256 con clave** (`SUPRESIONES_CLAVE`; sin ella se deriva de `SECRET_KEY`):
  un hash sin clave de un RUT se adivina probando los pocos RUT posibles. Se normalizan (RUT con o sin puntos, correo en
  minusculas). (2) **El registro no puede vivir solo en la base**: restaurar un respaldo lo devuelve a como estaba y
  perderia justo las supresiones posteriores. Por eso `manage.py exportar_supresiones RUTA.json` (cron diario) lo saca a un
  archivo que se guarda **fuera de la base**. (3) Tras restaurar y **antes de reabrir el servicio**:
  `manage.py reaplicar_supresiones --archivo RUTA.json` (con `--simular` solo cuenta). Elimina de nuevo las cuentas que
  coinciden por RUT **o** correo y que se crearon **antes** de la supresion: quien se registro otra vez despues no se toca.
  Las salidas de los comandos solo traen cantidades. **Decisiones por defecto, a validar con la abogada:** coincidir por
  RUT o por correo (basta uno), y cuanto tiempo se conservan las huellas y el archivo (hoy, sin limite: son datos de
  personas, aunque seudonimizados). **Si `SUPRESIONES_CLAVE` (o `SECRET_KEY`) cambia, el registro deja de reconocer a las
  personas ya eliminadas:** definirla aparte y guardarla con los respaldos, nunca en la base. No cubre cuentas que
  se eliminaron antes de este cambio (no dejaron huella): hoy no hay datos reales.
- **Aviso previo al chat (E5, 03-nov; `mensajes/templatetags/mensajes_tags.py`):** un aviso en las tres bandejas (alumno,
  profesor, apoderado) que dice para que sirven los mensajes, que un filtro automatico (sin que lea una persona) bloquea
  datos de contacto, quien puede leerlos (las partes; soporte solo si se reporta, desde el ticket y con registro; el
  administrador no), que los avisos por correo no traen el mensaje, cuanto se conservan y la retencion excepcional, y como
  ejercer los derechos. Va **desplegado antes de abrir una conversacion** y plegado dentro de ella. Los plazos salen de
  `retencion.DIAS_SIN_ACTIVIDAD` y `revision.MESES_REVISION`: no hay cifras escritas en el HTML. El estudiante menor, que
  no escribe, ve una version en lenguaje simple en su portal. **No es un consentimiento**: es informacion, sin casilla
  ni boton de aceptar. **A validar con la abogada:** el canal de derechos hoy apunta a *Ayuda y soporte* y a *Eliminar mi
  cuenta*; falta el canal formal (correo o formulario con un responsable) y, cuando exista, cambiar el texto.
- **Registro de requerimientos de autoridad (E6, 03-nov; app `requerimientos`):** cuando un tribunal, la fiscalia u otra
  autoridad pide datos de usuarios. **Solo lideres de soporte** (ni agentes comunes ni el admin). Estados que solo
  avanzan: recibido -> verificado -> cerrado, o rechazado. **No se entrega nada sin verificar**: verificar exige marcar
  tres controles (la autoridad es quien dice ser, es competente y cita su fundamento, se entregara solo lo necesario) y
  escribir como se verifico. Cada paso guarda quien y cuando; las entregas (que, por que medio, a quien) son filas que
  no se editan. **No copia datos personales ni documentos**: describe categorias de datos y se refiere a las personas
  por numero de ticket. Marca los requerimientos que pasaron su plazo. **Decisiones mias, a validar con la abogada:** los
  tres controles de la verificacion y que solo los lideres lo gestionen. No avisa por correo cuando se acerca el plazo.
- **Eliminacion de cuentas de profesores y apoderados (paso 5, 03-nov; `supresiones/datos_propios.py`):** profesores y
  apoderados pasan por el mismo `suprimir_cuenta` que los alumnos. **Profesor:** borrar la cuenta arrastraria sus clases,
  sesiones e inscripciones (historial de otros alumnos), asi que si tiene clases con inscripciones, paquetes o retiros
  se **seudonimiza**; si no, se borra. Siempre se le quitan el titulo, la cuenta bancaria y el horario, se cancelan sus
  clases futuras sin reservas y sale del catalogo (queda sin titulo aprobado). **No se puede eliminar hoy** si tiene clases
  reservadas por dictar, clases pagadas sin usar por alumnos con el, saldo disponible para retirar o retiros en tramite.
  **Apoderado:** se seudonimiza si tiene compras o un vinculo que llego a estar verificado (quien tuvo autoridad sobre un
  menor); se le quitan el carnet y los certificados, y su correo en las invitaciones que guardan los estudiantes. **No se
  puede eliminar** mientras sea el apoderado verificado de un menor: antes hay que desvincularse (si no, el estudiante
  quedaria sin apoderado). **Hueco cerrado para todos los roles:** `EmailAddress` y `SocialAccount` (allauth) guardaban el
  correo y los datos de Google aun con la cuenta seudonimizada, y la foto (o el titulo antiguo) del disco no se borraba
  al borrar la cuenta por completo. **Decisiones mias, a validar con la abogada:** cuando un apoderado queda
  seudonimizado en vez de borrado, y cuanto se conserva el historial (igual que el de los alumnos: por definir con el
  contador).
- **Avisos:** campanita + correo generico ("tienes un mensaje nuevo", sin el contenido). Se avisa al cambiar el
  turno, **o si pasaron mas de 12 h desde el ultimo aviso enviado a esa persona** (no desde el ultimo mensaje; 03-nov).
  Las 12 h son una decision funcional, no un plazo legal. Las cancelaciones y reagendamientos avisan aparte.
- **Menores:** cada apoderado con vinculo verificado tiene **su propia conversacion** con el profesor.
  El profesor ve "Apoderado de <nombre de pila del menor>". Si el vinculo se revoca, queda de solo lectura.
- **Apoderado (C2, 02-nov):** pagina **Mensajes** enlazada en su portal. Escribe solo con un vinculo vigente
  (`Vinculo.autoriza`) y con reserva o paquete del menor con ese profesor. **Solo lectura, para los dos lados**, si
  el vinculo se revoca, el apoderado se rechaza o el estudiante cumple 18 (ahi el estudiante abre la suya). Al
  profesor nunca le llega ni ve el nombre del apoderado (aviso y bandeja dicen "Apoderado de <menor>"). El profesor
  puede iniciar desde Mi Agenda ("Escribir al apoderado"): abre una conversacion con **cada** apoderado vigente y
  avisa si son varios. El reporte del apoderado marca al estudiante (D18). **Abierto:** madre y padre del mismo
  menor aparecen al profesor con el mismo nombre ("Apoderado de Ana"); se distinguen solo por la hora y el ultimo
  mensaje. Si se quiere distinguirlos, mostrar el parentesco (madre/padre/tutor).

### Retencion de mensajes (02-nov)
Finalidad: coordinar las clases. Un plazo se justifica por esa finalidad, no por comodidad tecnica
(Ley 19.628 art. 6; reforma desde el 01-dic-2026: conservar solo el tiempo necesario). **Validar con
asesoria legal** y comunicarlo en la politica de privacidad y en la pantalla de mensajes.

| Situacion | Regla |
|---|---|
| Conversacion normal | Se borra a los **90 dias de inactividad**, si no hay clases futuras ni gestiones pendientes (reserva futura, paquete activo, ticket abierto) |
| Reportada o ligada a una disputa | **Se suspende el borrado** y se restringe el acceso (solo soporte) |
| Ticket cerrado | **No se borra solo.** El jefe de soporte revisa si corresponde mantener la evidencia y lo registra |
| Investigacion o requerimiento de autoridad | Se conserva lo pertinente, con fundamento, plazo de revision y registro |

**Inactividad** = dias desde el **ultimo mensaje** (sin mensajes, desde que se creo). **Cambiado el 02-nov** tras la
respuesta legal: antes contaba tambien la ultima clase; ahora una clase ya dictada no extiende la conservacion y una
clase futura reservada impide borrar.

**Implementado (C1d, 02-nov):** `python manage.py borrar_conversaciones_inactivas` (con `--simular` solo cuenta).
Cron diario en el despliegue, igual que `generar_bloques`. Sin mensajes ni clases cuenta desde que se creo; una
clase futura cuenta como actividad. No borra si hay paquete vigente entre las partes, ticket abierto de cualquiera
de las dos (puede demorar unos dias hasta que soporte lo cierre) ni reporte (aunque su ticket este cerrado). La
salida solo trae cantidades. **Aun no existe:** (1) la pantalla donde el lider revisa y registra su decision sobre
una conversacion reportada con ticket cerrado: hoy esas **nunca** se borran solas; (2) la **retencion especial**
por investigacion o requerimiento de autoridad (fundamento, plazo de revision y registro); (3) que el borrado de
una cuenta respete las conversaciones reportadas.

### Privacidad
- El alumno no ve datos personales del profesor: se quita el telefono (y la casilla "hacer publico").
- El profesor solo ve el **nombre de pila** del alumno.

### Orden de trabajo (rama `fran-agenda`, un commit por paso)
A1 quitar telefono del profesor -> A2 regla de 4 h (cancelar/reagendar; tarde = profesor cobra) ->
A3 profesor cancela con 12 h -> B1 horario semanal y bloques -> B2 notificaciones (campanita + correo) ->
C1 mensajes alumno adulto <-> profesor -> C2 mensajes apoderado <-> profesor (menor sin mensajes).
