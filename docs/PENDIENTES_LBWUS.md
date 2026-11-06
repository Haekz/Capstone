# LBWUS: pendientes para despues de subir los PR

Actualizado: 02-nov-2026. Ninguno bloquea los 10 PR; todos se hacen en ramas nuevas desde `main`.

## Plan aprobado: soporte y pagos (detalle y decisiones en DECISIONES_SOPORTE_Y_PAGOS.md)
Por mergear en GitHub: `fran-soporte-2b1` -> `fran-soporte-2b2` -> `fran-contacto` -> `fran-saldos-realizados`.

| # | Paso | Estado |
|---|---|---|
| 0 | Integrar las ramas de arriba | Falta mergear |
| 1 | Saldos correctos: solo cuentan clases dictadas | Hecho en `fran-saldos-realizados` (0e9a82c) |
| 2 | Retiros trazables: quien, motivo, n.º de operacion, estados que solo avanzan | Hecho en `fran-retiros-trazables` (c8f2b0c), local |
| 3a | Cuenta bancaria: una por profesor, mismo RUT, cifrada, enmascarada | Hecho en `fran-cuenta-bancaria` (b0829fc), local. 534 pruebas OK |
| 3b | Cambio de cuenta: contrasena + enlace al correo + aviso + 48 h | Hecho en `fran-cuenta-cambio` (91a16a4), local. 539 pruebas OK |
| 4a | Corte viernes, pago lunes (o siguiente dia habil), minimo $10.000 | Hecho en `fran-ciclo-pago` (fe84f24), local. 544 pruebas OK |
| 4b | El profesor elige semanal o mensual; rige desde el ciclo siguiente; politica actualizada | Hecho en `fran-frecuencia-pago` (3571eb2), local. 552 pruebas OK |
| - | Retiros con dinero real: requiere 1 a 4, contador y Webpay en produccion | Codigo listo (pasos 1 a 4); falta contador y Webpay en produccion |
| 5 | 2b-3: avisos de retraso y de documentos por vencer | Hecho: 5a (afd5167), 5b (c84455c), 5c (9395336), local. 566 pruebas OK |
| 6 | 3a: tickets de usuarios (respuestas, prioridades, pagos y clases) | En curso. Decisiones D16 a D20 (31-oct) |
| 6a | El usuario abre ticket (Pagos, Clases, Tecnico, Otro) y lo ve; el agente lo recibe | Hecho en `fran-tickets-usuarios` (42716cb), local. 576 pruebas OK. Migracion soporte 0004 |
| 6b | Conversacion: respuestas, cierre y correos | Hecho en `fran-tickets-usuarios` (9815ab7), migracion soporte 0005. 583 pruebas OK. 6a y 6b se suben JUNTAS |
| 6b-plazo | DECIDIDO 31-oct: el plazo de un ticket de usuario se cumple con la primera respuesta del agente | Hecho (56428e4), migracion soporte 0006. 585 pruebas OK |
| 6c | Aviso de atraso AL USUARIO cada 3 dias habiles (D11) | Hecho (3a2e4dd). 588 pruebas OK. Tambien a apoderados/profesores en verificacion |
| 6d-menores | D18 revisada (01-nov): el menor NO abre tickets ni usa el canal viejo; su portal le dice que avise a su apoderado | Hecho (b304272) |
| 6d-puente | D21: menor califica con 1-2 estrellas -> aviso al apoderado sin el comentario | Hecho (6aa6bce) |
| 6d | Conducta: categoria restringida, 2 dias, aviso diario, aviso inmediato a lideres (D17, N5) | Hecho (7a85085), migracion soporte 0007. 595 pruebas OK |
| 6d-estudiante | El apoderado indica de que estudiante se trata el ticket | Hecho (564fc42), migracion soporte 0008. 599 pruebas OK |
| D22 | Linea de ayuda externa en el portal del menor | HECHO (02-nov): 147 Fono Ninos y 149 Fono Familia, validados en ChileAtiende. El *4141 no se valido: no se publica |
| 6e-1 | Retirar el formulario viejo "Soporte / Reportes" del portal (enviar_reporte) | Hecho (a088ada). 601 pruebas OK. Historial de reportes queda solo lectura |
| 6e-2 | Reportes viejos pendientes -> tickets (comando) y el admin deja de ver/resolver reportes (D23) | Hecho (e5350bc comando, 88df794 admin). 603 pruebas OK. **Al desplegar: correr `manage.py pasar_reportes_a_tickets` una vez** |
| 6e-limpieza | CSS de reportes sin uso en admin_panel.css y textos de home_adm | Hecho (d9abd67) |
| D17-disculpa | Conducta: aviso al equipo diario, disculpa al usuario cada 3 dias habiles | Hecho (0d1a25f). 610 pruebas OK |
| 6e-3b | Boton "Reportar problema con este pago" tras rechazo de Webpay, con la orden precargada (4.7) | Hecho (872f400). 607 pruebas OK |
| 6e-3a | Bandeja de contacto pasa del admin a soporte (H14) | Hecho (05-nov, `fran-contacto-soporte`): cada mensaje de Contactanos es un ticket de la categoria Contacto (5 dias habiles); el agente responde y al visitante le llega la respuesta por correo (sin citar su mensaje: el correo no esta verificado), o lo cierra sin responder si es spam. El admin ya no tiene la pagina Contactos. Migracion soporte 0010. **Al desplegar: habilitar al menos un agente en la categoria Contacto** (`manage.py habilitar_soporte <RUT> --agregar contacto`; el comando tambien quita temas con `--quitar`) |
| login-next | El login no respeta `?next=`: quien llega sin sesion al boton de pago pierde la orden precargada | Hecho (04a5e66), con `destino_seguro`. 609 pruebas OK. Matriz ID-23 |
| 7 | 3b: resto de reportes a soporte, conducta solo lideres | Hecho con 6d, 6e y H14 (tecnico/otro y contacto son tickets, conducta restringida, admin sin reportes) |
| 8 | Metricas del admin (ganancias reales, ingresos, registros) | Completo segun DECISIONES (P12, P13, H7, H8, H9). En `fran-metricas-admin-2`: 8d H8 personas que entran por dia, solo el numero por rol, sin guardar quien (4484963, migracion admin_portal 0001); 8e P12 comision estimada y saldo disponible de profesores (8ec534b); 8f P13 soporte en cifras sin contenido (c7dfb23); 8g H9 registros por dia/mes/trimestre (f13d492). Queda opcional: historial de personas por dia (hoy solo la tarjeta de hoy). Hecho antes en `fran-metricas-admin`: 8a finanzas reales (cobrado, ganancia LBWUS = 15% de clases dictadas, por dictar; segun POLITICA_PAQUETES), 8b grafico de registros reales por mes, 8c-1 campana del admin con plazos de retiros (fuera avisos falsos), 8c-2 campana del agente de soporte (sus tickets atrasados / por vencer), 8c-3 lider (tickets sin agente, incluidos los de agentes sin la categoria, y atrasos del equipo). En `fran-pendientes-chicos`: resenas reportadas en la campana del admin (45476ef) y `planes_adm.html` con los paquetes reales (769cd7f) |
| 9 | PDF: original cifrado + imagen con marca de agua | Hecho en `fran-pdf-protegido` (decidido 02-nov: apoderados y titulos; titulos cifrados en la base; original del titulo se borra al decidir; maximo 3 paginas). 9a apoderados aceptan PDF (a8d5011); 9b-1 titulos cifrados en la base, migracion alumnos 0018 (f847cb2); 9b-2 comando `pasar_titulos_a_base` (24c6244). **Al desplegar: instalar requirements (pypdfium2), `migrate` y correr una vez `manage.py pasar_titulos_a_base`.** FALTA 9b-3 (despues de ese deploy): quitar `titulo_archivo` y actualizar `usabilidad/verificar_google_titulo.py` |
| 10 | CSS muerto del carrito | Hecho en `fran-css-carrito` (styles.css, alumn_1.css, planes.css). Restos fuera del CSS (orden_pendiente con carrito en `test_flujos_funcionales`, flujo `/alumnos/pago` en `usabilidad/recorrido.py`) retirados en `fran-pendientes-chicos` (03a514b) |
| 11 | Seguridad S-07 (punto 1) | Hecho (05-nov, `fran-reservas-rol`, 67ec6b6): `@alumno_required_json` en las tres vistas de reserva. 1365 pruebas OK |
| 12 | Escalar casos graves (D5 revisada 05-nov) | Hecho (05-nov, `fran-contacto-soporte`): boton "Escalar" en el panel y en el ticket, con motivo obligatorio. Agente -> lider (el ticket pasa al lider con menos carga); lider -> administrador (bandeja "Casos escalados" + campana urgente; el admin deja una indicacion obligatoria, el ticket sigue en soporte). Migracion soporte 0011 |

