# Informe Técnico de Auditoría de Código: Errores, Vulnerabilidades y Carencias — LBWUS

**Proyecto:** LBWUS (Learn Better With Us)  
**Fecha de auditoría:** 22 de noviembre de 2026  
**Rama / Commit auditado:** `Franco` (`1789547`)  
**Alcance:** ~185 archivos Python y JavaScript de aplicación (excluyendo migraciones y tests), 174 plantillas HTML, configuración (`lbwus/`), comandos de gestión, dependencias (`requirements*.txt`), despliegue (`Procfile`) y pipeline CI/CD (`.github/`).  
**Metodología:** Auditoría estática de solo lectura dividida por dominios funcionales (Seguridad/Auth, Pagos/Alumnos/JS, Admin/Profesor/Agenda, Apoderados/Mensajes/Observaciones, Soporte/Supresiones/Comunidad/Reseñas/Notificaciones/Requerimientos, e Infraestructura/Plantillas/QA), con verificación directa sobre código fuente y motor de plantillas.

---

## 1. Resumen Ejecutivo

La plataforma cuenta con protecciones estructurales relevantes en ORM, plantillas Django y trazabilidad de migraciones, pero presenta **defectos críticos de seguridad, estabilidad en producción, integridad financiera y protección de menores** que deben corregirse antes de abrir el sistema a usuarios reales, además de **carencias transversales** en observabilidad (`LOGGING`), endurecimiento HTTP (CSP/SRI/Rate Limiting), rendimiento (consultas N+1 y carga de BLOBs en RAM) y pipeline CI.

### Tabla Resumen de Hallazgos

| Categoría | Crítico | Alto | Medio | Bajo | Total |
|---|---:|---:|---:|---:|---:|
| **Parte I — Errores, Bugs y Vulnerabilidades** | 10 | 15 | 18 | 8 | **51** |
| **Parte II — Carencias y Deficiencias Estructurales** | 0 | 7 | 5 | 1 | **13** |
| **Total Consolidado** | **10** | **22** | **23** | **9** | **64** |

### Controles y Aspectos Sólidos Verificados (Sin Defecto)

1. **Ausencia de SQL inyectable por interpolación:** `0` ocurrencias de `.raw()`, `.extra()` ni `cursor.execute()` en el código de aplicación.
2. **Sin escape deshabilitado en plantillas HTML:** `0` usos de `|safe`, `mark_safe`, `format_html` ni `{% autoescape off %}` en plantillas web (el motor `'correo'` con `autoescape: False` en `lbwus/settings.py:170-176` está restringido a correos de texto plano `.txt`).
3. **Grafo de migraciones íntegro:** Las 13 apps con modelos (90 archivos de migración) presentan exactamente 1 nodo hoja intra-app, sin ramas divergentes ni ciclos.
4. **Tabla de caché persistente automatizada:** `lbwus_cache_table` (`DatabaseCache`) se crea automáticamente tras cada `migrate` mediante la señal `post_migrate` en `alumnos/apps.py:6-17`.
5. **Control de propiedad en descargas privadas y ausencia de ReDoS:** No se hallaron IDOR directos en descarga de documentos cifrados (`apoderados/views_revision.py:ver_documento`), títulos (`admin_portal/titulos.py:ver_titulo`), especializaciones ni cancelación de reservas (`alumnos/services.py`); las expresiones regulares de `mensajes/filtro.py` no sufren backtracking catastrófico.
6. **Integridad de plantillas y control de secretos locales:** Todas las etiquetas `{% url %}`, `{% extends %}` y `{% include %}` de las 174 plantillas resuelven a nombres válidos; `db.sqlite3` local está ignorado por `.gitignore:3` y no está rastreado en Git.

---

## PARTE I — ERRORES, BUGS Y VULNERABILIDADES VERIFICADAS

### 🔴 Severidad Crítica (`AUD-CRIT-01` – `AUD-CRIT-10`)

#### `AUD-CRIT-01` — Secuestro de cuentas vía Google OAuth (incluidos `ADMIN` y `SOPORTE`) por auto-vinculación sobre correo no verificado
- **Ubicación:** `alumnos/google_adapter.py:72-95`, `lbwus/settings.py:135-142`, `alumnos/views.py:189-210`, `user_profesor/views.py:95-116, 488-509`
- **Evidencia:** El registro local crea usuarios con `CustomUser.email` sin verificar propiedad del correo. En `LbwusSocialAdapter.pre_social_login`, cuando ingresa alguien con Google y `not sociallogin.is_existing`, se busca cualquier cuenta con `email__iexact`, se ejecuta `sociallogin.connect(request, user)` sin invalidar la contraseña previa y se inicia sesión (`entrar_al_portal(request, user)`). Se desactivó `SOCIALACCOUNT_EMAIL_AUTHENTICATION` sin reemplazo de verificación.
- **Impacto:**
  1. *Pre-account takeover:* Un atacante registra localmente el correo Gmail de una víctima con una clave propia; cuando la víctima usa «Continuar con Google», vincula su identidad Google a la cuenta del atacante y este conserva acceso mediante su contraseña.
  2. *Secuestro de cuentas privilegiadas:* `pre_social_login` no excluye `Tutor` (`ADMIN`) ni `AgenteSoporte` (`SOPORTE`), permitiendo tomar cuentas con correo no verificado o mal tipeado.
- **Remediación:** Exigir verificación de correo al registrar/cambiar email en flujos locales, no auto-vincular cuentas existentes sin re-autenticación de clave actual y excluir roles `ADMIN`/`SOPORTE` de la vinculación automática por email.

#### `AUD-CRIT-02` — Stored XSS en el Portal de Administración en botones de eliminación (`onsubmit`)
- **Ubicación:** `admin_portal/templates/admin_portal/alumnos_list.html:68-70`, `admin_portal/templates/admin_portal/includes/dashboard/usuarios.html:71-74` (contrastar con `admin_portal/templates/admin_portal/asignaturas_adm.html:54`)
- **Evidencia:**
  ```html
  onsubmit="return confirm('¿Eliminar a {{ alumno.user.first_name }}?')"
  onsubmit="return confirm('¿Seguro que quieres eliminar a {{ alumno.user.first_name }}?')"
  ```
- **Impacto:** El parser HTML decodifica las entidades `&#x27;` dentro de atributos antes de entregar la cadena al motor JS. Un apellido legítimo con apóstrofe (`O'Higgins`) genera `SyntaxError` y **envía la eliminación sin confirmación**; un `first_name` manipulado en registro público ejecuta JavaScript arbitrario en la sesión privilegiada del administrador (con `CSP_OBLIGATORIA=False` y `'unsafe-inline'`).
- **Remediación:** Usar atributos `data-*` + `addEventListener` externo (o aplicar `|escapejs` como mitigación inmediata).

#### `AUD-CRIT-03` — Escape anti-XSS roto en el Portal del Alumno (`window.escaparHtml` es siempre `undefined`)
- **Ubicación:** `alumnos/templates/alumnos/base_alumno.html`, `alumnos/templates/alumnos/Alumno_pag1.html`, `alumnos/templates/alumnos/includes/panel/js/datos.js:15-16, 33-35`, `alumnos/templates/alumnos/includes/panel/js/horarios.js:68-69, 93-95, 124-128, 176-180`
- **Evidencia:** `base_alumno.html` y `Alumno_pag1.html` no cargan `alumnos/java/lbwus-utils.js`. En `datos.js:33` se declara `const escaparHtml = ...`, que en JS crea un binding léxico global **no adjunto a `window`**. Todas las expresiones `window.escaparHtml ? window.escaparHtml(x) : x` en `datos.js:15` y `horarios.js:124-125, 176-177` evalúan `undefined` y toman la rama **sin escapar**, inyectando valores en `planBadge.innerHTML` y `Swal.fire({ html })` (incluyendo `this.dataset.asig`, decodificado automáticamente por el DOM).
- **Impacto:** Regresión respecto a `docs/INFORME_SEGURIDAD_S23_XSS.md`: cualquier carga útil HTML/JS en el nombre de una asignatura o plan se ejecuta en el navegador del alumno (`tests/test_seguridad_s23_xss.py` no lo detecta por buscar solo subcadenas).
- **Remediación:** Cargar `lbwus-utils.js` en `base_alumno.html` o asignar `window.escaparHtml = escaparHtml` en `datos.js` (idealmente usando `textContent` / construcción DOM segura en lugar de HTML crudo).

#### `AUD-CRIT-04` — Sala virtual Jitsi estática por `Clase`, acceso perpetuo sin ventana horaria y `en_vivo` nunca se apaga
- **Ubicación:** `alumnos/sala_virtual.py:22-28, 45-48, 66-81`, `alumnos/models/clases.py:376-383`, `alumnos/templates/alumnos/sala_virtual.html:293, 365`
- **Evidencia:**
  - `nombre_sala_jitsi(clase)` deriva la sala únicamente de `clase.id_clase` sobre el dominio público `meet.jit.si`. Todas las sesiones 1-a-1 pasadas y futuras de esa asignatura/profesor comparten **la misma sala**.
  - `Inscripcion.puede_unirse` (`models/clases.py:377-383`) solo valida `estado == ESTADO_CONFIRMADA` y sesión no cancelada, **sin validar ventana horaria**, y nada cambia `SesionClase.estado` a `'finalizada'`.
  - `iniciar_directo` (`sala_virtual.py:78`) fija `clase.en_vivo = True`, pero no existe ningún endpoint ni acción para volverlo a `False`.
