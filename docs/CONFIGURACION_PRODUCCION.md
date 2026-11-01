# Configuración productiva, almacenamiento y respaldos (S4-13 / SCRUM-93)

Verificado el 31-oct-2026 sobre `main` en 5204d78 más los cambios de SCRUM-93. Producción: Railway (servicio web + PostgreSQL + volumen) y MongoDB Atlas.
**Este documento no contiene valores secretos y no debe contenerlos nunca.** Las claves viven solo en las variables de Railway y en un gestor de contraseñas del equipo.

## 1. Variables de entorno

Todas las lee `lbwus/settings.py`, salvo donde se indica.

| Variable | Para qué | ¿Obligatoria en producción? | Si falta |
|---|---|---|---|
| `SECRET_KEY` | Firma de sesiones, CSRF, tokens de recuperación y nombres de sala Jitsi | **Sí** | Con `DEBUG=False`, el sitio **no arranca** (`ImproperlyConfigured`). En desarrollo usa una clave insegura |
| `DOCUMENTOS_CLAVE` | Clave Fernet de los documentos de apoderados (sección 3) | **Sí** | **El despliegue no arranca**: el `Procfile` corre `check --deploy`, que da el error `apoderados.E001` (o `E002` si la clave no es válida) |
| `DEBUG` | Modo depuración | Sí, `False` | Queda en `True`: muestra la página de error de Django |
| `DATABASE_URL` | PostgreSQL (la crea Railway al enlazar la base) | Sí | Usa SQLite local: en Railway se perdería en cada despliegue |
| `MEDIA_ROOT` | Carpeta de archivos subidos | Sí, `/data/media` (el volumen) | Usa `media/` dentro del contenedor, que se borra en cada despliegue |
| `SECURE_SSL_REDIRECT` | Redirigir HTTP a HTTPS | No (por omisión `True` con `DEBUG=False`) | — |
| `RAILWAY_ENVIRONMENT` | La define Railway. Activa enlaces `https` de allauth y confiar en `X-Forwarded-For` para el límite de intentos (`alumnos/views.py`) | La pone Railway | Enlaces `http` y límite por IP del proxy |
| `PORT` | Puerto de gunicorn (`Procfile`) | La pone Railway | — |
| `EMAIL_HOST`, `EMAIL_PORT` | Servidor SMTP | No (por omisión Gmail, 587) | — |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Cuenta de correo | Sí | Fallan la recuperación de contraseña, el código de Google y los correos de apoderados |
| `DEFAULT_FROM_EMAIL` | Remitente | No (usa `EMAIL_HOST_USER`) | — |
| `MONGODB_URI` | MongoDB Atlas (app `comunidad`) | Sí, si se usa la comunidad | MongoDB queda desactivado y el sitio funciona igual |
| `MONGODB_DB`, `MONGODB_TIMEOUT_MS` | Base de MongoDB y tiempo de espera | No (por omisión `lbwus_dev`, 5000) | **En producción debe ser `lbwus_prod`** |
| `SITIO_CLAVE` | Puerta "Sitio en mantenimiento" (`lbwus/puerta.py`) | No | Sin puerta |
| `SITIO_DOMINIOS_CORREO` | Puerta por dominio de correo (tiene prioridad sobre `SITIO_CLAVE`) | No | Sin puerta por correo |
| `TRANSBANK_PRODUCCION_HABILITADA`, `TRANSBANK_ENVIRONMENT`, `TRANSBANK_COMMERCE_CODE`, `TRANSBANK_API_KEY` | Webpay real | No: sin ellas se usa el ambiente de integración | Sin cobros reales (es lo esperado hoy) |
| `WEBPAY_SIMULACION` | Modo simulación | — | **La lee `settings.py`, pero ningún flujo la usa hoy** (ver el reporte del sprint) |
| `EXIGIR_POSTGRES`, `MONGODB_INTEGRACION` | Solo pruebas | No | — |

El inicio de sesión con Google no usa variables: el `client_id` y el secreto están en la base (Django admin → Social applications).

## 2. Archivos privados

