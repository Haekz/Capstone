# Configuración productiva, almacenamiento y respaldos (S4-13 / SCRUM-93)

Verificado el 31-oct-2026 sobre `main` en 5204d78 más los cambios de SCRUM-93. Producción: Railway (servicio web + PostgreSQL + volumen) y MongoDB Atlas.
**Este documento no contiene valores secretos y no debe contenerlos nunca.** Las claves viven solo en las variables de Railway y en un gestor de contraseñas del equipo.

## 1. Variables de entorno

Todas las lee `lbwus/settings.py`, salvo donde se indica.

| Variable | Para qué | ¿Obligatoria en producción? | Si falta |
|---|---|---|---|
| `SECRET_KEY` | Firma de sesiones, CSRF, tokens de recuperación y nombres de sala Jitsi | **Sí** | Con `DEBUG=False`, el sitio **no arranca** (`ImproperlyConfigured`). En desarrollo usa una clave insegura |
| `DOCUMENTOS_CLAVE` | Clave Fernet de los documentos de apoderados (sección 3) | **Sí** | **El despliegue no arranca**: el `Procfile` corre `check --deploy`, que da el error `apoderados.E001` (o `E002` si la clave no es válida) |
| `SUPRESIONES_CLAVE` | Clave de las huellas del registro de supresiones (`supresiones/registro.py`) | Recomendada | Se deriva de `SECRET_KEY`. Si la clave cambia, el registro y los archivos exportados **dejan de reconocer a las personas eliminadas**: definirla aparte y guardarla junto con los respaldos, nunca en la base de datos |
| `DEBUG` | Modo depuración | Sí, `False` | En Railway queda en `False` (se detecta por `RAILWAY_ENVIRONMENT`) y exige `SECRET_KEY`; en local queda en `True` |
| `DATABASE_URL` | PostgreSQL (la crea Railway al enlazar la base) | Sí | Sin ella (o con una URL que no sea PostgreSQL) el sitio no arranca |
| `MEDIA_ROOT` | Carpeta de archivos subidos | Sí, `/data/media` (el volumen) | Usa `media/` dentro del contenedor, que se borra en cada despliegue |
| `SECURE_SSL_REDIRECT` | Redirigir HTTP a HTTPS | No (por omisión `True` con `DEBUG=False`) | — |
| `RAILWAY_ENVIRONMENT` | La define Railway. Activa enlaces `https` de allauth y confiar en `X-Forwarded-For` para el límite de intentos (`alumnos/views.py`) | La pone Railway | Enlaces `http` y límite por IP del proxy |
| `PORT` | Puerto de gunicorn (`Procfile`) | La pone Railway | — |
| `EMAIL_HOST`, `EMAIL_PORT` | Servidor SMTP | No (por omisión Gmail, 587) | — |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Cuenta de correo | Sí | Fallan la recuperación de contraseña, el código de Google y los correos de apoderados |
| `DEFAULT_FROM_EMAIL` | Remitente | No (usa `EMAIL_HOST_USER`) | — |
| `ERRORES_CORREOS` | Correos, separados por comas, que reciben un aviso cuando hay un error 500 (`lbwus/aviso_errores.py`). El aviso **no lleva datos de las personas** ni el mensaje del error: solo la pantalla, el tipo de error, el id de la cuenta y por dónde pasó el código. **Va en el servicio web** | Recomendada | No se avisa por correo; el error igual queda completo en los registros de Railway |
| `ALERTAS_CORREOS` | A quién avisar por correo si falla alguna tarea de `tareas_diarias` (sección 8). Varios correos separados por comas. **Va en el servicio Cron**, que es el que envía el aviso | Recomendada | No se envía ningún aviso: la falla queda solo en los logs del Cron y en `/salud/` |
| `SALUD_RECORDATORIOS` | `1` hace que `/salud/` vigile también el cron de recordatorios de clase (sección 4). **Va en el servicio web, y solo cuando ese cron ya existe** | No | `/salud/` solo vigila `tareas_diarias` |
| `MONGODB_URI` | MongoDB Atlas (app `comunidad` y la ficha de cada video) | Sí, si se usa la comunidad o se venden videos | MongoDB queda desactivado, no se venden videos y el resto del sitio funciona igual |
| `MONGODB_DB`, `MONGODB_TIMEOUT_MS` | Base de MongoDB y tiempo de espera | No (por omisión `lbwus_dev`, 5000) | **En producción debe ser `lbwus_prod`** |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | Cloudflare R2: los archivos de video (sección 2, «Crear el bucket de R2») | Sí, para vender videos: **las cuatro** y además `MONGODB_URI` | Los videos quedan desactivados: no se suben, no se ven y no se venden (`VIDEOS_A_LA_VENTA`). El paquete de clases se sigue vendiendo |
| `CSP_OBLIGATORIA` | `1` hace obligatoria la Content-Security-Policy (sección 7) | No | Queda en Report-Only: el navegador avisa, pero no bloquea |
| `SITIO_URL` | Dirección pública del sitio: la usan la dirección canónica, la vista previa al compartir (WhatsApp, redes), `robots.txt` y `sitemap.xml` (`lbwus/seo.py`). Así, entrando por `*.up.railway.app` los buscadores siguen viendo `lbwus.xyz` | No | Usa `https://lbwus.xyz`. **Si el dominio cambia hay que definirla**: si no, Google tomaría la dirección vieja como la oficial |
| `SITIO_CLAVE` | Puerta "Sitio en mantenimiento" (`lbwus/puerta.py`) | No | Sin puerta |
| `SITIO_DOMINIOS_CORREO` | Puerta por dominio de correo (tiene prioridad sobre `SITIO_CLAVE`) | No | Sin puerta por correo |
| `LEGAL_NOMBRE`, `LEGAL_RUT`, `LEGAL_DOMICILIO`, `LEGAL_TELEFONO`, `LEGAL_CORREO_DATOS`, `LEGAL_CORREO_CONTACTO` | Quién responde por los datos y cómo contactarlo: Términos, Privacidad, pie de página y Contacto (`settings.LEGAL`) | **Sí, antes de abrir al público** | Se muestran de ejemplo el nombre y el RUT (`LBWUS SpA`, `76.000.000-0`) y el domicilio; el teléfono y los correos ya son los reales (hoy `lbwus.proyecto@gmail.com` para contacto y para datos). Un RUT inventado no es un responsable real, y una solicitud enviada a un correo que nadie lee no se responde |
| `TRANSBANK_PRODUCCION_HABILITADA`, `TRANSBANK_ENVIRONMENT`, `TRANSBANK_COMMERCE_CODE`, `TRANSBANK_API_KEY` | Webpay real | No: sin ellas se usa el ambiente de integración (la simulación oficial de Transbank) | Sin cobros reales (es lo esperado hoy). **Para pasar a real: las cuatro a la vez** (`TRANSBANK_PRODUCCION_HABILITADA=True`, `TRANSBANK_ENVIRONMENT=LIVE`, código de comercio y llave). Si falta una, el sitio no arranca y dice cuál |
| `MONGODB_INTEGRACION` | Solo pruebas | No | — |