- **Impacto:** Cualquier ex-alumno con una clase pasada o una reserva futura (o inscripción `sesion=None`) conserva acceso perpetuo al enlace y a la sala Jitsi `meet.jit.si/<sala>`, pudiendo ingresar durante la clase privada 1-a-1 de otro alumno (incluyendo menores de edad). Además, el formulario de temas/descripción en directo queda oculto para siempre tras la primera clase.
- **Remediación:** Derivar el nombre de sala por `SesionClase` (no por `Clase`), restringir `puede_unirse` a la ventana horaria activa de esa sesión, agregar acción/cierre de `en_vivo = False` (o mover estado vivo a `SesionClase`) y migrar a Jitsi privado con JWT (`LBW-28`).

#### `AUD-CRIT-05` — Corrupción de memoria (`SIGSEGV`) en `pypdfium2` bajo `gthread` y DoS por OOM en subida pública de documentos
- **Ubicación:** `apoderados/documentos.py:51-110`, `Procfile:1`, `apoderados/views.py:99-105`, `apoderados/forms.py:114-121, 161-170`
- **Evidencia:**
  - `Procfile:1` levanta Gunicorn con `--worker-class gthread --threads 4`. `apoderados/documentos.py:89-99` llama a `pdfium.PdfDocument` y `render()` **sin `threading.Lock()`**, pese a que `libpdfium` no es thread-safe.
  - `preparar()` (`documentos.py:64-71`) ejecuta `imagen.load()` (descompresión total en RAM) **antes** de verificar `formato in FORMATOS` y sin restringir `Image.MAX_IMAGE_PIXELS` ni dimensiones en cabecera. Un PNG comprimido de ~200 KB (`13.000 × 13.000` px) pasa el límite por defecto de Pillow y consume >670 MB al decodificarse.
  - `/apoderados/registro/` es público (sin login ni rate limit) y procesa **dos** archivos (`carnet_frente`, `carnet_reverso`) en `clean_field` antes de validar RUT, correo o contraseña.
- **Impacto:** Dos peticiones concurrentes con PDF pueden provocar `SIGSEGV` tumbando todo el worker; imágenes o PDFs especialmente construidos provocan OOM kill o bloqueo de los 4 hilos del servidor.
- **Remediación:** Proteger todo uso de `pypdfium2` con `threading.Lock()` (o aislarlo en subproceso con timeout/límite de memoria); validar `imagen.format` y dimensiones máximas **antes** de `imagen.load()`, fijar `Image.MAX_IMAGE_PIXELS`, pre-renderizar PDFs al subir con cotas estrictas y añadir rate limiting por IP en `/apoderados/registro/`.

#### `AUD-CRIT-06` — OOM en la cola de revisión de soporte (`/apoderados/revision/`) por carga masiva de BLOBs cifrados
- **Ubicación:** `apoderados/views_revision.py:31-37`, `apoderados/models.py:449`, `apoderados/templates/apoderados/revision.html:32, 72`
- **Evidencia:** `revision()` ejecuta `.prefetch_related('documentos')` sobre todos los `Apoderado` y `Vinculo` pendientes sin `.defer('contenido')` ni paginación. La plantilla solo utiliza `d.pk` y `d.get_tipo_display`, pero Django descarga y mantiene en RAM cada `BinaryField` `contenido` completo (~6,7 MB por archivo Fernet; hasta ~13,4 MB por apoderado).
- **Impacto:** Con pocas decenas de revisiones pendientes, abrir `/apoderados/revision/` agota la memoria del contenedor en Railway.
- **Remediación:** Usar `Prefetch('documentos', queryset=Documento.objects.defer('contenido'))` y paginar las tablas de revisión.

#### `AUD-CRIT-07` — Reembolsos Transbank: `except Exception: reembolso.delete()` destruye el candado anti doble-reembolso + carreras
- **Ubicación:** `alumnos/reembolsos.py:62, 75-80, 83-118`, `alumnos/models/videos.py:143-163`, `alumnos/views_soporte_videos.py:127-135`
- **Evidencia:**
  - `ReembolsoTransbank(confirmado=None)` se crea antes de llamar a Transbank precisamente para bloquear segundos intentos si la respuesta de red se pierde. Sin embargo, `reembolsos.py:104-105` captura `except Exception` y ejecuta `reembolso.delete()` incondicionalmente.
  - `intentar()` no bloquea `DevolucionVideos` (`select_for_update`) ni verifica `devolucion.aprobada`; `_repartir()` calcula saldos sin bloquear `PaqueteClases`; `_pedir()` solo rechaza cuando `type == 'NULLIFIED' and response_code != 0`.
- **Impacto:** Ante un `ReadTimeout` después de que Transbank procesó la devolución, el registro se borra y soporte puede reintentar en Transbank (en reembolsos parciales sobre multi-video) o escalar y transferir manualmente -> **doble reembolso**. Dos procesos concurrentes (`reintentar_reembolso` y `devolucion_hecha`, o dos devoluciones del mismo paquete) pueden superar el monto pagado.
- **Remediación:** No borrar `ReembolsoTransbank` ante errores de red/timeout (solo ante rechazos explícitos confirmados de negocio); bloquear `DevolucionVideos` y `PaqueteClases` con `select_for_update()`, verificar `devolucion.aprobada` y validar explícitamente los tipos/códigos exitosos de Transbank.

#### `AUD-CRIT-08` — Webpay `confirmacion`: recarga (F5) muestra falso "Pago Rechazado", anulaciones/timeouts bloquean cuota de videos extra y `SameSite=Lax` pierde la sesión
- **Ubicación:** `alumnos/webpay.py:225-286`, `alumnos/videos_extra.py:54-62`, `alumnos/management/commands/revisar_pagos_pendientes.py:33-44`, `lbwus/settings.py:67-74`, `alumnos/templates/alumnos/confirmacion.html:47-51, 64-66`
- **Evidencia:**
  1. **Recarga -> falso rechazo:** `confirmacion()` invoca `_tx().commit(token)` en cada acceso sin revisar si la orden ya está `ESTADO_ACTIVA` ni usar patrón PRG. Al recargar (F5), Transbank devuelve error 422 (ya confirmada), `except Exception: resp = {}` lo silencia y muestra **«Pago Rechazado»** con botón *«Intentar de nuevo»* tras un cobro ya exitoso.
  2. **Cuota `MAX_VIDEOS_EXTRA` bloqueada:** Con `tbk_token` (anulación) o en timeout (solo llegan `TBK_ORDEN_COMPRA` + `TBK_ID_SESION`), la orden nunca pasa a `ESTADO_RECHAZADA`. Como `videos_extra.comprados()` suma compras `pendiente`, la cuota queda bloqueada; y en `revisar_pagos_pendientes.py:35-38`, si `status()` falla (ej. token expirado), hace `continue` y la bloquea permanentemente.
  3. **Pérdida de sesión en POST cross-site:** Al no configurar `SESSION_COOKIE_SAMESITE` (default `'Lax'`), los retornos `POST` desde el dominio externo de Transbank no envían la cookie `sessionid`: el comprobante renderiza al usuario como anónimo, enviando a un apoderado hacia `alumno_pag1` y mostrando a menores acciones restringidas.
- **Remediación:** Verificar estado previo de la orden antes de llamar `commit()` y aplicar redirect PRG tras confirmar; marcar inmediatamente `ESTADO_RECHAZADA` en `tbk_token` y timeouts (y rechazar órdenes expiradas tras el límite de Transbank en `revisar_pagos_pendientes`); configurar adecuadamente la sesión post-Webpay (p. ej. `SameSite=None; Secure` o desvincular la vista comprobante de la cookie en el callback intermedio).

#### `AUD-CRIT-09` — Flujo roto de invitación adolescente: apoderado ya verificado queda huérfano sin ticket de soporte
- **Ubicación:** `apoderados/views.py:511-515`, `apoderados/models.py:268-273, 370-380`, `apoderados/views_revision.py:34-37`
- **Evidencia:** En `invitacion()`, `pendiente.aceptar(...)` ejecuta `self.vinculo.abrir_ticket_si_revisable()` **antes** de que `form.guardar_documento(vinculo)` guarde el certificado de nacimiento. Al ser `documentos_completos == False` en ese punto, no se crea ningún ticket, y `guardar_documento()` no vuelve a invocar `abrir_ticket_si_revisable()`.
- **Impacto:** Si el apoderado ya tenía su identidad en `Apoderado.VERIFICADO`, el vínculo queda en `PENDIENTE`, **invisible** en `apoderados/views_revision.py` (`tickets__in=mios`), sin posibilidad de re-subir el documento (`documentos_completos == True`), hasta expirar a los 30 días.
- **Remediación:** Llamar `vinculo.abrir_ticket_si_revisable()` después de `form.guardar_documento(vinculo)` dentro de la misma transacción.