### Commits por subir, en orden (no subir hasta que Fran lo pida)
Cada rama sale de la anterior; subirlas y mergearlas en este orden. Comando: `git push -u origin <rama>`.

| Orden | Rama | Commit | Que hace | Migracion | Subido |
|---|---|---|---|---|---|
| 1 | `fran-soporte-2b1` | 23d1551, 5c07924 | Roles, tickets y asignacion de soporte | 0012 | Si |
| 2 | `fran-soporte-2b2` | 27ee561 | Plazos, correos y cron de atrasos | - | Si |
| 3 | `fran-contacto` | 97526a9 | Formulario de contacto persistente | - | Si |
| 4 | `fran-saldos-realizados` | 0e9a82c | Saldo solo con clases dictadas | - | Si |
| 5 | `fran-retiros-trazables` | c8f2b0c | Paso 2: retiros trazables | 0013 | No |
| 6 | `fran-cuenta-bancaria` | b0829fc | Paso 3a: cuenta bancaria cifrada | 0014 | No |
| 7 | `fran-cuenta-cambio` | 91a16a4 | Paso 3b: cambio de cuenta seguro | 0015 | No |
| 8 | `fran-ciclo-pago` | fe84f24 | Paso 4a: corte, dia de pago y minimo | 0016 | No |
| 9 | `fran-frecuencia-pago` | 3571eb2 | Paso 4b: frecuencia semanal o mensual | 0017 | No |
| 10 | `fran-avisos-atraso` | afd5167 | Paso 5a: aviso de atraso cada 3 dias habiles | - | No |
| 11 | `fran-avisos-documentos` | c84455c | Paso 5b: aviso al agente 5 dias antes del borrado | apoderados 0007 | No |
| 12 | `fran-documentos-vencidos` | 9395336 | Paso 5c: al vencer, cerrar ticket y volver a subirlos | - | No |
| 13 | `fran-tickets-usuarios` | 42716cb, 9815ab7, 56428e4, 3a2e4dd, b304272, 6aa6bce, 7a85085, 564fc42, a088ada, e5350bc, 88df794, 872f400, 04a5e66, d9abd67, 0d1a25f | Pasos 6a-6e (menos H14) + login next + limpieza | soporte 0004-0008 | No |
| 14 | `fran-claves-registro` | cdd6dc9 | Seg-3: clave distinta del RUT y del correo en los tres registros. 613 pruebas OK | - | No |
| 15 | `fran-css-carrito` | fb26d5d | Paso 10: CSS del carrito retirado. 613 pruebas OK | - | No |
| 16 | `fran-metricas-admin` | 9bab11f, d25b8af, f8901e0, c465229, ad85b81, 5348e19 | Paso 8: valor_clase a paquetes, finanzas reales, grafico de registros, campana por rol (admin, agente, lider). 647 pruebas OK | - | No |
| 17 | `fran-pendientes-chicos` | 45476ef, 769cd7f, 03a514b, 4071d81 | Campana: resenas reportadas; planes del admin reales; restos del carrito; clave del form admin con el helper. 650 pruebas OK | - | No |
| 18 | `fran-metricas-admin-2` | 4484963, 8ec534b, c7dfb23, f13d492 | Resto del paso 8: H8 personas por dia, P12, P13, H9. Incluye migracion admin_portal 0001 | - | No |
| 19 | `fran-pdf-protegido` | a8d5011, f847cb2, 24c6244 | Paso 9: PDF en apoderados y titulos cifrados con marca de agua | alumnos 0018 | No |
| 20 | `fran-retiros-antiguos` | 9721a83, 8c9bd30, 20efbcf | Retiros antiguos enmascarados; registro de quien abre cada titulo (solo lider lo ve); personas que entran por dia/mes/trimestre (promedio diario) | alumnos 0019 (datos, irreversible), admin_portal 0002 | No |
| 21 | `fran-agenda` (en curso) | 960d3d3 ... 107bef3 (32 commits; lista completa: `git log --oneline fran-retiros-antiguos..fran-agenda`) | Agenda (DECISIONES seccion 9): A1 sin telefono del profesor; A2 regla de 4 h (cancelada_tarde: se pierde la clase y el profesor cobra); B2a campanita (app notificaciones); B2b aviso al profesor por correo + campanita; B1a el profesor no puede estar en dos clases a la vez; B1b horario semanal y bloques de 4 semanas (app agenda, comando diario generar_bloques); B1c seccion Mi Agenda en el panel; A3a campanita en el panel del alumno; A3b el profesor cancela con 12 h (la clase vuelve al paquete, se cierra esa hora, avisa al alumno o apoderado). Mensajes (C1 y C2) completos: alumno adulto y apoderado de un menor con el profesor, reportar con lectura de soporte, borrado a los 90 dias (`borrar_conversaciones_inactivas` y `avisar_revisiones_pendientes`, **programar ambos a diario en el despliegue**), re-aviso a las 12 h C1e: eliminar un alumno con conversaciones reportadas seudonimiza la cuenta y deja lo reportado solo para soporte (antes se borraba en cascada), inactividad solo desde el ultimo mensaje, y C1f: el lider revisa lo reportado al cerrarse el ticket (libera o conserva como retencion excepcional con revision a 6 meses; pantalla, campanita y recordatorio). **Hecho 03-nov (respuesta legal E5, E6 y paso 5; ver DECISIONES): aviso previo al chat en las 3 bandejas y version simple para el menor (37609d4); registro de requerimientos de autoridad, solo lideres, app `requerimientos` (7beb4ae, migracion requerimientos 0001); eliminacion de cuentas de profesores y apoderados (`supresiones/datos_propios.py`; ademas la limpieza de allauth y de los archivos del disco corre al borrar o seudonimizar a cualquier rol). Al desplegar: migrar y listo; el aviso lee los plazos del codigo. Suite completa: 1127 pruebas OK (6 saltadas).** Sin hacer, ligado a mensajes (decidido 02-nov, ver DECISIONES): decidir si al profesor se le distingue madre/padre del mismo menor (hoy ambos salen como "Apoderado de <menor>"). Pendiente fuera de desarrollo (PAQUETE_LEGAL_LBWUS.md): responsable del tratamiento, proveedores reales, respaldos, correo de derechos y plazos contables. Otras maquetas del panel del alumno sin conectar a datos reales: `myClasses`, `teacherFeedback` y `subjectProgress` en Alumno_pag1.html; y en `panel_profesor.html` el chat del directo trae mensajes de demostracion fijos (`mockMessages`, "Juan Perez"). S1 (107bef3): eliminar una cuenta ya no borra sus pagos ni sus clases; se seudonimiza si tiene historial y solo se borra completa si no tiene historial ni conversaciones retenidas (cuanto se conserva, por definir con asesoria legal). 989 pruebas OK (02-nov). **E3 (03-nov, app `supresiones`, commits 871c21a y b301da8): el usuario pide eliminar su cuenta** (Ayuda y soporte > Eliminar mi cuenta): constancia, identidad por enlace al correo, evaluacion por categoria, ejecucion o rechazo por soporte y correo con el resultado; categoria de ticket nueva Privacidad (10 dias habiles), migraciones soporte 0009 y supresiones 0001. Solo se ejecuta para alumnos (profesores y apoderados: falta definir como se seudonimizan). 1035 pruebas OK. **Al desplegar: habilitar al menos un agente en la categoria Privacidad.** **E4 (03-nov, commit 3c26ade, migracion supresiones 0002): registro de supresiones** (huellas con clave del RUT y el correo; `exportar_supresiones` y `reaplicar_supresiones`). 1063 pruebas OK. **Al desplegar: definir `SUPRESIONES_CLAVE`, programar `exportar_supresiones RUTA` a diario guardando el archivo FUERA de la base, y tras restaurar cualquier respaldo correr `reaplicar_supresiones --archivo RUTA` antes de reabrir el servicio.** Al desplegar: programar `generar_bloques` una vez al dia | alumnos 0020, 0021, 0022; notificaciones 0001; agenda 0001; mensajes 0001-0005, apoderados 0008-0009 | No |

