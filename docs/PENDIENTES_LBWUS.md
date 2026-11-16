# LBWUS: pendientes

Actualizado: 15-nov-2026. Aqui queda solo lo que falta. Todo lo que listaba la version anterior ya esta en `main`
(35 de sus 38 ramas; las otras 3 se cierran sin mergear, LBW-16). El historial de lo hecho sigue en git:
`git show c8f3341:docs/PENDIENTES_LBWUS.md`. Las decisiones estan en DECISIONES_SOPORTE_Y_PAGOS.md.

Los codigos LBW-xx y Dx son los del backlog y las decisiones grupales del 08-nov (se cargan en Jira).

## Railway: una sola vez (ver CONFIGURACION_PRODUCCION.md)
- Servicio Cron `python manage.py tareas_diarias` a las 9:00 UTC (LBW-01). Corre las 8 tareas diarias.
- Correr una vez: `manage.py pasar_reportes_a_tickets` y `manage.py pasar_titulos_a_base` (LBW-07).
- Habilitar al menos un agente en cada tema nuevo: `manage.py habilitar_soporte <RUT> --agregar especializaciones
  horario contacto privacidad` (LBW-07). Sin agente, esos tickets quedan sin asignar.
- Definir `SUPRESIONES_CLAVE` aparte y guardarla junto a los respaldos, nunca en la base. Sin ella se deriva de
  `SECRET_KEY` (ver CONFIGURACION_PRODUCCION.md).
- Programar `exportar_supresiones RUTA` a diario, con el archivo fuera de la base (LBW-13; falta decidir donde, D3).
  Tras restaurar cualquier respaldo: `reaplicar_supresiones --archivo RUTA` antes de reabrir el servicio.
- Confirmar que Railway agrega la IP del cliente al final de `X-Forwarded-For` (S4-02, LBW-08).
- Definir `ERRORES_CORREOS` (quien recibe el aviso de un error 500) y poner un monitor externo gratuito (por ejemplo
  UptimeRobot) que consulte `https://lbwus.xyz/salud/` cada 5 minutos. No usar el Healthcheck Path de Railway con esa
  direccion sin permitir antes `healthcheck.railway.app` en `ALLOWED_HOSTS`. Detalle en CONFIGURACION_PRODUCCION.md.
- Respaldos automaticos y una restauracion probada (LBW-14). La politica de privacidad debe decir que los
  respaldos conservan los documentos durante su retencion.

## Despues de ese despliegue
- 9b-3: quitar `titulo_archivo` (alumnos/models/usuarios.py) y actualizar `usabilidad/verificar_google_titulo.py`.
  Solo despues de correr `pasar_titulos_a_base` en produccion. Sin ticket todavia.

## Seguridad y calidad (detalle en el backlog)
- LBW-11 y LBW-21 escape en el JS, LBW-12 suite en paralelo (la CI corre `manage.py test` sin `--parallel`),
  LBW-22 a LBW-26 deuda tecnica. LBW-03 (DEBUG seguro en Railway), LBW-04 (versiones fijas en `requirements.txt`),
  LBW-05 (gunicorn en el `Procfile`), LBW-06 (CI) y LBW-10 (Dependabot) ya estan hechos: se verificaron en el
  codigo el 15-nov.
- Revision visual en navegador de todos los flujos de apoderados (LBW-15).
- Posible CSS muerto en `pago/01_pago.css` (paneles de resumen y Webpay). Sin revisar, sin ticket.

## Antes de abrir al publico: lo que faltaba en esta lista (revision del 15-nov)
- **Cerrar la CSP.** Sigue en Report-Only (`CSP_OBLIGATORIA`), permite `'unsafe-inline'` (hay scripts, `onclick=` y
  `style=` en linea en las plantillas) y no tiene destino para reportes: hoy no bloquea nada. Es trabajo grande:
  sacar lo que esta en linea, mirar los reportes y recien ahi hacerla obligatoria.
- **SweetAlert2 sigue viniendo de internet.** Es el unico script externo (`cdn.jsdelivr.net/npm/sweetalert2@11`, la
  version 11 sin fijar). Alojarlo en `static/vendor/` como los iconos y las letras, y quitar jsDelivr de `script-src`.
  Tampoco es propia la letra del correo de recuperar clave: un correo no puede traer archivos.
- **Probar Atlas.** Las 6 pruebas que exigen conexion real a MongoDB (`MONGODB_INTEGRACION=1`) no se corrieron en esta
  revision. Correrlas con una base **de prueba**, nunca `lbwus_prod`: escriben datos.
- **Cookies en la politica de privacidad.** No menciona que el sitio usa cookies esenciales (sesion y proteccion
  CSRF), ni que no usa cookies de seguimiento. Para la abogada, junto con L-2, L-3 y L-5.