#### `AUD-CRIT-10` — Supresión de cuentas (`supresiones`) incompleta y evadible por usuarios multi-rol
- **Ubicación:** `supresiones/datos_propios.py:60-100`, `supresiones/evaluacion.py:64-70, 98-163`, `mensajes/supresion.py:33, 53, 61-76`, `resenas/models.py:80-87, 112-138`
- **Evidencia:**
  1. **Datos personales y multimedia sin eliminar:** `_limpiar_profesor` nunca borra sus videos MP4 en MongoDB GridFS (`videos.files`/`videos.chunks`); las `Resena` de alumnos seudonimizados siguen públicas firmadas literalmente como **`"Cuenta E."`** (`autor_publico` sobre `'Cuenta eliminada'`); permanecen intactos `ReporteResena`, `Invitacion` con `vinculo=None`, `SolicitudAdolescente`, `alumnos.models.Reporte`, `SolicitudClaseExtra`, `MensajeContacto` y `Clase.descripcion_vivo`/`temas_vivo`/`en_vivo`.
  2. **Bypass multi-rol:** `evaluar()` (`evaluacion.py:158`) evalúa únicamente el primer rol devuelto por `resolver_rol(user)` (`ALUMNO > PROFESOR > ADMIN > SOPORTE > APODERADO`), mientras `datos_propios.limpiar()` limpia los tres perfiles (`alumno`, `profesor`, `apoderado`). Un usuario con dos perfiles (ej. `Profesor` + `Apoderado` de un menor) evade los bloqueos de su segundo perfil.
  3. **Evaluación incompleta y carreras:** `_bloqueos_comunes` ignora tickets de verificación con `autor=None`; `_profesor` no bloquea videos pagados pendientes sin clases disponibles ni deuda negativa oculta por `max(0, ...)`; `_alumno` no bloquea `DevolucionVideos` pendientes; `supresiones/solicitud.py:73-84` no bloquea al `CustomUser`; y `datos_propios.py:68-89` borra archivos del disco dentro de `transaction.atomic()` antes del commit.
- **Remediación:** Evaluar bloqueos y categorías sobre **todos** los perfiles del usuario; extender `datos_propios.limpiar()` a GridFS, reseñas/reportes y campos libres pendientes; bloquear `CustomUser` en `ejecutar()` y diferir borrados físicos a `transaction.on_commit()`.

---

### 🟠 Severidad Alta (`AUD-ALT-01` – `AUD-ALT-15`)

#### `AUD-ALT-01` — Fuga de `DATABASE_URL` (credenciales PostgreSQL en claro) en reportes de error
- **Ubicación:** `lbwus/reporte_errores.py:18-25`, `lbwus/settings.py:189`
- **Evidencia:** `FiltroReporteErrores.hidden_settings` filtra `URI` (para `MONGODB_URI`), pero **no** `URL`, dejando `settings.DATABASE_URL` (con usuario y clave de PostgreSQL) expuesto en claro en reportes de excepción (`DEBUG=True` o correos de error).
- **Remediación:** Agregar `URL` a `hidden_settings` (o almacenar la variable como `_DATABASE_URL`).

#### `AUD-ALT-02` — Bypass total del rate limit por IP en login, condición de carrera y endpoints sin límite
- **Ubicación:** `alumnos/views.py:160-173, 436-462`, `lbwus/urls.py:20`, `lbwus/puerta.py:163-208`
- **Evidencia:** `custom_login` ejecuta `cache.delete(clave_cache_ip)` tras un login exitoso (`views.py:453`), permitiendo a un atacante con una cuenta propia probar 14 claves ajenas, loguearse 1 vez para resetear el contador de su IP y repetir indefinidamente. Además, `cache.get()` + `cache.set()` es no atómico (TOCTOU bajo 4 hilos), `/admin/login/` no tiene límite de intentos, y `/puerta/` carece de rate limit en `PuertaForm` y omite `ESPERA_REENVIO` cuando `accion == 'correo'`.
- **Remediación:** No borrar `clave_cache_ip` al autenticar con éxito (solo `clave_cache_user`); usar operaciones atómicas de incremento; proteger `/admin/login/` y `/puerta/` con cooldown y límite de intentos.

#### `AUD-ALT-03` — Autorización por sesión sin verificar vigencia/propiedad del perfil en BD + bypass de `is_active` y `debe_renovar_clave`
- **Ubicación:** `alumnos/decorators.py:22-32, 53-67, 101-108`, `soporte/permisos.py:63-94`, `notificaciones/views.py:11`
- **Evidencia:**
  - `_rol_requerido` verifica `request.session.get(rol.clave_sesion)` sin comprobar en BD que `perfil_de(request.user, rol)` exista ni coincida con la PK guardada (sesiones vigentes hasta 14 días conservan acceso tras revocación de `Tutor`/`AgenteSoporte`/`Profesor`).
  - `@reporta_required` y `notificaciones/views.py` no comprueban `request.user.is_active` (con sesión abierta tras desactivación siguen entrando).
  - `@alumno_required_json` y `@sesion_iniciada_required` omiten `debe_renovar_clave(request.user)`, permitiendo a ex-menores con clave conocida por su apoderado invocar reservas, clases extra, videos y sala virtual.
- **Remediación:** Validar pertenencia real del perfil en `_rol_requerido`, verificar `is_active` en `reporta_required` y `notificaciones`, y exigir `not debe_renovar_clave(request.user)` en `alumno_required_json` y `sesion_iniciada_required`.

#### `AUD-ALT-04` — Reprogramación de clases del alumno completamente inoperante en el frontend + decorador erróneo
- **Ubicación:** `alumnos/templates/alumnos/includes/panel/mis_clases.html:39`, `alumnos/templates/alumnos/includes/panel/js/horarios.js:67-68, 90-98, 175-210`, `alumnos/reservas.py:198-213`
- **Evidencia:** `horarios.js:68` renderiza botones `.btn-mover-sesion`, pero las líneas `90-98` solo registran listener `click` sobre `.btn-reservar-sesion`; `confirmarReprogramacion` nunca se invoca desde ningún archivo. Además, `reprogramar_inscripcion` usa `@alumno_required` (devuelve 302 HTML ante sesión expirada) en vez de `@alumno_required_json`, rompiendo `res.json()`.
- **Remediación:** Vincular el evento `click` de `.btn-mover-sesion` hacia `confirmarReprogramacion(...)` y cambiar el decorador de `reprogramar_inscripcion` a `@alumno_required_json`.

#### `AUD-ALT-05` — Fallo por cambio de horario de verano (DST `America/Santiago`) en `agenda/bloques.py` colapsa `generar_bloques`
- **Ubicación:** `agenda/bloques.py:23-36, 53-58`, `agenda/franjas.py:19-30`, `agenda/models.py:38-53`, `agenda/views.py:22-33`, `agenda/management/commands/generar_bloques.py:12-15`
- **Evidencia:** `franjas.agregar()` no restringe horarios al rango `HORAS` (`06:00`–`23:00`) ni valida segundos/offsets (`tzinfo`). Al crear una franja dominical `00:00`–`01:00`, el primer domingo de septiembre en Chile (`00:00` no existe por salto DST `-04` → `-03`), `inicio + DURACION` realiza aritmética de reloj de pared (PEP 495) produciendo el **mismo instante UTC** (`duración = 0`). PostgreSQL rechaza el `bulk_create` con `IntegrityError` (`sesion_fin_posterior_a_inicio`). Como `franjas.agregar()` no envuelve en `transaction.atomic()`, la franja queda guardada y rompe el cron diario `generar_bloques` para todos los profesores siguientes durante 4 semanas.
- **Remediación:** Restringir horas válidas y validar `tzinfo is None`/segundos en `HorarioSemanal.clean()`, calcular duración en UTC (`astimezone(timezone.utc) + DURACION`), saltar horas locales inexistentes, envolver `franjas.agregar()` en `transaction.atomic()` y aislar errores por profesor en `generar_bloques`.

#### `AUD-ALT-06` — Condiciones de carrera en `agenda`, `videoteca`/`entregas`, `titulo.resolver`, `mensajes` y cascada destructiva de auditoría
- **Ubicación:** `agenda/bloques.py:38-73`, `agenda/franjas.py:15-30`, `user_profesor/entregas.py:89-103`, `user_profesor/videoteca.py:150-167`, `user_profesor/titulo.py:40-82`, `mensajes/retencion.py:47-52`, `mensajes/revision.py:41-49, 85-112`, `mensajes/models.py:118-150`
- **Evidencia:**
  1. `quitar_franja` ejecuta `.delete()` sin bloquear `Profesor` ni `SesionClase`, pudiendo borrar en cascada una `Inscripcion` pagada recién creada; `bloques.generar` lee `existentes` fuera de transacción y sin `UniqueConstraint`, duplicando bloques; `franjas.agregar` permite franjas solapadas concurrentes.
  2. `entregas.compartir` y `videoteca.eliminar` no comparten bloqueo (`Profesor.select_for_update()`), permitiendo borrar el MP4 en GridFS mientras se confirma `VideoCompartido` y se acredita el pago al profesor.
  3. `titulo.resolver()` valida estado fuera de `transaction.atomic()`, descarta el resultado de `select_for_update()` y guarda sin `update_fields`, permitiendo sobreescribir decisiones y campos concurrentes.
  4. `mensajes/retencion.borrar_inactivas()` y `revision.liberadas()` no usan `select_for_update()` sobre `Conversacion` y `liberadas()` no exige `con_ticket_abierto=False`, pudiendo eliminar conversaciones con un reporte `CONDUCTA` recién abierto.
  5. `AccesoConversacion` y `DecisionRetencion` tienen `on_delete=CASCADE` hacia `Conversacion`/`ReporteConversacion`, destruyendo todo el historial de auditoría al borrarse conversaciones liberadas.