Paso 5b HECHO en `fran-avisos-documentos` (559 pruebas OK): aviso unico al agente del ticket **5 dias antes** de que se
borren los documentos (decidido 31-oct), sin datos personales; sin agente, a los lideres.
Paso 5c HECHO en `fran-documentos-vencidos` (9395336, 566 pruebas OK): hallazgo: hoy el carnet solo se sube al registrarse y el documento del
vinculo al aceptar la invitacion; si se borran sin revisar, el apoderado queda atascado. Decidido (31-oct): al
vencer se cierra el ticket, se avisa al apoderado y su portal le pide subirlos de nuevo; al subirlos se abre un
ticket nuevo con plazo nuevo.

Notas: los retiros de prueba antiguos guardan el numero de cuenta sin cifrar (decidir si se enmascaran).
Si cambia SECRET_KEY, las cuentas bancarias cifradas dejan de leerse.
Archivos sobre 600 lineas: en curso en `fran-dividir-archivos`. Fase 1 Python HECHA: `alumnos/views.py`, `alumnos/models.py`
(paquete `alumnos/models/` con usuarios, clases, pagos, reportes y retiros) y `apoderados/views.py` (la revision de
soporte paso a `apoderados/views_revision.py`; el flujo del adolescente se queda porque comparte helpers del registro).
Fase 2 plantillas HECHA: `Alumno_pag1.html` (1478 -> 105; partes en `alumnos/includes/panel/`, y el JS en `panel/js/`,
incluido dentro del mismo `<script>`), `dashboard_admin.html` (836 -> 170; `admin_portal/includes/dashboard/`) y
`panel_profesor.html` (790 -> 393; `user_profesor/includes/panel/`). Verificado sin navegador: el HTML generado (alumno con
clases, sin clases y menor, profesor y admin) es identico al de antes.
Fase 3 CSS HECHA: `alumn_1.css` (10 partes), `styles.css` (9), `admin_panel.css` (5), `pago.css` (3) y `panel.css` (2)
pasan a carpetas con su mismo nombre (`alumnos/css/alumn_1/01_base.css`...; `panel.css` a `user_profesor/panel/`), una
parte por capa. Unidas en orden dan el original byte a byte, y la pagina las carga en ese orden: la cascada no cambia
(en el HTML solo cambian los `<link>`). `recuperar.css` (685) se queda: es una sola hoja que cargan 7 plantillas.
CSS muerto probable, sin borrar: `pago/03_rediseno_checkout.css` (385 lineas, "solo pagina de pago"): 30 de sus 31 clases
no estan en ninguna plantilla. Es lo que quedo del checkout `/alumnos/pago`, y solo `confirmacion.html` carga esas hojas.
Bug visto, sin arreglar: en `dashboard_admin`, "ultimos alumnos/profesores" (`alumnos[:3]`) no tiene `order_by`: muestra 3
cualesquiera, no los ultimos, y la tabla de usuarios cambia de orden entre cargas.
Doc pendiente de corregir: CONCILIACION_Y_TRANSBANK_7_6.md describe un modelo `Pago` que no existe.
El enlace de cambio de cuenta exige sesion: si el profesor no la tiene, entra y vuelve a abrir el enlace.
Decidido (31-oct): si el lunes de pago es feriado, se paga el siguiente dia habil (`alumnos/liquidacion.py`).