- **Politica de privacidad: Google y las letras.** La lista de proveedores dice que Google entrega "fuentes de texto
  de la pagina". Desde que las letras salen del propio sitio (`static/vendor`) ya no es asi: solo queda la letra del
  correo de recuperar clave. Ajustar el texto cuando se mezcle ese cambio, con la abogada.
- **Sin constancia en el repositorio (confirmar fuera de el):** auditoria de accesibilidad WCAG 2.2 AA; prueba de
  carga con el `Procfile` actual (gunicorn, 4 hilos); un entorno de ensayo distinto de produccion; SPF, DKIM y DMARC
  del dominio desde el que sale el correo (si faltan, la recuperacion de clave y los avisos pueden caer en spam); y
  la carga de datos iniciales de produccion (generos, asignaturas, planes).

## Pagos
- Transbank en produccion: checklist en CONCILIACION_Y_TRANSBANK_7_6.md, seccion 6 (LBW-09).
- Reporte de conciliacion (LBW-18) y retiros con dinero real: falta el contador y Webpay en produccion (LBW-19).
- Cuanto se guardan los registros de pago: contador y abogada (LBW-20, D2).

## Menores y legal
- **Menores habilitados (15-nov).** La revision juridica ya se hizo. Los certificados y documentos de los apoderados
  los revisan los agentes de soporte: cada revision es un ticket (LBW-02, D1). Sin agente habilitado esos tickets
  quedan sin asignar (ver Railway, mas arriba).
- **Antes de abrir al público: reemplazar los datos de ejemplo del responsable** (B7, 15-nov). Las páginas
  `/terminos/` y `/privacidad/` y el pie ya existen, pero muestran un responsable inventado (`LBWUS SpA`, RUT
  `76.000.000-0` y domicilio de ejemplo; el teléfono y los correos ya son los reales, hoy el mismo para contacto y para
  datos: `lbwus.proyecto@gmail.com`). Se cambian con las variables `LEGAL_*` de Railway, sin tocar código
  (ver CONFIGURACION_PRODUCCION.md). Hay que definir razón social o nombre, RUT y domicilio (L-1). El correo de derechos
  es hoy el de contacto (L-4): alguien debe leerlo a diario. Ambos textos son un borrador a revisar por la abogada; lo más delicado es
  Terminos §9, "no se devuelve dinero por clases" (revisar contra la ley del consumidor y el retracto). En Privacidad faltan
  confirmar país y contratos de los proveedores (L-2), los respaldos (L-3) y los plazos contables (L-5).
- **Aceptación de Términos y Privacidad (15-nov):** se pide al comprar un paquete (alumno y apoderado, un solo control
  en `webpay.iniciar_compra_paquete`) y queda registrada por versión (`AceptacionLegal`). Al cambiar los textos hay
  que subir `VERSION` en `alumnos/aceptacion.py`: se vuelve a pedir una vez. **No se pide al registrarse**: los
  profesores, que no compran, hoy no aceptan nada, y la compra de videos extra no la repite porque exige un paquete
  ya comprado. Decidir con la abogada si también debe ir en el registro (4 formularios: alumno, profesor, apoderado
  y Google).
- **Descarga de datos del alumno: decidido no hacerla (15-nov).** Las solicitudes de una copia se atienden a mano,
  por soporte o por el correo de derechos, como dice la política de privacidad (sección 5). Retomar solo si la
  abogada la exige.
- Fuera de desarrollo: responsable del tratamiento, proveedores reales, respaldos, correo
  de derechos y plazos contables. Cuanto se conserva al seudonimizar una cuenta: con asesoria legal.

## En espera (solo si hace falta)
- Sala de Jitsi privada con JWT: hoy es la sala publica `meet.jit.si` (LBW-28, D4).
- Tope de reintentos para apoderados rechazados, si aparece abuso. Invitacion del adolescente tambien para el
  tutor legal (hoy solo madre o padre; cambia textos legales). Observaciones del profesor en una descarga de datos
  del alumno, si algun dia se hace. Historial de personas que entran por dia (hoy solo la tarjeta de hoy). Ver D9.

## Notas vigentes
- Si cambia `SECRET_KEY`, lo cifrado con `alumnos/cifrado.py` sin clave propia (por ejemplo, las cuentas
  bancarias) deja de leerse, y cambian los nombres de las salas de Jitsi. Si cambia `DOCUMENTOS_CLAVE`, los
  documentos pendientes se piden de nuevo.
- Al crear un correo nuevo, mandarlo por `alumnos.correo.enviar` (no por `send_mail` directo).
- El enlace de cambio de cuenta bancaria exige sesion: si el profesor no la tiene, entra y vuelve a abrirlo.

## Limpieza local
- Sacar el repo de OneDrive y limpiar los worktrees huerfanos de `.git/worktrees` (LBW-29).
