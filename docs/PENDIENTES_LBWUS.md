# LBWUS: pendientes

Actualizado: 20-nov-2026. Aqui queda solo lo que falta. Todo lo que listaba la version anterior ya esta en `main`
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

## Arreglos acordados (20-nov): orden de trabajo, en `fran-pulido-apoderado`
Decididos con Fran el 20-nov. Van en este orden (bugs primero) y cada uno con sus pruebas, su commit y esta lista al día.
Antes (16-nov) las etapas A1 a A6 dejaron las 10 pantallas del admin iguales a la copia (0 px de diferencia, salvo datos
de la demo); los puntos 3 y 4 son lo que se vio al comparar y no se tocó porque cambia comportamiento.

1. **Planes: las vigencias de «Condiciones» están mal.** `alumnos/templates/alumnos/planes.html` dice a mano «30 días
   (Flexible), 60 días (Progreso) o 90 días (Intensivo)», pero desde el 14-nov son 30, 30 y 60 (`alumnos/paquetes.py`,
   `PLANES`). Las tarjetas sí muestran lo real: la pantalla se contradice y le promete al alumno algo que no es. Leerlas
   de `PLANES` (nada escrito a mano) y una prueba que compare el texto con `PLANES`. Revisar el resto de «Condiciones» y
   de los textos legales por otras cifras escritas a mano.
2. **Planes: no se leen los enlaces de Términos y Privacidad en la tarjeta oscura** (Intensivo, `.featured`).
   `.pl-acepta a` (`styles/10_legal.css`) usa `var(--primary)`: morado sobre fondo oscuro, no cumple el contraste de
   WCAG 2.2 AA (4,5:1). Color propio dentro de `.featured`, también la casilla y su foco.
3. **Admin: Ajustes no guarda nada. Se conecta de verdad (decidido).** En `includes/dashboard/perfil.html` el
   `onsubmit` hace `preventDefault()` y muestra «Ajustes guardados» sin enviar nada; los campos ni siquiera tienen
   `name`. Hacer: vista POST con `@admin_required`, form con validación, nombre, correo, teléfono y dirección editables;
   **RUT de solo lectura** (es la identidad; el registro de supresiones guarda su huella); correo único; formato del
   teléfono; mensajes de error junto a cada campo; el nombre del menú se actualiza; pruebas. El color de acento
   sigue siendo solo de la sesión (decir eso en la pantalla, como hoy). Unas 1 a 2 h.
4. **Admin: un solo «Usuarios» (decidido).** Hoy hay dos listados de alumnos: el del dashboard (`#usuarios`, diseño
   nuevo) y `crud` (`alumnos_list.html`, diseño viejo). El menú de `base_admin.html` apunta a `crud` en todas las
   páginas menos el dashboard. Además, desde el listado nuevo: «Agregar» y «Editar» abren `alumnos_add.html` y
   `alumnos_edit.html` (diseño viejo) y «Eliminar» (`alumnos_del`) termina en `alumnos_list.html`. Hacer:
   (a) `crud` redirige a `dashboard_admin#usuarios` (la ruta se mantiene para no romper enlaces) y se borra
   `alumnos_list.html`; (b) `alumnos_del` redirige al mismo lugar con su mensaje («datos eliminados» o «se
   seudonimizó») por `messages`; (c) el menú siempre va al dashboard; (d) rediseñar agregar y editar con la capa 06:
   no hay copia de referencia, **Fran aprueba con capturas** antes del commit. Revisar `test_boton_atras`,
   `test_control_acceso`, `test_portales_por_rol`, `test_qa_acceso`, `test_apoderados` y `usabilidad/recorrido.py`,
   que nombran `crud`. Unos 20 min (a-c) y 1 a 1,5 h (d).
5. **Soporte: el menú de Verificaciones según quién entra (decidido, opción a).** Hoy «Apoderados» y «Documentos de
   profesores» (`soporte/templates/soporte/base_soporte.html`) salen a todo el soporte sin mirar sus categorías: un
   agente de Pagos ve dos pantallas que siempre estarán vacías. Hacer: el agente ve cada una solo si atiende ese tema
   (Apoderados: `apoderados`; Documentos de profesores: `titulos` o `especializaciones`); el líder las ve siempre, pero
   bajo **«Supervisión»** en vez de «Verificaciones», porque para él es control (historial, vínculos vigentes con
   «Revocar», revocaciones y registros de quién abrió cada documento), no trabajo pendiente. No quitárselas al líder:
   perdería «Revocar» y la auditoría. Las vistas ya filtran por ticket: esto es solo el menú (y el buscador Ctrl+K,
   que lista las secciones del menú). Pruebas: un agente sin el tema no ve el enlace; el líder sí, bajo «Supervisión».
6. **Planes: diseño más profesional.** Lo que se ve en el video de presentación:
   - La casilla de Términos **se queda en cada tarjeta** (decidido), pero con mejor diseño y aire: hoy queda pegada
     al botón de comprar.
   - El desglose de cada tarjeta («Incluye comisión LBWUS de 15%: $X (IVA incluido: $Y)» y «El profesor recibe $Z»)
     pasa a un **plegable «Ver desglose»** (decidido): sigue siendo transparente, pero no compite con el precio.
   - Coherencia de nombres: el menú dice «Mis paquetes» y el título «Planes y precios».
   - «Ver perfil del profesor» no debe partirse en dos líneas.
   - Jerarquía de precios (precio del paquete y precio por clase), una etiqueta mejor que «Mayor descuento» e íconos
     parejos en la lista de beneficios.
   - Revisar en claro, oscuro y celular. El recuadro «Portal del alumno · Ana, alumna» del video no es de la app: lo
     pone `video_demo/guion.py`.

- Para una demo mientras se hacen 3 y 4: no usar «Guardar cambios» de Ajustes y entrar a «Usuarios» siempre desde el Resumen.
  SweetAlert viene de internet (ver el pendiente de arriba): sin conexión, el aviso de Ajustes no aparece y «Eliminar»
  usa el `confirm()` del navegador.
- Los scripts de verificación (comparador con la copia, claro, oscuro y celular; Resumen; Usuarios; HTML de Soporte)
  están en `puppy_workspace`, fuera del repositorio.

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