## Seguridad
1. **HECHO (05-nov, `fran-reservas-rol`): vistas de alumno sin decorador de rol (resto de S-07).** `inscribir_clase`,
   `listar_sesiones_disponibles` y `reservar_sesion` usan `@alumno_required_json`; `iniciar_directo` ya tenia
   `@profesor_required_json` y `sala_virtual` ya bloqueaba cuentas inactivas.
   Documentado en docs/MATRIZ_IDENTIDAD.md.
2. **Confirmar en Railway la IP real.** S4-02 asume que Railway agrega la IP del cliente AL FINAL de
   `X-Forwarded-For`. Verificarlo en un deploy real (log de la cabecera en un login de prueba).
3. **HECHO (01-nov, `fran-claves-registro`): contrasenas del registro de profesor, "crear administrador" y
   tambien el registro publico de alumnos.** Llamaban a `validate_password` sin usuario: clave = RUT (con o sin
   puntos) o = correo pasaba. Ahora usan `alumnos.utils.validar_clave_nueva`. Matriz ID-24.
   HECHO tambien (4071d81, `fran-pendientes-chicos`): el formulario del admin (S4-02) usa el mismo helper.
   HECHO tambien (05-nov, `fran-dividir-archivos`): `apoderados/forms.py` (_CuentaForm) usa el helper, que
   ahora acepta `nombre` opcional para no perder la comparacion con first_name; prueba nueva en
   `Seg3ClaveIgualAlRutTests.test_registro_de_apoderado` (antes el apoderado no tenia prueba de Seg-3).

