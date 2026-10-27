# Matriz de pruebas de identidad y permisos (S4-11)

Inicio de sesión, usuarios desactivados, errores de autenticación y permisos por rol para **alumnos, profesores y administradores**. Registra los resultados y la evidencia de los hallazgos **S-03, S-05, S-06 y S-07** del informe `INFORME_SEGURIDAD_LBWUS.html`.

> **Alcance:** esta tarea valida y registra. **No corrige** los hallazgos. Cada corrección es una tarea aparte; el informe ya propone las ramas `fran-login-fuerza-bruta` (S-05) y `fran-cerrar-registro-allauth` (S-06 y S-07). S-03 no tiene rama propuesta.

## Cómo se lee y cómo se ejecuta

- **OK:** el sistema se comporta como se espera.
- **ABIERTO:** el hallazgo sigue presente. La prueba describe el comportamiento **seguro**, falla hoy y está marcada con `expectedFailure`, así la suite queda en verde y el hallazgo sigue visible. Cuando se corrija, unittest avisa "unexpected success" y se quita la marca.
- **CERRADO (S4-02):** lo corrigió la rama de seguridad S4-02; la prueba ya pasa sin marca.
- Las filas **nuevas** están en `tests/test_matriz_identidad.py`. Las **existentes** se referencian, no se repiten.

```
python manage.py test tests.test_matriz_identidad                     # suite normal
VER_HALLAZGOS=1 python manage.py test tests.test_matriz_identidad -v 2 # muestra el fallo real de cada hallazgo
```

## Matriz

### Inicio de sesión y errores de autenticación

| ID | Rol | Escenario | Esperado | Observado | Resultado | Hallazgo | Evidencia |
|---|---|---|---|---|---|---|---|
| ID-01 | Alumno | Entra con RUT, RUT con puntos o correo | Entra a su portal | Entra con los tres | OK | — | `LoginTests.test_entra_con_rut_rut_con_puntos_o_correo` |
| ID-02 | Los tres | Cada rol inicia sesión | Llega a su propio portal | Llega a su portal | OK | — | `test_portales_por_rol.test_login_lleva_a_cada_rol_a_su_portal` |
| ID-03 | Alumno | 5 claves incorrectas con el mismo RUT | Bloqueo de 5 min, incluso con la clave correcta | Bloquea | OK | — | `test_seguridad_blindaje.test_01_rate_limiting_login_bloquea_tras_5_intentos_fallidos` |
| ID-04 | Anónimo | 15 fallos desde la misma IP | Bloqueo por IP | Bloquea | OK | — | `S05LimiteDeIntentosTests.test_el_contador_por_ip_bloquea_tras_15_fallos` |
| ID-05 | Alumno | 5 fallos con `12.345.678-5` y luego entra con `12345678-5` | Sigue bloqueado: es el mismo RUT | Sigue bloqueado | **CERRADO (S4-02)** | S-05 | `S05LimiteDeIntentosTests.test_escribir_el_rut_de_otra_forma_no_reinicia_el_contador` |
| ID-06 | Anónimo | 15 fallos y luego cambia `X-Forwarded-For` | Sigue bloqueado | Sigue bloqueado | **CERRADO (S4-02)** | S-05 | `S05LimiteDeIntentosTests.test_cambiar_x_forwarded_for_no_reinicia_el_contador_por_ip` |
| ID-06b | Anónimo | Detrás del proxy (Railway): 15 fallos y luego cambia el inicio de `X-Forwarded-For` | Sigue bloqueado: cuenta solo la IP que agrega el proxy | Sigue bloqueado | OK | S-05 | `S05LimiteDeIntentosTests.test_detras_del_proxy_solo_cuenta_la_ip_que_agrega_el_proxy` |
| ID-07 | Alumno | Alumno creado por el admin entra usando su RUT como clave | No entra | **Entra** | **ABIERTO** | S-03 | `S03ClaveInicialTests.test_alumno_creado_por_admin_no_entra_con_su_rut` |

### Usuarios desactivados

| ID | Rol | Escenario | Esperado | Observado | Resultado | Hallazgo | Evidencia |
|---|---|---|---|---|---|---|---|
| ID-08 | Alumno | Usuario desactivado intenta entrar con su clave | Rechazado, sin sesión | Rechazado | OK | — | `LoginTests.test_usuario_desactivado_no_inicia_sesion` |
| ID-09 | Cualquiera | Usuario desactivado con sesión abierta, en una vista con decorador de rol | Expulsado | Expulsado | OK | — | `test_seguridad_blindaje.test_08_usuario_con_is_active_false_es_expulsado_por_decorador` |
| ID-10 | Admin | Admin desactivado con sesión abierta abre "crear administrador" (`/profesor/registro_tutor`) | Redirige al login | **Responde 200: entra** | **ABIERTO** | S-07 | `S07CuentasDesactivadasTests.test_admin_desactivado_con_sesion_no_entra_a_crear_administradores` |
| ID-11 | Alumno | Cuenta desactivada entra con Google | Rechazada | Rechazada | **CERRADO (S4-02)** | S-07 | `S07GoogleTests.test_cuenta_desactivada_no_entra_con_google` |

### Registro y cuentas