El inicio de sesión con Google no usa variables: el `client_id` y el secreto están en la base (Django admin → Social applications).

**Salud del sitio.** `/salud/` responde `200` solo si `tareas_diarias` terminó completa en las últimas 26 horas, y `503` (`atrasado`) si no; detalle y monitor externo en la sección 8 («Detectar que `tareas_diarias` no corrió»). Si la base de datos no responde también da `503 atrasado`, porque esa hora se guarda en PostgreSQL: ante una alerta, revisa primero si el resto del sitio abre. **No uses `/salud/` como "Healthcheck Path" de Railway**: da 503 hasta la primera corrida del Cron y cada vez que se atrasa, así que bloquearía los despliegues (además, esa consulta sale desde `healthcheck.railway.app`, que no está en `ALLOWED_HOSTS`: daría 400).

## 2. Archivos privados

| Qué | Dónde vive | Cómo se entrega |
|---|---|---|
| Títulos de profesores (`Profesor.titulo_archivo`, `titulos/`) | Volumen de Railway en `MEDIA_ROOT=/data/media` | Solo por `admin_portal/titulos.py::ver_titulo` (`@admin_required`) |
| Fotos de perfil (`CustomUser.foto_perfil`, `perfiles/`) | Volumen | **Ninguna vista las sirve hoy** (pendiente conocido: la imagen se ve rota) |
| Documentos de apoderados (carnet, documento del vínculo) | **PostgreSQL, cifrados** (`apoderados.Documento.contenido`, `BinaryField`). No van a disco ni al volumen | Solo por `apoderados/views_revision.py::ver_documento` (`@soporte_required`, solo el agente con el ticket), con marca de agua y registro de cada apertura; se borran al resolver la revisión o a los 30 días |
| Videos de apoyo (MP4 de hasta 500 MB y 30 minutos) | Archivo en **Cloudflare R2, bucket privado** (`user_profesor/almacen_videos.py`); su ficha en la colección `videos` de MongoDB | La web revisa el acceso (`alumnos/videos_compartidos.py`) y redirige a un **enlace firmado que vence en 2 horas**. Un enlace ya entregado sigue sirviendo hasta que vence, aunque el acceso se quite antes |