## Apoderados y menores
4. **Segundo padre vinculandose a un menor ya registrado: HECHO** (02-nov, `fran-agenda`, pasos A1 a A3). Pide
   el vinculo con el RUT del menor y el documento (Apoderado > Vincularme a un estudiante ya registrado); soporte lo
   verifica; el apoderado ya vinculado recibe un aviso sin datos de quien pidio (sin veto); la contrasena del menor
   solo la cambia quien creo la cuenta. Ver DECISIONES. Cabos cerrados el 02-nov: limites (5 busquedas sin
   resultado en 24 h y 3 solicitudes pendientes), aviso tambien al adolescente de 14 a 17 con correo propio, y la
   clave del menor la maneja soporte si el primer vinculo se revoca (decision: sin cambio de codigo).
5. **Volver a vincularse: HECHO** (02-nov). Puede volver a pedirlo el rechazado y quien se desvinculo solo (mismo
   vinculo, con su historial; varias revocaciones por vinculo, migracion apoderados 0009). Si lo revoco soporte,
   debe escribir a soporte.
6. **Avisos de la revocacion: HECHO** (02-nov). Si la revoca soporte, al revocado con el motivo; si el vinculo
   estaba verificado, a los demas apoderados y al adolescente de 14 a 17 con correo, sin motivo ni quien era.