- **Remediación:** Adquirir `select_for_update()` en todas las transiciones críticas, agregar `UniqueConstraint` en `SesionClase(clase, fecha_hora_inicio)`, exigir `con_ticket_abierto=False` en `liberadas()`, y cambiar `AccesoConversacion`/`DecisionRetencion` a `on_delete=SET_NULL`.

#### `AUD-ALT-07` — Error financiero en `saldos.valores_videos` / `devoluciones_videos` y falta de atomicidad/validación de monto en `webpay.registrar_respuesta`
- **Ubicación:** `user_profesor/saldos.py:20-35`, `alumnos/devoluciones_videos.py:30-33, 60-61`, `alumnos/models/retiros.py:104-129`, `alumnos/webpay.py:196-222`, `alumnos/models/pagos.py:156-162`
- **Evidencia:**
  - `valores_videos` promedia dinámicamente `(monto_videos + extra_monto) // (videos + extra_videos)` sobre *todos* los videos del paquete. Si un alumno compra extras en promoción tras haber consumido y cobrado el profesor los videos del agregado, el valor unitario cae retroactivamente creando deuda oculta al docente (enmascarada por `max(0, ...)`) y `DevolucionVideos` intenta reembolsar **más dinero del pagado por los extras** (p. ej. \$14.355 sobre \$13.500). Además, `SolicitudRetiro.aprobar` y `marcar_pagado` no revalidan saldo tras un retiro de video.
  - `webpay.registrar_respuesta` corre fuera de `transaction.atomic()` (anulando `transaction.on_commit`), `PaqueteClases.confirmar_pago` hace dos `UPDATE` no atómicos, y cuando `esperado is None` (`webpay.py:210`) no valida ni rechaza el monto.
- **Remediación:** Fijar el valor unitario de cada video al momento de entregar o asignar FIFO contra el agregado y cada `CompraVideosExtra`; revalidar saldo neto antes de aprobar/pagar retiros; envolver `registrar_respuesta` y `PaqueteClases.confirmar_pago` en `transaction.atomic()` rechazando órdenes desconocidas.

#### `AUD-ALT-08` — Debilitamiento del flujo de cuenta bancaria docente y formularios sin `method="POST"` / `{% csrf_token %}`
- **Ubicación:** `user_profesor/views.py:264-365`, `user_profesor/cambio_cuenta.py:23-64`, `user_profesor/templates/user_profesor/includes/panel/saldo.html:35-99`, `user_profesor/templates/user_profesor/videos.html:49-64`, `alumnos/templates/alumnos/contactos.html:50-51`, `alumnos/templates/alumnos/sala_virtual.html:295-299`
- **Evidencia:**
  - `actualizar_perfil_prof` (`views.py:312`) modifica `user.email` sin exigir contraseña actual ni verificación, permitiendo evadir el doble factor por correo del cambio de cuenta bancaria; la primera cuenta bancaria se guarda sin contraseña ni bloqueo temporal.
  - `confirmar_cambio_cuenta` ejecuta la confirmación vía **`GET`** (susceptible a CSRF y escáneres SafeLinks), sin `select_for_update()` ni `@never_cache`, exponiendo metadatos en Base64 firmado en la URL.
  - Los 3 formularios de `saldo.html` (incluyendo `numero_cuenta` y `password`), `videos.html:49` (sin `enctype="multipart/form-data"` ni `POST`/`csrf_token`), `contactos.html:50` y `sala_virtual.html:295` omiten `method="POST"` (y los cuatro primeros también `{% csrf_token %}`). Si el JS falla, envían credenciales y `numero_cuenta` en texto plano por `GET`.
- **Remediación:** Exigir clave actual + confirmación al cambiar correo; cambiar la confirmación de cuenta bancaria a página `GET` + botón `POST` con `select_for_update()` y token opaco; añadir `method="post"` y `{% csrf_token %}` a todos los formularios afectados.

#### `AUD-ALT-09` — Brechas críticas en protección de menores y mensajería
- **Ubicación:** `apoderados/forms.py:135, 280-284`, `apoderados/views.py:370-385, 448-524`, `soporte/permisos.py:72-79`, `observaciones/views.py:19-25`, `observaciones/panel.py:17-20`, `mensajes/filtro.py:14-36`, `mensajes/servicio.py:40-47`, `mensajes/panel.py:53, 71`
- **Evidencia:**
  1. **Oráculo de RUT de menores:** `VincularEstudianteForm.clean()` ejecuta `_menor_con_rut` aunque falten `documento` o `acepta_declaracion`, permitiendo confirmar si un RUT corresponde a un menor activo sin crear vínculo ni disparar alertas a los padres.
  2. **Fuga de nombre completo de menores:** `_CuentaForm` guarda `"Nombre completo"` íntegro en `user.first_name`, mientras `mensajes`, `observaciones` y correos/enlaces de invitación asumen que `first_name` es solo el nombre de pila.
  3. **Permisos rotos tras cumplir 18 años:** `revocar_vinculo` y `revocar_vinculo_admin` no verifican `es_menor(vinculo.alumno.user)`, permitiendo a un ex-apoderado (o líder) revocar el vínculo y **cancelar clases futuras del estudiante ya adulto**; `estudiantes_que_reporta` permite abrir tickets en nombre del adulto; `subir_documento_vinculo` e invitaciones tampoco bloquean mayores de 18.
  4. **Observaciones sobre cuentas suprimidas:** `observaciones/panel.py` y `observaciones/views.py` no filtran `alumno__user__suprimida__isnull=True`, permitiendo crear observaciones sobre alumnos ya eliminados.
  5. **Evasión trivial del filtro de contacto (`mensajes/filtro.py`):** No elimina caracteres Unicode invisibles (`Cf`, como `\u200b` ZWSP), no detecta URLs/acortadores (`t.me/`, `bit.ly/`, `meet.google.com/`), teléfonos con espacios/guiones (`9 - 1234 - 5678`) ni direcciones con números (`Av. 11 de Septiembre 1234`), afectando tanto al chat como a `observaciones` (canal directo profesor → menor).
  6. **Chat perpetuo y cuentas eliminadas:** `ids_profesores_con_relacion` consulta `Inscripcion` con `ESTADOS_ACTIVOS` (`'confirmada'` incluye clases pasadas de hace años) y sin excluir profesores suprimidos (`user__suprimida__isnull=True`), otorgando permiso eterno de chat y re-listando a `"Cuenta eliminada"`.
- **Remediación:** Validar errores de campos previos antes de `_menor_con_rut`; separar nombre de pila de apellidos; exigir `es_menor()` en revocaciones, vínculos y reportes de apoderados; filtrar cuentas suprimidas en `observaciones` y `mensajes`; normalizar caracteres `Cf` y ampliar reglas de `mensajes/filtro.py`; limitar `ids_profesores_con_relacion` a reservas `proximas()` activas y paquetes vigentes de docentes activos.

#### `AUD-ALT-10` — RUT sin normalización canónica (duplicados, fallos de login y `DataError` HTTP 500)
- **Ubicación:** `alumnos/utils.py:55-68`, `alumnos/forms.py:32-37, 77-83, 112-135`, `alumnos/backends.py:11-31, 94-100`, `apoderados/forms.py:70-74, 144-150`, `admin_portal/forms.py:119-129`, `user_profesor/views.py:39-125, 454-537`
- **Evidencia:** Los formularios validan dígito verificador pero almacenan y comparan texto crudo (`12.345.678-5`, `12345678-5`, `123456785`), permitiendo múltiples cuentas con el mismo RUT. En PostgreSQL case-sensitive, `variaciones_rut()` omite variantes con `'k'` minúscula con puntos y variantes sin guión cuando la entrada trae guión, rompiendo el login. Además, `AlumnoForm` y los formularios manuales de `user_profesor` omiten `max_length` (provocando `DataError` 500 en `rut` 12, `telefono` 20, `direccion` 100) y crean `CustomUser` + perfil sin `transaction.atomic()`.
- **Remediación:** Normalizar todo RUT con `normalizar_rut_canonico()` antes de validar unicidad y guardar; buscar por `variaciones_rut` case-insensitive en `usuario_existe()`; añadir `max_length` y `validate_email`, y envolver creación usuario+perfil en `transaction.atomic()`.

#### `AUD-ALT-11` — Cifrado de `CuentaBancaria` y fallback de `SUPRESIONES_CLAVE` acoplados a `SECRET_KEY` + bug en `cifrador()`
- **Ubicación:** `alumnos/models/retiros.py:50-62`, `alumnos/cifrado.py:10-18`, `supresiones/registro.py:33-34`, `lbwus/settings.py:46`
- **Evidencia:** `CuentaBancaria` deriva su clave únicamente de `SECRET_KEY` (sin variable dedicada ni `MultiFernet`): rotar `SECRET_KEY` rompe con `InvalidToken` HTTP 500 todo `dashboard_admin` y deja ilegibles las cuentas bancarias permanentes. `SUPRESIONES_CLAVE` cae silenciosamente en `SECRET_KEY` sin validación en `check --deploy`: rotar `SECRET_KEY` invalida todas las huellas HMAC y permite reponer cuentas eliminadas al restaurar un respaldo. Asimismo, `alumnos/cifrado.py:16` ignora el argumento `proposito` cuando se pasa una `clave` externa.
- **Remediación:** Definir claves dedicadas (`CUENTAS_BANCARIAS_CLAVE`, `SUPRESIONES_CLAVE`) obligatorias en producción con soporte `MultiFernet`/rotación, y derivar sub-claves por `proposito` mediante HKDF en `alumnos/cifrado.py`.