- `lbwus/urls.py` **no publica `MEDIA_URL`**: no existe ninguna ruta `/media/`. Un GET a `/media/titulos/...` o `/media/perfiles/...` da 404, también para un admin (`tests/test_configuracion_produccion.py::ArchivosPrivadosTests`).
- WhiteNoise sirve solo `STATIC_ROOT` (`/static/`), nunca `MEDIA_ROOT`.

### Crear el bucket de R2 (una vez)

Hasta hacer esto, los videos quedan desactivados (no se venden). Nada de esto va al repositorio.
1. En Cloudflare → **R2 Object Storage**: activar R2. Pide un medio de pago, aunque los primeros 10 GB al mes son gratis y ver los videos no cobra salida de datos.
2. **Create bucket**: por ejemplo `lbwus-videos`, ubicación automática. **No** activar *Public access* ni el dominio `r2.dev`: el bucket debe quedar privado. **No hace falta CORS**: la subida pasa por la web y el reproductor solo carga el video.
3. R2 → **Manage API tokens → Create API token**: permiso **Object Read & Write**, limitado **solo a ese bucket**. Copiar el *Access Key ID* y el *Secret Access Key* (este último se muestra una sola vez) al gestor de contraseñas del equipo.
4. Copiar el **Account ID**, que aparece en la página de R2.
5. Railway → servicio web → Variables: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` y `R2_BUCKET`. Desplegar.
6. Probar: como profesor, subir un video corto y compartirlo; como ese alumno, verlo y adelantarlo.

Si la clave se filtra: en Cloudflare, borrar ese token y crear otro (pasos 3 y 5). Los enlaces ya entregados dejan de servir.

## 3. Claves: `SECRET_KEY` y `DOCUMENTOS_CLAVE`

**Riesgo.** Antes de SCRUM-93, sin `DOCUMENTOS_CLAVE`, los documentos se cifraban con una clave **derivada de `SECRET_KEY`**. La `SECRET_KEY` de producción se rotó en SCRUM-81, así que **lo que se cifró antes de esa rotación ya no se puede leer**. No hay forma de recuperarlo sin la clave anterior, y no se debe intentar. Como los documentos viven 30 días como máximo (si corre el cron de la sección 4), el impacto se limita a las revisiones que estaban pendientes en ese momento: hay que pedirle al apoderado que vuelva a subir el documento.

**Desde SCRUM-93:**
- Se cifra con `DOCUMENTOS_CLAVE`. Para leer, se prueba esa clave y luego la derivada de la `SECRET_KEY` actual (`MultiFernet`). Así, lo subido antes de definir la variable sigue legible.
- Con `DEBUG=False` y sin `DOCUMENTOS_CLAVE` válida, el despliegue se detiene antes de gunicorn (`check --deploy --fail-level ERROR` en el `Procfile`) y, si igual se llegara a usar, subir o ver un documento da error. Ya no hay un respaldo silencioso a `SECRET_KEY`.
- Rotar `SECRET_KEY` ya no afecta a los documentos nuevos (`test_con_documentos_clave_rotar_secret_key_no_pierde_documentos`).

**Procedimiento (una vez, antes de desplegar esta rama; si no, el despliegue no arranca):**
0. Revisar en Railway → servicio web → Variables si **ya existe** `DOCUMENTOS_CLAVE`. Si existe, **no la cambies**: los documentos cifrados con ella dejarían de leerse. Solo confírmala en el gestor de contraseñas y salta al paso 4.
1. Si no existe, generar la clave en tu equipo: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
2. Guardarla en el gestor de contraseñas del equipo. **Nunca** en el repositorio, en `.ia/` ni en un chat.
3. En Railway → servicio web → Variables: `DOCUMENTOS_CLAVE=<la clave>`. Desplegar.
4. Verificar con `railway ssh` → `python manage.py check --deploy`: no debe aparecer `apoderados.E001` ni `E002`.
5. Abrir un documento pendiente desde el portal admin. Si da error, era de antes de la rotación de SCRUM-81: pedirlo de nuevo.

**No cambies `DOCUMENTOS_CLAVE` después.** Rotarla requiere agregar la clave anterior a `MultiFernet` (no está implementado). Si se pierde, los documentos pendientes no se recuperan.

## 4. Despliegue y reinicio

`Procfile`: `migrate --noinput` → `collectstatic --noinput` → `check --deploy --fail-level ERROR` → `gunicorn lbwus.wsgi` (con hilos: `--worker-class gthread --threads 4 --timeout 120`, para que ver o subir un video largo no corte la conexión ni bloquee al resto). Si falta una clave obligatoria, el despliegue falla en el paso 3 y gunicorn no arranca (revisa los logs del despliegue en Railway). Los avisos (`W…`) de `check --deploy` no lo detienen.

| Qué | ¿Sobrevive a un redespliegue o reinicio? | Por qué |
|---|---|---|
| Usuarios, pagos, paquetes, reservas, sesiones de Django y caché del límite de intentos | Sí | PostgreSQL es un servicio aparte. La sesión y la caché usan la base (`DatabaseCache`, la tabla la crea `alumnos/apps.py` después de cada `migrate`) |
| Documentos de apoderados | Sí | Están en PostgreSQL |
| Títulos y fotos | **Solo si el volumen está montado en `/data/media` y `MEDIA_ROOT=/data/media`** | El disco del contenedor se borra en cada despliegue |
| Estáticos | Se regeneran | `collectstatic` en cada inicio |
| Comunidad (MongoDB) | Sí | Atlas es externo |
| Videos de apoyo (Cloudflare R2) | Sí | R2 es externo |

Con `DEBUG=False`, `CompressedManifestStaticFilesStorage` da error 500 si una plantilla pide un estático que no existe. Las pruebas no usan el manifiesto (`lbwus/test_runner.py`), así que no necesitan `collectstatic`; a cambio, `tests/test_configuracion_produccion.py::EstaticosTests` corre `collectstatic` con el almacenamiento de producción en una carpeta temporal (falla si un CSS apunta a un archivo inexistente) y revisa que cada `{% static '...' %}` literal de las plantillas esté en el manifiesto. Las rutas armadas con variables no se revisan.

**Tareas diarias (un solo cron).** `python manage.py tareas_diarias` corre todas las tareas diarias en orden (lista en `TAREAS`, `alumnos/management/commands/tareas_diarias.py`): agenda (`generar_bloques`), pagos que no volvieron, borrado de documentos de más de 30 días, observaciones y conversaciones vencidas, y avisos a líderes y agentes. Si una falla, corren las demás y la corrida termina con error nombrándola (se ve en los logs del servicio), y se avisa por correo a `ALERTAS_CORREOS`. Si todas terminan bien, guarda la hora de la corrida para `/salud/` (sección 8). Una tarea nueva se suma en `TAREAS`; Railway no se toca.

No está en el `Procfile` (ese arranca solo la web). Se crea **una vez** en Railway:
1. Proyecto → **+ New → GitHub Repo** → el mismo repositorio.
2. **Variables:** las mismas del servicio web (al menos `DATABASE_URL`, `SECRET_KEY`, `DOCUMENTOS_CLAVE` y las de correo y Transbank); conviene usar referencias a las del servicio web. Además, `ALERTAS_CORREOS` (sección 8).
3. **Settings → Custom Start Command:** `python manage.py tareas_diarias`. Sin esto arrancaría gunicorn por el `Procfile`.
4. **Settings → Cron Schedule:** `0 9 * * *` (todos los días 9:00 UTC, 6:00 en Chile).

**Verificar que exista y que no queden crons sueltos** de alguna de esas tareas: correrían dos veces. Sin este cron la agenda deja de ofrecer horas unas 4 semanas después de que el profesor editó su horario por última vez, y los documentos pendientes no se borran solos. `exportar_supresiones RUTA.json` no está en `tareas_diarias`: necesita una ruta de salida fuera de la base.

**Recordatorios de clase (segundo cron, cada 15 minutos).** `python manage.py enviar_recordatorios_clases` avisa 24 y 2 horas antes de cada clase al alumno (o a sus apoderados, si es menor) y al profesor, con campanita y correo (`alumnos/recordatorios.py`). **No va en `tareas_diarias`**: esa corre una vez al día y un aviso de 2 horas no puede esperar hasta mañana. Se crea **una vez** en Railway, como el cron de arriba pero con otro comando y otro horario:
1. Proyecto → **+ New → GitHub Repo** → el mismo repositorio.
2. **Variables:** las mismas del servicio web. Necesita sobre todo `DATABASE_URL`, `SECRET_KEY`, `SITIO_URL` (los botones de los correos llevan un enlace completo) y las de correo (`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`).
3. **Settings → Custom Start Command:** `python manage.py enviar_recordatorios_clases`.
4. **Settings → Cron Schedule:** `*/15 * * * *` (cada 15 minutos).
5. **Cuando ya haya corrido una vez bien**, en el servicio **web** define `SALUD_RECORDATORIOS=1`: desde ahí `/salud/` también da `503` (`atrasado`) si pasa más de 1 hora sin una corrida completa. **No lo enciendas antes**: sin este cron, `/salud/` daría 503 desde el primer minuto.

Cada reserva lleva sus marcas de «ya avisado» (`recordatorio_1d`, `recordatorio_2h`): un recordatorio no se repite, y reagendar las reinicia. Una reserva hecha con menos de 24 horas no recibe el de un día (llegaría minutos después de la confirmación), y una con menos de 2 horas no recibe ninguno. Si una reserva falla, la corrida termina con error (Railway la marca como fallida), las demás siguen y la que falló se reintenta en la próxima corrida. Un correo que Gmail rechaza se registra (`evento=correo_no_enviado`) y **no se reintenta**.

## 5. Respaldos (manual)

**Dónde guardarlos:** fuera del repositorio y fuera de Railway, en una carpeta cifrada (por ejemplo, un disco o una unidad en la nube del equipo con acceso restringido). Nombrarlos con la fecha (`AAAA-MM-DD`). **Nunca** en Git, en `.ia/` ni en un chat: contienen datos personales de menores.

**Frecuencia sugerida:** semanal, y siempre antes de un despliegue con migraciones. Conservar las últimas 4 semanales y 3 mensuales. Una vez al mes, probar la restauración en una base local.

1. **PostgreSQL** (desde tu equipo, con la URL pública que muestra Railway en la base → Variables → `DATABASE_PUBLIC_URL`; cópiala a la terminal, no a un archivo):
   ```bash
   pg_dump "$DATABASE_PUBLIC_URL" --format=custom --no-owner --file=lbwus_pg_AAAA-MM-DD.dump
   pg_restore --list lbwus_pg_AAAA-MM-DD.dump | head   # comprobar que se puede leer
   ```
   Usa un `pg_dump` de la misma versión mayor que el PostgreSQL de Railway, o una más nueva.
2. **Volumen (`/data/media`: títulos y fotos)**:
   ```bash
   railway ssh -- tar czf - -C /data media > lbwus_media_AAAA-MM-DD.tar.gz
   tar tzf lbwus_media_AAAA-MM-DD.tar.gz | head        # comprobar
   ```
   Este comando no se ha probado. Si `railway ssh` no entrega datos binarios por la salida, crea el `tar` dentro del contenedor y cópialo con el método de copia de archivos que ofrezca Railway.
3. **MongoDB Atlas** (con la URI de producción en una variable de la terminal):
   ```bash
   mongodump --uri "$MONGODB_URI" --db lbwus_prod --gzip --archive=lbwus_mongo_AAAA-MM-DD.gz
   ```
   Incluye las fichas de los videos. **Los archivos de video (R2) no entran en estos respaldos**: Cloudflare los guarda con redundancia, y si se perdiera uno, el profesor tendría que volver a subirlo.
4. **Claves:** `SECRET_KEY` y `DOCUMENTOS_CLAVE` van **solo** en el gestor de contraseñas, nunca junto a los respaldos. Sin `DOCUMENTOS_CLAVE`, los documentos del respaldo de PostgreSQL no se pueden leer, y eso es lo que se busca.

## 6. `check --deploy`

Con `DEBUG=False` y valores de prueba para `SECRET_KEY` y `DOCUMENTOS_CLAVE`: **"System check identified no issues"**. Sin `DOCUMENTOS_CLAVE`: error `apoderados.E001` (detiene el `Procfile`). Sin `SECRET_KEY`: `ImproperlyConfigured`, ningún comando arranca. HSTS, cookies seguras y la redirección a HTTPS ya están en `settings.py` cuando `DEBUG=False`.

## 7. Cabeceras de seguridad: CSP y Permissions-Policy

`lbwus/cabeceras.py` (`CabecerasSeguridadMiddleware`, justo después de `SecurityMiddleware`) agrega a toda respuesta:
- **`Content-Security-Policy-Report-Only`**: la política se evalúa, pero **no bloquea nada**. Cada violación aparece en la consola del navegador. Los orígenes permitidos, por directiva, están en `CSP` dentro de ese archivo.
- **`Permissions-Policy`**: cámara, micrófono, captura de pantalla y pantalla completa solo para el sitio y `https://meet.jit.si` (el iframe de la sala virtual). Geolocalización, pagos, USB y los demás, para nadie.