7. **Profesor cancela una clase: ya estaba HECHO** en el paso A3b de agenda (`agenda/avisos_alumno.py`: correo y
   campanita a los apoderados con vinculo verificado; prueba `test_si_es_menor_avisa_al_apoderado_y_no_al_menor`).
   Revisado el 02-nov: no hay otro camino por el que se cancele una clase reservada sin aviso.
8. **No habilitar menores reales** hasta la revision juridica de los textos (declaracion de facultad,
   revocacion, transicion a los 18), de seguridad y operativa (quien verifica certificados y como).

## Documentos de apoderados (2a hecha en `fran-apoderados-2a`; falta 2b)
A. **Fase 2b: tickets.** Hecha en `fran-soporte-2b1` y `fran-soporte-2b2` (roles agente y lider,
   asignacion automatica, 5 dias habiles para verificaciones). Faltan los avisos al usuario: paso 5 del plan.
B. **Railway: cron diario** `python manage.py borrar_documentos_vencidos` (el comando ya existe) y
   **definir `DOCUMENTOS_CLAVE`** (clave Fernet). Si la clave cambia, los documentos pendientes ya no se
   pueden leer y hay que pedirlos de nuevo.
C. **PDF: hecho (paso 9, `fran-pdf-protegido`).** Original cifrado que nunca va al navegador + imagen con
   marca de agua; maximo 3 paginas, sin contrasena. Los titulos de profesores siguen la misma regla.