#### `AUD-ALT-12` — Endpoints de `allauth`/`django.contrib.auth` expuestos + flujo Google sobreescribe cuentas `is_staff`/`is_superuser` huérfanas
- **Ubicación:** `lbwus/urls.py:62-68`, `lbwus/settings.py:178-179`, `alumnos/google_views.py:63-65, 88-93`, `alumnos/google_forms.py:75-100`
- **Evidencia:** Montar completos `django.contrib.auth.urls` y `allauth.urls` deja abiertos `/accounts/3rdparty/`, `/accounts/social/connections/`, `/accounts/password/set/`, `/accounts/password/reset/` (en inglés, aceptando cuentas sin contraseña usable) y `/accounts/logout/` (redirige a `home_adm` para cualquier rol). Además, `_cuenta_a_completar()` trata cualquier usuario sin perfil (`resolver_rol(user) == (None, None)`) como huérfano: un superusuario creado por `createsuperuser` sin perfil `Tutor` que entre con Google es sobreescrito en `username`, `rut`, `rol` y pierde su contraseña (`set_unusable_password()`), conservando `is_staff=True` y `is_superuser=True`.
- **Remediación:** Montar únicamente las rutas OAuth necesarias de `allauth`, ajustar `LOGIN_REDIRECT_URL`/`LOGOUT_REDIRECT_URL`, y excluir cuentas `is_staff`/`is_superuser`/`not is_active` de `_cuenta_a_completar()` y `pre_social_login`.

#### `AUD-ALT-13` — Endpoint legado `/alumnos/inscribir_clase/` activo + flujo "Clase extra" a medio construir en producción
- **Ubicación:** `alumnos/urls.py:52, 55-56`, `alumnos/reservas.py:21-90`, `alumnos/services.py:164-214`, `alumnos/clase_extra.py:48-205`, `alumnos/management/commands/tareas_diarias.py:17-27`
- **Evidencia:**
  - `POST /alumnos/inscribir_clase/` sigue publicado y crea `Inscripcion(sesion=None)`, lo cual otorga acceso perpetuo a `sala_virtual`, permite cancelar con reembolso del crédito en cualquier momento y hace que **el profesor nunca cobre la clase** (`pagables()` exige `sesion__fecha_hora_fin__lte`).
  - Los alumnos ya pueden solicitar **clases extra** desde el modal de horarios enviando correos al docente, pero `clase_extra.aceptar()` y `rechazar()` carecen de vistas, rutas URL y UI; `vencer_las_vencidas()` nunca corre en `tareas_diarias.py`; y `solicitar()` no valida el rango `HORAS_DEL_DIA` (`08:00`–`21:00`), valida fuera de transacción ni limita pedidos pendientes.
- **Remediación:** Retirar o deshabilitar `/alumnos/inscribir_clase/` (`inscribir_alumno_en_clase`); completar vistas y UI docente de aceptar/rechazar clase extra (o deshabilitar la UI hasta completarlo), sumar `vencer_las_vencidas` a `tareas_diarias` y validar hora/límite dentro de transacción.

#### `AUD-ALT-14` — Errores visibles en plantillas productivas, correo de recuperación y condiciones comerciales
- **Ubicación:** `admin_portal/templates/admin_portal/includes/dashboard/usuarios.html:115-116, 162-167`, `admin_portal/templates/admin_portal/titulos_adm.html:28, 64, 109`, `templates/registration/correo_recuperacion_clave.html:153` (y `:84-328`), `alumnos/templates/alumnos/planes.html:126-127`, `alumnos/templates/alumnos/includes/panel/paquetes.html:8`
- **Evidencia:**
  1. Tres etiquetas `{{ ... }}` partidas en múltiples líneas en `usuarios.html` (`prof.user.first_name`, `admin_user.user.first_name`, `admin_user.user.direccion`) se renderizan como texto literal en el panel admin.
  2. `titulos_adm.html` lee `{{ p.rut }}` y `{{ e.profesor.rut }}`, dejando vacío el RUT en revisión de títulos y especializaciones (el atributo vive en `.user.rut`).
  3. `correo_recuperacion_clave.html:153` hardcodea `https://lbwus.xyz{{ reset_path }}` en vez de `{{ protocol }}://{{ domain }}`, rompiendo Staging/Railway/Local.
  4. `planes.html:126-127` y `paquetes.html:8` prometen vigencias de 60/90 días (reales en `paquetes.py`: 30/60) y devolución de clase cancelando antes del inicio (real en `services.py`: se pierde con menos de 4 horas).
- **Remediación:** Unificar las etiquetas en una sola línea en `usuarios.html`, corregir `.user.rut` en `titulos_adm.html`, usar `{{ protocol }}://{{ domain }}` en correos, y alinear los textos comerciales con `paquetes.py` y `Inscripcion.ANTICIPACION_SIN_COSTO`.

#### `AUD-ALT-15` — Crashes HTTP 500, errores en streaming MongoDB, bloqueo en `resenas`, `conftest.py` inconsistente y CVEs Altos
- **Ubicación:** `alumnos/views.py:440`, `alumnos/portales.py:18-29`, `alumnos/views_soporte_videos.py:49-155`, `user_profesor/titulo.py:102-106`, `comunidad/mongo.py:47-53`, `alumnos/videos_compartidos.py:74-168`, `resenas/models.py:89-95, 131`, `conftest.py:24-35`, `requirements.txt:3, 20`
- **Evidencia:**
  1. **Cache key >255 chars en login:** `username` de >230 chars excede `VARCHAR(255)` de `lbwus_cache_table` -> `DataError` 500.
  2. **Sesión obsoleta en `portales.py`:** Cuenta desactivada con `alumno_id` en sesión lanza `AttributeError` 500 en `es_menor(AnonymousUser)` al abrir páginas públicas como `/alumnos/planes`.
  3. **Soporte de videos con ticket cerrado:** `retirar_video` y `reintentar_reembolso` no capturan `ValidationError` de `agregar_mensaje()` -> HTTP 500 tras reembolsar dinero en Transbank; además `retirar_video` permite doble envío y contradice a `entregas.compartir` en paquetes vencidos.
  4. **Borrado físico prematuro antes de commit:** `pasar_titulos_a_base` (`titulo.py:102-106`), `user_profesor/views.py:315-318` (`foto.guardar`) y `supresiones/datos_propios.py:68-89` eliminan archivos antes de confirmar la transacción en PostgreSQL.
  5. **PyMongo sin `socketTimeoutMS` y streaming sin captura:** Conexiones colgadas bloquean hilos del worker hasta el timeout de 120s de Gunicorn; excepciones durante `StreamingHttpResponse` escapan del `try/except` y `NoFile` devuelve 503 en lugar de 404.
  6. **Reseñas (`resenas/models.py:89-95, 131`):** `UniqueConstraint(fields=['resena', 'remitente'])` sin `condition=Q(estado='pendiente')` bloquea permanentemente re-reportar reseñas editadas con abusos tras una moderación; y `puede_actualizarse()` permite sobrescribir reseñas ya ocultadas por moderación, destruyendo la evidencia.
  7. **`conftest.py` incompleto vs `RunnerLBWUS`:** Omite `VIDEOS_A_LA_VENTA=True`, `MEDIA_ROOT` temporal y `MD5PasswordHasher`, rompiendo pruebas en `pytest` y dejando archivos en `media/`.
  8. **CVEs Altos en `requirements.txt`:** `setuptools==68.0.0` (CVE-2024-6345, CVE-2025-47273) y `sqlparse==0.5.0` (CVE-2026-59893, CVE-2026-59894, CVE-2026-54284).
- **Remediación:** Hashear claves de caché; exigir `user.is_authenticated and user.is_active` en `portales.py`/`roles.py`; manejar `ValidationError` y lock en `views_soporte_videos.py`; mover borrados físicos a `on_commit`; fijar `socketTimeoutMS` y capturar `NoFile`/errores dentro del generador de streaming; acotar `UniqueConstraint` de `ReporteResena` a pendientes e impedir editar reseñas ocultas; alinear `conftest.py` con `RunnerLBWUS`; actualizar `setuptools` y `sqlparse`.

---

### 🟡 Severidad Media (`AUD-MED-01` – `AUD-MED-18`)