Mientras la CSP sea Report-Only, los navegadores **ignoran `frame-ancestors`**; contra el clickjacking protege `X-Frame-Options: DENY` (`XFrameOptionsMiddleware`). No lo quites.

**Si agregas un CDN, un iframe, un `fetch` a otro dominio o un formulario que envía a otro sitio**, agrega el origen en `CSP`. `tests/test_cabeceras.py::InventarioOrigenesTests` falla si una plantilla carga un `<script src>`, una hoja de estilo o un `<iframe>` de un dominio que no está permitido. Los `fetch`, las imágenes y los videos no los revisa: búscalos en la consola.

### Pasar de Report-Only a obligatoria

1. **Revisar las violaciones con Report-Only activo.** En producción (o en local con `DEBUG=False`), abrir con la consola del navegador abierta (F12 → Consola), y con al menos un usuario de cada rol: inicio, login (también con Google), registro, planes, compra hasta la página de Webpay de integración, retorno de Webpay, portal del alumno, sala virtual con el directo iniciado (cámara, micrófono, compartir pantalla, pantalla completa), panel del profesor (videos), portal admin, portal del apoderado y 404. Buscar mensajes `[Report Only] Refused to …`.
2. **Corregir cada aviso**: agregar el origen a `CSP` si es legítimo o quitar el recurso si no lo es. Repetir hasta que la consola quede limpia.
3. **Activar**: en Railway → servicio web → Variables, `CSP_OBLIGATORIA=1` y desplegar. Ahora la cabecera es `Content-Security-Policy` y el navegador bloquea lo no permitido, incluido `frame-ancestors`.
4. **Verificar** las mismas páginas del paso 1, ahora sin mensajes `Refused to …`.
5. **Revertir** si algo se rompe: borrar `CSP_OBLIGATORIA` (o ponerla en `0`) y desplegar. No hace falta tocar el código.