D. **Apoderados registrados antes de la 2a sin carnet: HECHO** (03-nov, `fran-agenda`). La pantalla ya existia
   (`apoderado_subir_carnet` para quien esta en revision sin documentos y `apoderado_subir_documento_vinculo` para
   cada vinculo pendiente) y al subir se abre el ticket. Lo que faltaba era el texto, que decia "vencieron": ahora
   dice "o nunca las subiste, o vencieron". Al verificado no se le pide nada. Prueba: `RegistradoAntesDeLosDocumentosTests`.
E. **Rechazo: HECHO** (03-nov, decidido). El apoderado rechazado puede reintentar: si fue la identidad, sube otro
   carnet desde su portal (`apoderado_subir_carnet`) y vuelve a "Identidad en revision"; si fue el vinculo, sube
   otro documento (`apoderado_subir_documento_vinculo`) y vuelve a pendiente. En ambos casos se abre un ticket
   nuevo (el del vinculo solo cuando su identidad este verificada) y el rechazo queda en el historial. El vinculo
   revocado por soporte sigue siendo caso de contacto. No hay tope de reintentos: si se vuelve un abuso, agregar
   uno (por ejemplo, 3 rechazos seguidos y luego solo por contacto). Prueba: `tests/test_apoderados_reintento.py`.
F. **La invitacion del adolescente (1b-ii) es solo para madre o padre.** El tutor legal entra por 1b-i.
   Ampliarla exige cambiar textos de 1b-ii (declaracion y su version, etiquetas, correos, verbose_name).
G. **Respaldos de PostgreSQL/Railway**: conservan los documentos durante su retencion aunque se borren.
   Revisarlo en la politica de privacidad.
H. **Revision juridica** del aviso de documentos y de las declaraciones v2 (apoderado y vinculo).

## Calidad
9. **alumnos/views.py: HECHO** (05-nov, `fran-dividir-archivos`): de 947 a 519 lineas, movimiento puro (sin
   cambios de comportamiento). Reservas en `alumnos/reservas.py`, Webpay en `alumnos/webpay.py` (los parches de
   pruebas apuntan a `alumnos.webpay._tx`) y sala virtual en `alumnos/sala_virtual.py`.
10. **Revision visual en navegador** de todas las fases de apoderados (registro, revision admin, vinculos,
    invitacion de adolescentes, compra, reservas, revocacion, transicion a los 18).
11. **Correos con entidades HTML: HECHO** (05-nov, `fran-dividir-archivos`). `render_to_string` escapa aunque la
    plantilla sea .txt: "O'Higgins" llegaba como "O&#x27;Higgins" en los 28 correos. Ahora `alumnos.correo.enviar`
    usa el motor de plantillas `correo` (settings.TEMPLATES, `autoescape: False`); las paginas siguen escapando.
    Prueba: `tests/test_correo.py`. Al crear un correo nuevo, mandarlo por `enviar` (no por `send_mail` directo).