| ID | Rol | Escenario | Esperado | Observado | Resultado | Hallazgo | Evidencia |
|---|---|---|---|---|---|---|---|
| ID-12 | Anónimo | Registro propio de allauth (`/accounts/signup/`) | Cerrado | Cerrado | **CERRADO (S4-02)** | S-06 | `S06RegistroAbiertoTests.test_el_registro_propio_de_allauth_esta_cerrado` |
| ID-13 | Anónimo | Cuenta sin perfil creada con el correo de otra persona, que luego la completa con Google | La clave previa deja de servir | **La clave previa sigue sirviendo** | **ABIERTO** | S-06 | `S06CuentaHuerfanaTests.test_completar_con_google_anula_la_clave_previa` |
| ID-14 | Anónimo | Google entrega un correo no verificado | Rechazado | Rechazado | OK | — | `test_google_y_titulo.test_correo_no_verificado_por_google_se_rechaza` |

### Permisos y accesos por rol

| ID | Rol | Escenario | Esperado | Observado | Resultado | Hallazgo | Evidencia |
|---|---|---|---|---|---|---|---|
| ID-15 | Los tres | Abrir el portal de otro rol | Vuelve a su propio portal | Vuelve | OK | — | `test_portales_por_rol.test_ningun_rol_entra_a_un_portal_ajeno` |
| ID-16 | Otros roles | Ejecutar acciones de administrador | Rechazado | Rechazado | OK | — | `test_portales_por_rol.test_acciones_de_admin_no_corren_con_otro_rol` |
| ID-17 | Otros roles | Llamar endpoints del profesor | Rechazado | Rechazado | OK | — | `test_portales_por_rol.test_endpoints_del_profesor_rechazan_a_otros_roles_en_json` |
| ID-18 | Anónimo | Abrir vistas internas del portal admin | Rechazado | Rechazado | OK | — | `test_control_acceso.test_anonimo_no_entra_a_ninguna_vista_interna` |
| ID-19 | Superusuario sin perfil | Iniciar sesión | No cae en el portal de alumno | No cae | OK | — | `test_portales_por_rol.test_superusuario_sin_perfil_no_cae_en_portal_de_alumno` |
| ID-20 | Alumno | Entrar a la sala virtual de una clase sin estar inscrito | Rechazado | Rechazado | OK | — | `test_sala_virtual_acceso.test_sin_inscripcion_no_entra` |
| ID-21 | No admin | Ver el archivo del título de un profesor | Solo admins | Solo admins | OK | — | `test_google_y_titulo.test_archivo_del_titulo_solo_lo_ven_admins` |

## Estado de los hallazgos

| Hallazgo | Gravedad (informe) | Estado | Filas | Dónde está hoy |
|---|---|---|---|---|
| **S-03** Alumnos creados por el admin entran con su RUT como clave | Crítica | **Abierto, confirmado por prueba** | ID-07 | `admin_portal/forms.py:82` (`password=rut`) |
| **S-05** El límite de intentos se puede saltar | Alta | **Cerrado (S4-02)**: contador por RUT normalizado, IP confiable y caché compartida en base de datos | ID-05, ID-06, ID-06b | `alumnos/backends.py` (`obtener_identificador_rate_limit`), `alumnos/views.py` (`_obtener_ip`), `CACHES` en `lbwus/settings.py` |
| **S-06** Registro de allauth abierto y reutilización de cuentas huérfanas | Alta | **Parcial**: el registro de allauth está cerrado (S4-02); la cuenta huérfana sigue abierta | ID-12, ID-13 | `alumnos/google_views.py:56` (reutiliza la cuenta); `alumnos/google_forms.py:89-90` (solo anula la clave en cuentas nuevas) |
| **S-07** Cuentas desactivadas siguen operando por la sesión o por Google | Alta | **Parcial**: Google ya las rechaza (S4-02); el admin con sesión sigue abierto | ID-10, ID-11 | `user_profesor/views.py:421-428` (`_es_admin` solo mira la sesión) |

**S-07, vistas sin decorador de rol (solo revisión de código, sin prueba propia).** Estas vistas de `alumnos/views.py` usan la sesión sin `@alumno_required`, y por lo tanto no revisan `is_active`: `enviar_reporte` (504), `inscribir_clase` (594), `listar_sesiones_disponibles` (677), `reservar_sesion` (725), `sala_virtual` (953) e `iniciar_directo` (996). Son las mismas que cita el informe, con números de línea actualizados.

## Evidencia

Ejecutado el 26-oct-2026 en SQLite, rama `fran-matriz-identidad`.

**Con `VER_HALLAZGOS=1`** (10 pruebas: 3 OK y 7 fallos, cada uno por su hallazgo):

```
S-03: el alumno creado por el admin entra con su RUT como contraseña
S-05: tras 5 fallos con 12.345.678-5, entra escribiendo 12345678-5
S-05: cambiando X-Forwarded-For el cliente evita el bloqueo por IP
S-06: /accounts/signup/ acepta registros (no hay ACCOUNT_ADAPTER que lo cierre)
S-06: la clave previa de la cuenta huérfana sigue sirviendo tras completarla con Google
S-07: un admin desactivado con sesión abierta entra a crear administradores (200 != 302)
S-07: una cuenta desactivada entra a su portal con Google
```

Ningún fallo se debe a un error de preparación: los siete son `AssertionError` con el mensaje de su hallazgo.

**Suite completa en modo normal:** `Ran 349 tests — OK (skipped=6, expected failures=7)`. Las 6 omitidas requieren MongoDB Atlas; las 7 esperadas son los hallazgos abiertos.

## Lo que esta matriz no cubre

- **S-05, `X-Forwarded-For` en Railway:** la app confía solo en la última IP de la cabecera, la que agrega el proxy (ID-06b). Falta confirmar en un deploy real que Railway la agrega así; si usara varios saltos internos, habría que ajustar cuántos se descartan.
- **Pruebas contra producción:** no se hicieron. Todo corre en el entorno de pruebas de Django.