### Siguiente paso: quitar `'unsafe-inline'`

Hoy `script-src` y `style-src` permiten `'unsafe-inline'`, porque las plantillas tienen 38 bloques `<script>` en línea, 81 manejadores `on…=` y 391 atributos `style=` (detalle por archivo en el reporte de cabeceras). Con `'unsafe-inline'`, la CSP **no frena un XSS que inyecte un script**: lo que protege es `escaparHtml()` y el autoescape de Django. Para quitarlo:
1. Pasar los `onclick=`/`onload=`… a `addEventListener` en archivos `.js` de `static/`.
2. Mover los `<script>` en línea a archivos `.js`, o darles un *nonce* por respuesta (el middleware tendría que generarlo y las plantillas usarlo).
3. Quitar `'unsafe-inline'` de `script-src` primero (es el que protege del XSS) y, más adelante, de `style-src`.

## 8. Logging, monitoreo y alertas (SCRUM-100)

### Dónde ver los logs

Todo se escribe en la consola (stdout/stderr) y Railway lo guarda por servicio:
- **Servicio web** → pestaña **Deployments** → el despliegue activo → **View Logs** (o la pestaña **Logs** del proyecto, filtrando por servicio). Ahí están los errores 500, los logins fallidos y los pagos.
- **Servicio Cron** (`tareas_diarias`) → **Deployments** → cada ejecución tiene sus propios logs. Una corrida con error aparece como fallida.