## Tanda 6 a 9 (03-nov, `fran-agenda`)
- **6. El adolescente de 14 a 17 no contrata ni paga solo: HECHO.** Revisados todos los caminos: las 4 operaciones
  de reserva ya bloqueaban en `InscripcionService`; la compra bloqueaba solo en la vista. Ahora el bloqueo esta en
  `iniciar_compra_paquete` (donde se crea el paquete), con el vinculo del apoderado como unica llave, y la pantalla
  Planes le dice que contrata su apoderado. La fecha de nacimiento no la edita el usuario (solo el admin).
- **7. Maquetas a datos reales: HECHO.** Avance por ramo con clases y horas reales (`alumnos/progreso.py`);
  `myClasses` y `myReports` eran codigo muerto; el estudio de streaming simulado del profesor (con el chat de "Juan
  Perez") era JS huerfano y se borro; el "Chat de la Sesion" de la sala virtual no enviaba nada y prometia ser
  privado: se reemplazo por una indicacion de usar el chat de la videollamada. **`teacherFeedback` ahora es real**
  (app `observaciones`, migracion 0001): el profesor deja una observacion por clase ya realizada (Mi Agenda >
  Clases realizadas), con el mismo filtro anti-contacto del chat (`mensajes/filtro.py`), 10 a 500 caracteres,
  editable. **Quien la lee (decidido 03-nov): el alumno en su Mi Progreso, tambien el menor, y el apoderado del
  menor en Clases del estudiante.** Se borra al eliminar la cuenta del alumno (`supresiones/datos_propios.py`) y
  **a los 12 meses de la clase** (`OBSERVACIONES_MESES` en settings, igual para menores; comando diario
  `borrar_observaciones_vencidas`). Una clase vencida ya no admite observacion ni se muestra aunque el cron no haya
  corrido; el aviso de las pantallas lee el mismo numero. Pendiente: si deben aparecer en una futura descarga de
  datos del alumno.
- **8. El profesor ve "Madre/Padre/Tutor legal de X": HECHO.** Sale del vinculo verificado. Si no hubiera vinculo,
  "Apoderado de X". Se actualizo el aviso previo del apoderado. Sigue sin ver el nombre, RUT ni correo del apoderado.
- **9. Carnet de apoderados antiguos:** ver D arriba.
- **Hallazgos (03-nov, resueltos):** (a) la sala de Jitsi ya no se llama `lbwus-clase-privada-<id>`: el nombre es
  una firma HMAC con `SECRET_KEY` (`alumnos/sala.py`). **Por eso `SECRET_KEY` debe estar definida en Railway**: con
  el valor por defecto del codigo el nombre se podria calcular. Sigue siendo la sala publica `meet.jit.si`: quien
  consiga el enlace puede entrar; Jitsi con JWT (servidor propio o 8x8) seria el siguiente paso. Ademas, todos los
  alumnos de una misma clase comparten esa sala. (b) Tildes de `sala_virtual.html` recuperadas, con prueba.
  (c) El grafico "Horas de estudio semanales" ahora usa las clases completadas de las ultimas 5 semanas
  (`alumnos/progreso.horas_por_semana`). (d) `myReports` se borro. (e) "Juan Perez" en el simulador (retirado el 03-nov, con su conversor de moneda) era una demo
  publica, otra cosa.
- **Al desplegar:** correr `python manage.py migrate` (nueva: `observaciones 0001`) y **programar el cron diario
  `python manage.py borrar_observaciones_vencidas`** junto al de documentos.

## Equipo
11. **Cerrar SIN mergear el PR de la rama `Franco`**: `fran-integrar-s402` lo reemplaza (su flujo de pagos
    antiguo rompia paquetes y honorarios). No borrar su rama.
12. **Avisar del orden de migraciones**: alumnos 0010 y 0011 vienen de apoderados; la cache de S4-02 ya no
    usa migracion (se crea con post_migrate).

## Limpieza local (opcional)
- Carpetas temporales en Documents\puppy_workspace: franco_s402, combinado_s402_1d, combinado2_s402_1d,
  combinado3_hallazgos_1d y los .zip/.log de esas pruebas.