| ID | Hallazgo | Ubicación principal | Impacto / Acción |
|---|---|---|---|
| `AUD-MED-01` | Logout CSRF vía `GET` | `apoderados/views.py:527-529, 400`, `soporte/views.py:73-75` | Cierra sesión con una petición `GET` externa; agregar `@require_POST`, `@never_cache` y `<form method="post">`. |
| `AUD-MED-02` | Mutación de estado vía `GET` en notificaciones y confirmación de correo | `notificaciones/views.py:12-17`, `apoderados/views.py:119-128, 429-437` | `mis_notificaciones` marca como leídas *todas* las notificaciones (incluso >50 no vistas) en `GET`; confirmación de correo sensible a escáneres SafeLinks y carreras, con cooldown solo en sesión. |
| `AUD-MED-03` | Nombre de usuario siempre en blanco en el navbar global | `alumnos/templates/alumnos/includes/navbar.html:49, 57`, `alumnos/context_processors.py:54-60` | Lee `usuario_sesion.user.first_name`, pero el context processor expone `usuario_sesion.nombre`. |
| `AUD-MED-04` | Usuarios registrados con Google no pueden crear ni cambiar contraseña | `alumnos/google_forms.py:92`, `lbwus/urls.py:44-61`, `alumnos/context_processors.py:58` | `set_unusable_password()` impide usar `PasswordResetForm` y `PasswordChangeView` exige clave actual. |
| `AUD-MED-05` | `RutOrEmailBackend` con solo espacios (`"   "`) y triple hashing PBKDF2 | `alumnos/backends.py:87-102`, `lbwus/settings.py:340-344` | Chequea `if not username` antes de `.strip()` (prueba contraseña contra todos los menores sin correo); 3 backends multiplican x3 el costo PBKDF2 en fallos. |
| `AUD-MED-06` | `regis_tutor` suplanta la sesión del administrador creador | `user_profesor/views.py:488-510` | Hace `auth_login` como el nuevo administrador; debe conservar la sesión del creador. |
| `AUD-MED-07` | Desfases de zona horaria (UTC vs Chile) y gráfico anual mezclado | `alumnos/utils.py:26-28, 51`, `alumnos/models/clases.py:319`, `reportes.py:12`, `user_profesor/views.py:82, 134-156`, `videoteca.py:116` | `date.today()` / `auto_now_add` / `uploadDate` en UTC cambian mayoría de edad o fechas 3–4h antes; `_rendimiento_mensual` agrupa por mes sin año. |
| `AUD-MED-08` | Cuentas suprimidas visibles/editables en `admin_portal` y calificables en `resenas` | `admin_portal/views.py:38-164`, `admin_portal/titulos.py:54, 63`, `resenas/consultas.py:26` | Siguen contando como activas y pueden editarse/re-eliminarse o recibir reseñas (`"Cuenta eliminada"`). Filtrar `user__suprimida__isnull=True`. |
| `AUD-MED-09` | `ALLOWED_HOSTS` permisivo en producción | `lbwus/settings.py:54-59`, `alumnos/webpay.py:122, 171` | Permite cualquier `*.up.railway.app`, `localhost` y `127.0.0.1` con `DEBUG=False`, ampliando riesgo de *Host Header Poisoning* en `build_absolute_uri`. |
| `AUD-MED-10` | `on_delete=CASCADE` destructivo en modelos financieros y académicos | `alumnos/models/clases.py:48-324`, `pagos.py:62-108`, `videos.py:54-150`, `retiros.py:79` | Borrar un profesor, alumno, clase o asignatura en Django Admin destruye pagos, reembolsos y retiros conciliados. Cambiar a `PROTECT`. |
| `AUD-MED-11` | `Vinculo.revocar()` no borra `Documento` y apoderado no puede reprogramar con `0` disponibles | `apoderados/models.py:275-286`, `apoderados/views.py:294-304` | Quedan certificados retenidos y rompe re-solicitudes a los 30 días; además `<select>` de reprogramación queda vacío si no quedan clases libres y mezcla vigencias entre profesores. |
| `AUD-MED-12` | Fuga de solicitantes `por_rut`, `ZeroDivisionError` en PDFs y carreras en apoderados | `apoderados/views.py:449-457`, `apoderados/documentos.py:96-101`, `apoderados/models.py:53-62, 366-380` | `solicitud_adolescente` revela solicitantes `por_rut=True` no verificados; PDF con MediaBox `0` lanza 500; carreras en `Invitacion.aceptar` (enlace reutilizable), `_registrar_decision` y subida duplicada de documentos. |
| `AUD-MED-13` | Carreras, bloqueos y errores en `soporte` y `requerimientos` | `soporte/tickets.py:32-148`, `soporte/views.py:33-34`, `soporte/escalamientos.py:29-44`, `soporte/correo.py:69-125`, `requerimientos/gestion.py:59-62`, `avisos.py:27-35` | `abrir_ticket` y respuestas sin `select_for_update()`; líder no habilitado en una categoría queda bloqueado de reasignarse; `escalar.html` omite `'agente'`; correos a agentes inactivos; `requerimientos` permite `RECHAZADO` tras registrar `Entrega`. |
| `AUD-MED-14` | Casos borde en plazos/entregas de videos y validación MP4 superficial | `user_profesor/plazos_videos.py:24-50`, `user_profesor/entregas.py:28-64`, `user_profesor/videoteca.py:26-73` | Avisos de 3 días sin idempotencia; paquetes vencidos con extras sin entregar omitidos; `TypeError` si `fecha_pago=None`; `duracion_mp4()` acepta `duracion==0` y payloads arbitrarios de 500 MB con cabecera `ftyp`+`mvhd`, sin cuotas. |
| `AUD-MED-15` | Desfase de cuenta bancaria en `SolicitudRetiro`, carrera en `marcar_pagado` y posible deadlock | `alumnos/models/retiros.py:118-129`, `admin_portal/templates/admin_portal/includes/dashboard/finanzas.html:133-135`, `alumnos/services.py:69-291`, `agenda/cancelacion.py:39-41` | Si el profesor cambia de cuenta antes del pago, el registro queda con la cuenta antigua; `marcar_pagado` no bloquea `CuentaBancaria`; orden inverso de `select_for_update()` entre `InscripcionService` y `agenda.cancelacion`. |
| `AUD-MED-16` | API de sesiones, historial de pagos y tope horario del alumno | `alumnos/reservas.py:93-104`, `alumnos/views.py:312-318`, `alumnos/services.py:86-162`, `alumnos/models/clases.py:245-272, 386-392` | `listar_sesiones_disponibles` expone profesores sin título aprobado y da 500 con `clase_id=abc`; historial omite `CompraVideosExtra`; alumno puede reservar dos clases simultáneas; `esta_disponible`/`proximas()`/`puede_cancelar` inconsistentes. |
| `AUD-MED-17` | Bugs de estado, reloj local y manejo HTTP en JS y plantillas | `clase_extra.js:34-51, 168-189`, `horarios.js:42-108, 136-170`, `inscripcion.js:67`, `vistas.js:116`, `tira_horarios.js:14-17`, `perfil_profesor.html:86`, `videos_apoyo.html:68-69`, `comprar_videos_extra.html:23-35`, `regis_alum.html:58-97`, `contactos.html:166`, `sala_virtual.html:339-357` | `clase_extra.js` usa `new Date()` local en vez de Chile y bloquea el calendario; `JSON.parse(localStorage)` sin `try/catch` rompe toda la navegación del alumno; botones horarios repetidos sin materia; doble envío bloquea cuota de videos; CDN protocol-relative `//cdn.jsdelivr.net`; fetch sin validar `res.ok` ni deshabilitar submit. |
| `AUD-MED-18` | Errores en comandos de gestión y marca prematura de vencimientos | `alumnos/management/commands/revisar_pagos_pendientes.py:30-46`, `cargar_sesiones.py:45-94`, `crear_cuentas_demo.py:92-151`, `apoderados/correo.py:165-169` | `revisar_pagos_pendientes` silencia fallos, reintenta tokens viejos sin tope y retorna exit `0`; `cargar_sesiones` sin guardia `DEBUG` crea sesiones grupales con precios obsoletos; `crear_cuentas_demo` no usa `variaciones_rut`; `avisar_vencimientos()` marca `avisado=True` aunque falle SMTP. |

---

### 🟢 Severidad Baja (`AUD-BAJ-01` – `AUD-BAJ-08`)