Cada línea es un evento: `fecha nivel logger mensaje`, con los datos del evento como `clave=valor`. Para buscar, filtra por el nombre del evento:

| Evento | Nivel | Qué registra |
|---|---|---|
| `login_fallido` | WARNING | Usuario enmascarado (`***678-5` o `j***@gmail.com`), `ref` (huella del usuario: la misma para todas las formas de escribir el RUT), IP e intentos |
| `login_bloqueo_activado` / `login_bloqueado` | WARNING | El intento que activó el bloqueo de 5 minutos / un intento que llegó bloqueado |
| `pago_iniciado` | INFO | `tipo` (paquete o videos_extra), `buy_order` y `monto` |
| `pago_aprobado` / `pago_rechazado` | INFO (WARNING con `motivo=monto_distinto` u `orden_desconocida`) | `buy_order`, `monto` recibido, monto `esperado`, `estado` y `codigo` de Transbank, y `activados` (compras que esta respuesta activó). Se registra después de guardar. Lo registran el retorno del alumno y `revisar_pagos_pendientes` |
| `pago_anulado` | INFO | El alumno anuló en Webpay (`buy_order`) |
| `pago_error_transbank` | ERROR | `etapa` (`create`, `commit` o `status`), `buy_order` y el tipo del error |
| `Internal Server Error: /ruta` | ERROR (`django.request`) | Cada error 500, con su traza |
| `tarea_diaria_fallida` / `tareas_diarias_con_error` | ERROR | La tarea que falló (con traza) y el resumen de la corrida |
| `tareas_diarias_completas` | INFO | La corrida terminó bien |
| `alerta_enviada` / `alerta_omitida` / `alerta_no_enviada` | INFO / WARNING / ERROR | El aviso por correo salió, no había `ALERTAS_CORREOS`, o el SMTP falló |