| Qué | Dónde vive | Cómo se entrega |
|---|---|---|
| Títulos de profesores (`Profesor.titulo_archivo`, `titulos/`) | Volumen de Railway en `MEDIA_ROOT=/data/media` | Solo por `admin_portal/titulos.py::ver_titulo` (`@admin_required`) |
| Fotos de perfil (`CustomUser.foto_perfil`, `perfiles/`) | Volumen | **Ninguna vista las sirve hoy** (pendiente conocido: la imagen se ve rota) |
| Documentos de apoderados (carnet, documento del vínculo) | **PostgreSQL, cifrados** (`apoderados.Documento.contenido`, `BinaryField`). No van a disco ni al volumen | Solo por `apoderados/views.py::ver_documento` (`@admin_required`), con marca de agua y registro de cada apertura; se borran al resolver la revisión o a los 30 días |

- `lbwus/urls.py` **no publica `MEDIA_URL`**: no existe ninguna ruta `/media/`. Un GET a `/media/titulos/...` o `/media/perfiles/...` da 404, también para un admin (`tests/test_configuracion_produccion.py::ArchivosPrivadosTests`).
- WhiteNoise sirve solo `STATIC_ROOT` (`/static/`), nunca `MEDIA_ROOT`.

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

`Procfile`: `migrate --noinput` → `collectstatic --noinput` → `check --deploy --fail-level ERROR` → `gunicorn lbwus.wsgi`. Si falta una clave obligatoria, el despliegue falla en el paso 3 y gunicorn no arranca (revisa los logs del despliegue en Railway). Los avisos (`W…`) de `check --deploy` no lo detienen.

| Qué | ¿Sobrevive a un redespliegue o reinicio? | Por qué |
|---|---|---|
| Usuarios, pagos, paquetes, reservas, sesiones de Django y caché del límite de intentos | Sí | PostgreSQL es un servicio aparte. La sesión y la caché usan la base (`DatabaseCache`, la tabla la crea `alumnos/apps.py` después de cada `migrate`) |
| Documentos de apoderados | Sí | Están en PostgreSQL |
| Títulos y fotos | **Solo si el volumen está montado en `/data/media` y `MEDIA_ROOT=/data/media`** | El disco del contenedor se borra en cada despliegue |
| Estáticos | Se regeneran | `collectstatic` en cada inicio |
| Comunidad (MongoDB) | Sí | Atlas es externo |

Con `DEBUG=False`, `CompressedManifestStaticFilesStorage` da error 500 si una plantilla pide un estático que no existe. Las pruebas no usan el manifiesto (`lbwus/test_runner.py`), así que no necesitan `collectstatic`; a cambio, `tests/test_configuracion_produccion.py::EstaticosTests` corre `collectstatic` con el almacenamiento de producción en una carpeta temporal (falla si un CSS apunta a un archivo inexistente) y revisa que cada `{% static '...' %}` literal de las plantillas esté en el manifiesto. Las rutas armadas con variables no se revisan.

**Cron de documentos.** `python manage.py borrar_documentos_vencidos` borra los documentos de apoderados con más de 30 días. No está en el `Procfile`: hay que crearlo en Railway como un servicio Cron diario (mismo repositorio y variables, comando `python manage.py borrar_documentos_vencidos`). **Verificar que exista**; sin él, los documentos pendientes no se borran solos.

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
4. **Claves:** `SECRET_KEY` y `DOCUMENTOS_CLAVE` van **solo** en el gestor de contraseñas, nunca junto a los respaldos. Sin `DOCUMENTOS_CLAVE`, los documentos del respaldo de PostgreSQL no se pueden leer, y eso es lo que se busca.

## 6. `check --deploy`

Con `DEBUG=False` y valores de prueba para `SECRET_KEY` y `DOCUMENTOS_CLAVE`: **"System check identified no issues"**. Sin `DOCUMENTOS_CLAVE`: error `apoderados.E001` (detiene el `Procfile`). Sin `SECRET_KEY`: `ImproperlyConfigured`, ningún comando arranca. HSTS, cookies seguras y la redirección a HTTPS ya están en `settings.py` cuando `DEBUG=False`.