| ID | Hallazgo | Ubicación principal | Detalle |
|---|---|---|---|
| `AUD-BAJ-01` | Maquetas, formularios falsos y datos obsoletos en UI pública/admin | `admin_portal/templates/.../perfil.html:9-45`, `saldo.html:155-226`, `base_admin.html:320`, `footer.html:24-29`, `home.html:51-120`, `recuperar_*.html` | `#formAjustes` simula guardar con SweetAlert sin backend; tabla vacía `desgloses_profesor` ("Regla S4-09"); `#reportes` roto; newsletter sin backend; dirección/teléfonos/planes viejos en `home.html` y `teachers@lbwus.cl` hardcodeado. |
| `AUD-BAJ-02` | Enlace roto en campana admin y uso de `CustomUser.rol` obsoleto | `admin_portal/avisos.py:54`, `admin_portal/ingresos.py:20-23`, `user_profesor/views.py:162` | Campana enlaza a `#section-finanzas` en vez de `#finanzas`; `ingresos.py` y `panel_profesor` leen `user.rol` en lugar de `resolver_rol()`. |
| `AUD-BAJ-03` | Deprecación Django 6.0 y restricciones débiles en modelos | `alumnos/models/clases.py:167-175`, `retiros.py:80`, `videos.py:55, 131`, `usuarios.py:26`, `alumnos/models/__init__.py:17-28`, `soporte/models.py:125-137` | 3 `CheckConstraint(check=...)` deprecados (fallarán en Django 6.0); `SolicitudRetiro.monto` y `CompraVideosExtra.cantidad` admiten `<= 0`; `CustomUser.rut` vacío guarda `""` en admin; faltan `DevolucionVideos`/`ReembolsoTransbank` en `__all__`. |
| `AUD-BAJ-04` | Enlaces `target="_blank"` sin `rel="noopener noreferrer"` y typos | `templates/registration/correo_recuperacion_clave.html:99-328` (7 casos), `user_profesor/templates/user_profesor/clases_en_vivo.html:21, 28`, `videos.html:7` | Falta `rel="noopener noreferrer"`; errata `"an"` por `"aún"` y copy obsoleto en `videos.html`. |
| `AUD-BAJ-05` | Desincronización menor de sesión, `ClaveDelApoderado` y códigos HTTP | `lbwus/urls.py:44-61`, `apoderados/models.py:416-425`, `alumnos/decorators.py:28, 49-50`, `alumnos/context_processors.py:74-78`, `alumnos/reservas.py:189-195` | Cambiar/recuperar clave en vistas Django no borra `ClaveDelApoderado`; `profesor_required_json`/`admin_required_json` retornan HTTP `200`; entrar por `/admin/login/` muestra enlace al portal en navbar pero redirige al login. |
| `AUD-BAJ-06` | Token reutilizable, fechas *naive* y vista de tickets cerrados en `supresiones` | `supresiones/identidad.py:20-37`, `supresiones/registro.py:59-81`, `supresiones/templatetags/supresiones_tags.py:10-16` | Token válido 24h reutilizable y no ligado al correo; importación acepta fechas *naive* duplicando registros; `evaluacion_pendiente()` muestra panel abierto en tickets de privacidad cerrados. |
| `AUD-BAJ-07` | Desajustes menores en `admin_portal`, `user_profesor`, `agenda` y `observaciones` | `admin_portal/titulos.py:31-36`, `admin_portal/metricas.py:54, 64`, `user_profesor/views.py:251, 310, 505`, `agenda/bloques.py:62-73`, `observaciones/models.py:14-19`, `observaciones/views.py:28` | `pedir_asignatura` no filtra `EN_REVISION`; `por_dictar` acumula residuos de división entera; `foto_profesor` omite `is_active`; asignación muerta `telefono_publico`; recrear franja reabre bloque cancelado; `30.4375 * meses` en observaciones y `errors['texto'][0]`. |
| `AUD-BAJ-08` | Validación, caché, PII en CLI y detalles de consistencia | `alumnos/paquetes.py:141-169`, `alumnos/webpay.py:145-185`, `notificaciones/models.py:30-32`, `requerimientos/forms.py:17-19`, `soporte/plazos.py:10-21`, `habilitar_soporte.py:46`, `auditar_cuentas_rut.py`, `comunidad/views.py:9-24` | Redondeo de `planes.html` difiere en \$1–\$7 respecto a `saldos.py`; videos extra no revalidan `aceptacion.VERSION`; `notificar()` no trunca ni valida `enlace`; fechas sin cota pueblan `@lru_cache(maxsize=None)`; `auditar_cuentas_rut` imprime PII a `stdout`; `salud` sin `@never_cache`. |

---

## PARTE II — CARENCIAS Y DEFICIENCIAS ESTRUCTURALES (`AUD-CAR-01` – `AUD-CAR-13`)

### Eje 1 — Observabilidad, `LOGGING` y Trazabilidad (Auditoría)
- **`AUD-CAR-01` [Alto] Sin configuración `LOGGING` ni reporte de fallos en producción:** `lbwus/settings.py` no define `LOGGING` ni `ADMINS`. En Django 5.2 con `DEBUG=False`, los tracebacks 500 (`django.request`) y eventos de seguridad (`django.security`) no se emiten a los logs de Railway. Solo 9 de ~250 archivos utilizan `logging`; `alumnos/webpay.py:121-252` silencia excepciones de Transbank y `lbwus/puerta.py:68` / `alumnos/codigo_google.py:70` silencian caídas SMTP sin registrar logs.
- **`AUD-CAR-02` [Alto] Ausencia de registro de auditoría (*audit trail*):** No existe trazabilidad persistente (quién, cuándo y qué cambió) para transacciones Webpay, operaciones CRUD sobre alumnos y asignaturas en `admin_portal`, creación de administradores (`regis_tutor`), ni aprobaciones/rechazos de títulos y especializaciones (`revisado_por`). Además, aprobar/rechazar/pagar retiros no notifica al profesor ni exige unicidad de `numero_operacion`.

### Eje 2 — Endurecimiento Web (CSP, SRI, Rate Limiting, Sesiones)
- **`AUD-CAR-03` [Alto] CSP inefectiva y cero Subresource Integrity (SRI):** `CSP_OBLIGATORIA` es `False` por defecto (`Report-Only`, donde `frame-ancestors` se ignora) y `lbwus/cabeceras.py:19-25` mantiene `'unsafe-inline'` (debido a 39 `<script>`, 56 `on*=`, 5 `<style>` y 503 `style=` inline) además del origen muerto `https://commondatastorage.googleapis.com`. Ninguno de los 22 recursos CDN externos incluye `integrity` ni `crossorigin`, y `sweetalert2@11` se carga con versión flotante en 6 plantillas.
- **`AUD-CAR-04` [Alto] Ausencia de Rate Limiting en superficies públicas y autenticadas de alto costo:** Carecen de límite de peticiones `/apoderados/registro/` (2 archivos de 5 MB + SMTP), `/apoderados/adolescente/`, `/apoderados/mi-cuenta/estudiantes/registrar/` (enumeración de RUT), `soporte/mis-tickets/nuevo/` (dispara correos a todos los líderes en `conducta`), `supresiones/eliminar-cuenta/` (bombardeo SMTP), `mensajes/` y `observaciones/`.
- **`AUD-CAR-05` [Medio] Sesiones extensas, cookies y enumeración en registro:** `SESSION_COOKIE_AGE` queda en 14 días sin expiración por inactividad incluso para `ADMIN`, `SOPORTE` y `APODERADO`; falta `CSRF_COOKIE_HTTPONLY = True`; `EMAIL_BACKEND` no es configurable por entorno; `DatabaseCache` con `MAX_ENTRIES=10000` y `CULL_FREQUENCY=3` puede sufrir evicción forzada por usuarios aleatorios; y `usuario_existe()` permite enumeración diferenciada de RUT/correos en los formularios públicos de registro.

### Eje 3 — Rendimiento, Consultas N+1, BLOBs y Paginación
- **`AUD-CAR-06` [Alto] Degradación severa por N+1, descarga de BLOBs y falta de paginación:**
  - **BLOBs de hasta 5 MB en listados:** `Profesor.titulo_contenido` se lee sin `.defer('titulo_contenido')` en `admin_portal/titulos.py:54`, hasta **4 veces** en `dashboard_admin` (`admin_portal/views.py`, `metricas.py`), en `panel_profesor` y en `admin_portal/avisos.py:58`.
  - **N+1 críticos:** `listar_sesiones_disponibles` (1 `COUNT(*)` por sesión ignorando la anotación), `perfil_profesor.html:78` (3 `COUNT(*)` por sesión), `clase_extra.horas_para_pedir` (hasta 42 queries por día consultado), `admin_portal/avisos.py:_de_agente` (1–4 queries por ticket en **cada** página de soporte), `apoderados/views.py:portal` y `clases_estudiante` (múltiples queries por vínculo/paquete), `soporte/views.py:_supervision` (12 queries de categorías por carga), `alumnos/views.py:alumno_pag1` (4 queries sobre `completadas()` y loops de `paquetes`), `videos_compartidos.py` consultando MongoDB con `0` videos compartidos, y `notificaciones/context_processors.py` ejecutando `SELECT COUNT(*)` en portales `ADMIN`/`SOPORTE` que no renderizan la campana.
  - **Sin paginación:** Falta paginación en `dashboard_admin`, `crud`, `titulos_adm`, `casos_escalados`, `panel_profesor`, `apoderados/revision`, `soporte`, `requerimientos`, `mensajes` y `resenas` (o se aplican cortes rígidos `[:50]`/`[:20]` en notificaciones/requerimientos/observaciones dejando inaccesible el historial).

### Eje 4 — Índices de Base de Datos (PostgreSQL y MongoDB)
- **`AUD-CAR-07` [Alto] Índices y restricciones de unicidad faltantes:**
  - **PostgreSQL:** `CustomUser.email` carece de índice y `UniqueConstraint(Lower('email'))`; `buy_order` en `PaqueteClases`/`Suscripcion`/`CompraVideosExtra` no tiene `unique=True`; faltan índices en `Profesor.titulo_estado`, `Inscripcion(alumno, estado)`/`(clase, estado)`/`(paquete, estado)`/`(sesion, estado)`, `PaqueteClases(estado, fecha_fin)`, `SolicitudRetiro.estado`, `SolicitudClaseExtra(estado, vence_el)`, `Especializacion.estado`, `Ticket(estado, asignado)`/`(estado, respondido, vence)`, `Notificacion(usuario, -creada)`, `Resena.estado`, `ReporteResena(remitente, creado)` y `Requerimiento(estado, vence)`.
  - **MongoDB:** `comunidad/esquemas.py:38-145` declara 5 colecciones muertas sin uso productivo, mientras el bucket real GridFS (`videos.files`) carece de índice compuesto en `('metadata.profesor_id', 1), ('uploadDate', -1)` (provoca `COLLSCAN` + sort en memoria) y `MongoClient` omite `maxPoolSize`/`maxIdleTimeMS`.