Niveles: la raíz y `django` en WARNING; `django.request` solo ERROR (los 404 y 403 no se registran); las apps del proyecto en INFO. La configuración está en `LOGGING` (`lbwus/settings.py`).

**Datos sensibles.** Nunca se registran contraseñas, tokens de Webpay completos, datos de tarjeta, RUT completos ni correos completos. Cada evento enmascara lo suyo y, además, el formateador de la consola (`FormatoSeguro`, `lbwus/registro.py`) enmascara la clave de las cadenas de conexión (`usuario:***@host`), correos, RUT con guion y tokens de Webpay en todas las líneas, trazas incluidas (por ejemplo, el RUT repetido que trae un error de PostgreSQL o el correo que trae un error SMTP). **Solo reconoce esos patrones:** un secreto con otra forma (un RUT sin guion, una contraseña dentro del texto de un error) no se detecta. Por eso, si agregas un log, no le pases la contraseña ni el objeto completo de un usuario o de una respuesta de Transbank: usa ids, `buy_order` y `type(error).__name__`.

### Alerta cuando falla `tareas_diarias`

En el **servicio Cron**, define `ALERTAS_CORREOS` con uno o más correos del equipo separados por comas (por ejemplo `persona1@dominio,persona2@dominio`). Si alguna tarea falla, al final de la corrida se envía **un** correo con el SMTP ya configurado (`EMAIL_HOST_USER` y `EMAIL_HOST_PASSWORD`, que el Cron también necesita) con las tareas que fallaron y la hora. El correo no lleva trazas ni datos personales: el detalle está en los logs de esa ejecución. El comando igual termina con error, para que Railway marque la corrida como fallida, aunque el correo no salga.

Sin `ALERTAS_CORREOS` no se envía nada (queda `alerta_omitida` en el log).

### Detectar que `tareas_diarias` no corrió: `/salud/`

Si el Cron no arranca (servicio borrado, horario mal puesto, despliegue roto), no hay corrida que falle ni correo que salga. Para eso está `https://lbwus.xyz/salud/`:
- **200** `{"estado": "ok"}`: la última corrida **completa** (todas las tareas sin error) fue hace menos de 26 horas.
- **503** `{"estado": "atrasado"}`: no hubo corrida completa en 26 horas, o nunca hubo una.

No pide login, no pasa por la puerta del sitio (`SITIO_CLAVE`), no tiene límite de intentos, acepta GET y HEAD, no se guarda en caché y no devuelve ningún otro dato. La hora de la última corrida se guarda en la caché compartida (`DatabaseCache`, en PostgreSQL), así que sobrevive a despliegues y reinicios sin migraciones. Si esa caché se limpia, `/salud/` dice `atrasado` hasta la próxima corrida completa: una falsa alarma, nunca un falso `ok`.

**Decisión: un Transbank que no responde no hace fallar la corrida.** Si `revisar_pagos_pendientes` no obtiene respuesta de Transbank (red, caída o token vencido), esa tarea termina bien: cada pago sin respuesta queda como `pago_error_transbank etapa=status` (ERROR) en los logs del Cron, sigue pendiente y se vuelve a consultar en la corrida siguiente. Por eso ese fallo, por sí solo, no envía alerta por correo ni cambia `/salud/`: la corrida cuenta como completa si las demás tareas también terminan bien. Se decidió así porque un corte breve de Transbank no es una falla de LBWUS, y alertar por cada uno haría ignorar las alertas reales. Si los logs muestran `etapa=status` varios días seguidos para la misma `buy_order`, revisa ese pago a mano con Transbank.

Además, el **portal admin** (Resumen General) muestra el aviso "Las tareas diarias están atrasadas" con el mismo criterio. En local, sin Cron, el aviso aparece siempre: es lo esperado.

### Conectar un monitor externo gratuito (UptimeRobot)

1. Crear una cuenta gratuita en UptimeRobot (con un correo del equipo).
2. **Add New Monitor** → tipo **HTTP(s)** → URL `https://lbwus.xyz/salud/` → intervalo de 5 minutos (el mínimo del plan gratuito).
3. En **Alert Contacts**, marcar los correos del equipo.
4. Guardar. Desde ahí, UptimeRobot avisa por correo cuando la respuesta no es 2xx o no hay respuesta.

Con un solo monitor se cubren los dos casos:
- **El sitio está caído** (no responde, o responde 502 desde Railway) → alerta.
- **El Cron no corrió o falló** (503 `atrasado`) → alerta. Para distinguir los casos, abre `/salud/` en el navegador: si muestra `{"estado": "atrasado"}`, el sitio funciona y el problema es el Cron; revisa sus ejecuciones en Railway.

Después de una falla del Cron, la alerta se cierra sola con la próxima corrida completa.

**Pruebas:** `tests/test_logging_alertas.py`. Nunca probar `/salud/` ni las alertas con escaneos o cargas contra producción: basta abrir la URL una vez.