### Eje 5 — Infraestructura, Despliegue y Carencias Operativas
- **`AUD-CAR-08` [Medio] Arquitectura WSGI/SMTP, páginas de error y mantenimiento periódico:**
  - `Procfile:1` ejecuta `migrate` en `web:` (carreras al escalar) sobre **1 solo worker Gunicorn con 4 hilos**, donde envíos SMTP síncronos (`EMAIL_TIMEOUT=15`s) saturan el sitio completo; `DATABASES` no habilita `conn_health_checks=True`; `lbwus/settings.py` acopla `DEBUG`, protocolo OAuth y `X-Forwarded-For` a `RAILWAY_ENVIRONMENT`.
  - `alumnos/management/commands/tareas_diarias.py` omite `clearsessions` (crecimiento indefinido de `django_session`).
  - Faltan plantillas `templates/400.html` y `templates/403.html`; `templates/500.html:1` usa `{% static %}` con `CompressedManifestStaticFilesStorage` (riesgo de 500 en cascada si falla el manifiesto).
- **`AUD-CAR-09` [Medio] Brechas operativas en protección infantil, requerimientos y supresiones:**
  - En `observaciones` (canal directo profesor → menor), no se valida `profesor.puede_hacer_clases`, no hay aviso al apoderado al crear/editar, no hay historial de cambios ni botón de reporte/retiro.
  - En `requerimientos`, no existen alertas internas en la campana del líder para plazos próximos a vencer.
  - En `supresiones`, falta procedimiento/checklist para terceros externos (Transbank, Google, Railway), programación de `exportar_supresiones`, y se exhibe a usuarios el placeholder `SIN_PLAZO` (*«está por definir con el contador»*).
  - La compra de videos extra omite verificar `aceptacion.confirmar(request)` si cambió `aceptacion.VERSION`.

### Eje 6 — Pipeline CI/CD, Cobertura QA y Gestión de Claves
- **`AUD-CAR-10` [Alto] Pipeline CI incompleto y desfase de versión de Python:** `.github/workflows/tests.yml:38-50` instala `ruff`, `bandit`, `pip-audit` y `pytest`, pero no ejecuta ninguno en CI, ni corre `makemigrations --check --dry-run` ni `check --deploy --fail-level ERROR` con `DEBUG=False` (`DOCUMENTOS_CLAVE`). Además prueba en Python `3.13` mientras `.python-version` despliega en `3.14.0`.
- **`AUD-CAR-11` [Medio] Puntos ciegos en `test_qa_acceso.py` y validación de configuración:**
  - `tests/test_qa_acceso.py:105-184` solo instancia soporte líder (`lider=True`), sin probar agentes regulares, menores, profesores sin título ni apoderados sin verificar; sus endpoints `@require_GET` JSON sin MongoDB pasan aunque pierdan autenticación; `rutas_qa.py` ignora `re_path` (`allauth`); y `test_cabeceras.py:91` omite URLs protocol-relative (`//`).
  - `check --deploy` no valida `SUPRESIONES_CLAVE`, credenciales SMTP vacías ni datos legales de ejemplo (`settings.LEGAL` con RUT `76.000.000-0`); `DOCUMENTOS_CLAVE` no aplica `.strip()` ni permite rotación multi-clave.

### Eje 7 — Documentación Obsoleta, Datos de Prueba en Git, Código Muerto y Administración
- **`AUD-CAR-12` [Medio] Documentación desactualizada, credenciales en Git y código muerto:** `Usuarios_test.txt` rastreado en Git contiene contraseñas de prueba en texto plano; `contexto.txt`, `docs/CONFIGURACION_PRODUCCION.md:38-39` y `README.md:29` describen arquitectura/versiones obsoletas (*passwordless*, títulos en disco, fotos sin servir, Python 3.13 / Django 5.0.6). Persiste código muerto sin uso productivo (`Suscripcion`, `PlanError`, `PlanSinSaldoError`, `validar_imagen_perfil`, `tutors = []` / `renderMyClasses` / `renderMyReports`, `comunidad/esquemas.py`).
- **`AUD-CAR-13` [Bajo] Mejoras menores de administración y mantenimiento de repositorio:** Seis apps (`soporte`, `supresiones`, `requerimientos`, `resenas`, `notificaciones`, `comunidad`) carecen de registro en `admin.py`; `.github/dependabot.yml` solo vigila `pip` (sin `github-actions`); `.github/workflows/tests.yml` omite `permissions` mínimos y `concurrency`.

---

## PARTE III — PLAN DE REMEDIACIÓN PRIORIZADO

### Ola 1 — Bloqueadores Pre-Producción (Seguridad, Menores, Estabilidad y Pagos)
1. **Autenticación y XSS:** Cerrar auto-vinculación OAuth sobre emails no verificados y proteger cuentas `is_staff`/`is_superuser`/roles privilegiados (`AUD-CRIT-01`, `AUD-ALT-12`); corregir Stored XSS en `admin_portal` (`AUD-CRIT-02`) y restaurar `window.escaparHtml` en `base_alumno.html`/`datos.js` (`AUD-CRIT-03`).
2. **Estabilidad Worker y Menores:** Agregar `threading.Lock()` en `pypdfium2` + validación previa de dimensiones Pillow + rate limit en `/apoderados/registro/` (`AUD-CRIT-05`); añadir `.defer('contenido')` y paginación en `/apoderados/revision/` (`AUD-CRIT-06`); aislar salas Jitsi por `SesionClase` con ventana horaria y apagar `en_vivo` (`AUD-CRIT-04`); corregir invitación adolescente huérfana (`AUD-CRIT-09`).
3. **Pagos y Reembolsos:** No borrar `ReembolsoTransbank` en timeouts y bloquear filas con `select_for_update` (`AUD-CRIT-07`); hacer idempotente `webpay.confirmacion` con PRG, rechazar anulaciones/timeouts sin bloquear cuotas y resolver pérdida de sesión `SameSite` (`AUD-CRIT-08`); volver atómicos `registrar_respuesta` y `PaqueteClases.confirmar_pago` (`AUD-ALT-07`).
4. **Exposición de secretos y fuerza bruta:** Ocultar `DATABASE_URL` en `FiltroReporteErrores` (`AUD-ALT-01`); no borrar el límite de IP al hacer login y hacerlo atómico (`AUD-ALT-02`); validar vigencia real del perfil en `_rol_requerido` y `is_active`/`debe_renovar_clave` (`AUD-ALT-03`).

### Ola 2 — Integridad Funcional, Legal y de Datos
1. **Agenda, Concurrencia y Clases:** Corregir el fallo DST `America/Santiago` en `agenda/bloques.py` (`AUD-ALT-05`), añadir `select_for_update()`/`UniqueConstraint` en `agenda`, `videoteca`/`entregas`, `titulo.resolver`, `mensajes` y `supresiones` (`AUD-ALT-06`), habilitar `.btn-mover-sesion` (`AUD-ALT-04`), retirar `/alumnos/inscribir_clase/` y completar o deshabilitar flujo "Clase extra" (`AUD-ALT-13`).
2. **Privacidad, Menores y Supresiones:** Completar limpieza multi-rol + GridFS + reseñas en `supresiones` (`AUD-CRIT-10`); cerrar oráculo de RUT en `VincularEstudianteForm`, separar nombre de pila, proteger mayoría de 18 años en revocaciones/reportes, bloquear observaciones sobre eliminados y reforzar `mensajes/filtro.py` y `ids_profesores_con_relacion` (`AUD-ALT-09`).
3. **Finanzas, Cuentas y Plantillas:** Corregir cálculo unitario de videos y retiros (`AUD-ALT-07`), endurecer cambio de email/cuenta bancaria y añadir `method="post"` + `csrf_token` (`AUD-ALT-08`), normalizar RUT en formularios y login (`AUD-ALT-10`), desacoplar `CuentaBancaria` y `SUPRESIONES_CLAVE` de `SECRET_KEY` (`AUD-ALT-11`), reparar plantillas rotas (`usuarios.html`, `titulos_adm.html`, `correo_recuperacion_clave.html`, `planes.html`, `navbar.html`) y actualizar dependencias con CVE (`AUD-ALT-14`, `AUD-ALT-15`).

### Ola 3 — Rendimiento, Observabilidad, CI/CD y Deuda Técnica
1. **Observabilidad y Rendimiento:** Configurar `LOGGING` en `settings.py` y audit trail (`AUD-CAR-01`, `AUD-CAR-02`); agregar `.defer('titulo_contenido')`, eliminar N+1, paginar listados y crear índices en PostgreSQL y MongoDB `videos.files` (`AUD-CAR-06`, `AUD-CAR-07`).
2. **Endurecimiento y Despliegue:** Migrar scripts/estilos inline para quitar `'unsafe-inline'`, añadir SRI a CDNs y activar `CSP_OBLIGATORIA=1` (`AUD-CAR-03`); añadir rate limiting transversal (`AUD-CAR-04`); ajustar `Procfile`, `conn_health_checks`, SMTP asíncrono/desacoplado, `clearsessions` y páginas `400`/`403`/`500` (`AUD-CAR-05`, `AUD-CAR-08`).
3. **CI/CD, QA y Limpieza:** Activar `ruff`, `bandit`, `pip-audit`, `makemigrations --check`, `check --deploy` y Python `3.14` en `.github/workflows/tests.yml` (`AUD-CAR-10`); alinear `conftest.py` y ampliar `test_qa_acceso.py` (`AUD-ALT-15`, `AUD-CAR-11`); retirar código muerto y actualizar/limpiar documentación y `Usuarios_test.txt` (`AUD-CAR-12`).
