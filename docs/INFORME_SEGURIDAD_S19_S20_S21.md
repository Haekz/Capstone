# Informe Técnico de Seguridad: Eliminación de Rutas y Métodos de Autenticación Inseguros (S-19, S-20, S-21)

**Proyecto:** LBWUS (Learn Better With Us)  
**Fecha:** 30 de Octubre de 2026  
**Referencia:** Informe de seguridad y estado técnico LBWUS (25/10/2026) — S-19, S-20 y S-21  
**Estándares aplicados:** OWASP Top 10 (A01: Broken Access Control, A07: Identification and Authentication Failures), RFC 7231 / RFC 9110, Django 5.2 Security Guidelines, django-allauth Security Best Practices  
**Estado:** ✅ Implementado y Verificado (100% Pruebas Pasadas)

---

## 1. Resumen Ejecutivo

En cumplimiento con las recomendaciones del informe de seguridad de LBWUS, se procedió a la subsanación integral de tres vectores de vulnerabilidad identificados en el control de acceso y flujos de autenticación:

1. **S-19:** Se neutralizó la vulnerabilidad de cierre de sesión mediante peticiones `GET` (Logout CSRF / DoS), forzando estrictamente el método `POST` con validación de token CSRF en todas las vistas y componentes de interfaz (Alumno, Profesor, Administrador y Barra de Navegación Global).
2. **S-20:** Se desactivó el inicio de sesión OAuth2 de Google mediante peticiones `GET` (`SOCIALACCOUNT_LOGIN_ON_GET = False`), mitigando ataques de *Login CSRF*, transformando el enlace en un formulario `POST` con token CSRF válido.
3. **S-21:** Se blindó el enrutamiento de producción aislando las rutas de prueba de plantillas de error (`test404/` y `test500/`) bajo la guarda condicional `if settings.DEBUG:`, impidiendo su exposición en entornos de despliegue.

---

## 2. Detalle de Vulnerabilidades y Soluciones Implementadas

### 2.1. Requerimiento S-19: Cierre de Sesión Seguro (POST + CSRF)

#### A. Diagnóstico de Seguridad
* **Riesgo:** El uso del método `GET` para cerrar sesiones (`logout`) viola la semántica de HTTP (RFC 7231 / 9110), donde las peticiones `GET` deben ser seguras e idempotentes (sin efectos colaterales de mutación de estado). Permitir el cierre de sesión por `GET` facilita ataques de tipo **Logout DoS** o CSRF donde una etiqueta `<img src="/alumnos/logout_alumno/">` incrustada en un foro, mensaje o sitio malicioso fuerza el cierre de sesión de la víctima sin su consentimiento.
* **Estándar Django 5.x:** A partir de Django 5.0, `django.contrib.auth.views.LogoutView` rechaza peticiones `GET` y exige exclusivamente `POST`.

#### B. Cambios Aplicados en Controladores (Backend)
Se decoraron todas las vistas de logout del sistema con `@require_POST` y `@never_cache`:
* `alumnos/views.py` -> `logout_alumno`:
  ```python
  @never_cache
  @require_POST
  def logout_alumno(request):
      auth_logout(request)
      request.session.flush()
      return redirect('home')
  ```
* `admin_portal/views.py` -> `logout_admin`:
  ```python
  @never_cache
  @require_POST
  def logout_admin(request):
      from django.contrib.auth import logout as auth_logout
      auth_logout(request)
      request.session.flush()
      return redirect('home')
  ```
* `user_profesor/views.py` -> `logout_prof`:
  ```python
  @never_cache
  @require_POST
  def logout_prof(request):
      auth_logout(request)
      request.session.flush()
      return redirect('home')
  ```
* **Comportamiento ante solicitudes GET no autorizadas:** El framework responde automáticamente con código de estado HTTP `405 Method Not Allowed`.

#### C. Modificaciones en Interfaz de Usuario (Frontend)
Se sustituyeron los enlaces HTML `<a>` por formularios semánticos con protección CSRF:
1. **`alumnos/templates/alumnos/includes/navbar.html`**:
   * *Menú móvil:* `<form method="post" action="{{ usuario_sesion.url_logout }}" class="form-logout-mobile">{% csrf_token %}<button type="submit" class="btn-logout-mobile">Cerrar sesión</button></form>`
   * *Menú desplegable de escritorio (Avatar):* `<form method="post" action="{{ usuario_sesion.url_logout }}" class="form-logout-desktop">{% csrf_token %}<button type="submit" class="cuenta-item cuenta-item--salir btn-logout-cuenta"><i class="bi bi-box-arrow-right"></i> Cerrar sesión</button></form>`
2. **`alumnos/templates/alumnos/Alumno_pag1.html`** (Sidebar Alumno):
   * Formulario `form-sb-logout` con botón `.sb-logout.btn-sb-logout`.
3. **`admin_portal/templates/admin_portal/base_admin.html`** (Sidebar Admin):
   * Formulario `form-sidebar-logout` con botón `.sidebar-logout.btn-sidebar-logout`.
4. **`user_profesor/templates/user_profesor/panel_profesor.html`** (Sidebar Profesor):
   * Formulario `form-prof-logout` con botón `.prof-logout-btn.btn-prof-logout`.
5. **Estilos y Accesibilidad:** Se agregaron reglas en `styles.css`, `alumn_1.css`, `admin_panel.css` y `panel.css` asegurando que la apariencia visual, efectos hover y compatibilidad con modo oscuro se mantengan idénticos.

---

### 2.2. Requerimiento S-20: Desactivación de Inicio de Sesión OAuth Google por GET

#### A. Diagnóstico de Seguridad
* **Riesgo:** Iniciar un flujo OAuth2 mediante peticiones `GET` permite ataques de **Login CSRF** (OWASP). Un atacante puede engañar al navegador de un usuario para autenticarse automáticamente en una cuenta controlada por el atacante o forzar redirecciones OAuth imprevistas mediante precarga (*prefetching*) de enlaces.
* **Estándar django-allauth:** El proyecto `django-allauth` exige que las solicitudes a `{% provider_login_url 'google' %}` se realicen vía `POST` acompañadas del token CSRF.

#### B. Cambios en Configuración (`lbwus/settings.py`)
Se cambió explícitamente la bandera de allauth:
```python
# S-20 (OWASP Login CSRF): La autenticación OAuth con proveedores sociales
# NUNCA debe iniciarse por peticiones GET, pues permite ataques de inicio de
# sesión involuntario / CSRF. Se exige solicitud POST con token CSRF válido.
SOCIALACCOUNT_LOGIN_ON_GET = False
```

#### C. Modificaciones en Interfaz de Usuario (`templates/registration/login.html`)
Se transformó el botón de acceso de Google de hipervínculo `<a>` a un formulario `POST`:
```html
{% if socialaccount_providers %}
<form method="post" action="{% provider_login_url 'google' %}" class="form-google">
    {% csrf_token %}
    <button type="submit" class="btn-google">
        <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
            <!-- Iconografía oficial de Google -->
        </svg>
        <span>Continuar con Google</span>
    </button>
</form>
{% endif %}
```
Se ajustó `lbwus/static/login.css` y `recuperar.css` agregando `.form-google` (`width: 100%`) y `cursor: pointer;`.

---

### 2.3. Requerimiento S-21: Restricción de Rutas de Prueba a DEBUG

#### A. Diagnóstico de Seguridad
* **Riesgo:** Rutas como `/test404/` y `/test500/` exponen las pantallas de error de forma arbitraria en producción (`DEBUG=False`), retornando código HTTP 200 para páginas que simulan errores, afectando el SEO, el escaneo de seguridad y potencialmente divulgando detalles de la arquitectura de plantillas.

#### B. Modificaciones en Rutas (`lbwus/urls.py`)
Se removieron las rutas `test404/` y `test500/` de la lista general estática de `urlpatterns` y se ubicaron al final del módulo bajo verificación estricta de entorno:
```python
# S-21: Rutas de prueba de errores restringidas estrictamente a DEBUG.
# En producción (DEBUG=False) jamás deben exponerse en la tabla de rutas.
if settings.DEBUG:
    urlpatterns += [
        path('test404/', TemplateView.as_view(template_name='404.html'), name='test404'),
        path('test500/', TemplateView.as_view(template_name='500.html'), name='test500'),
    ]
```

---

## 3. Matriz de Pruebas Automatizadas y Evidencia

Para certificar la integridad de las soluciones y la ausencia de regresiones, se diseñó e integró la suite de pruebas `tests/test_seguridad_s19_s20_s21.py`:

| Identificador | Caso de Prueba | Método / Entorno | Resultado |
|---|---|---|:---:|
| **S-19.1** | `test_logout_alumno_rechaza_get` | `GET /alumnos/logout_alumno/` responde 405 | **OK** |
| **S-19.2** | `test_logout_admin_rechaza_get` | `GET /admin_portal/logout_admin/` responde 405 | **OK** |
| **S-19.3** | `test_logout_prof_rechaza_get` | `GET /profesor/logout` responde 405 | **OK** |
| **S-19.4** | `test_logout_alumno_via_post_cierra_sesion_exitosamente` | `POST` invalida sesión, purga `alumno_id` y redirige a `home` | **OK** |
| **S-19.5** | `test_logout_admin_via_post_cierra_sesion_exitosamente` | `POST` invalida sesión, purga `admin_id` y redirige a `home` | **OK** |
| **S-19.6** | `test_logout_prof_via_post_cierra_sesion_exitosamente` | `POST` invalida sesión, purga `profesor_id` y redirige a `home` | **OK** |
| **S-19.7** | `test_plantillas_contienen_formulario_post_y_csrf_para_logout` | Verificación de renderizado de `<form method="post">` y `csrfmiddlewaretoken` en todos los portales | **OK** |
| **S-20.1** | `test_socialaccount_login_on_get_desactivado` | `settings.SOCIALACCOUNT_LOGIN_ON_GET is False` | **OK** |
| **S-20.2** | `test_google_login_via_get_no_inicia_oauth_directo` | `GET /accounts/google/login/` no emite 302 hacia Google | **OK** |
| **S-20.3** | `test_formulario_login_contiene_post_csrf_para_google` | Login template incluye formulario POST y CSRF token | **OK** |
| **S-21.1** | `test_rutas_test_estan_definidas_condicionalmente_segun_debug` | `DEBUG=False` omite rutas; `DEBUG=True` registra rutas | **OK** |

### Pruebas de Regresión Adicionales
* `tests.test_control_acceso`: 100% OK
* `tests.test_google_y_titulo`: 100% OK
* `tests.test_portales_por_rol`: 100% OK
* `tests.test_puerta`: 100% OK
* `alumnos.tests_front`: 100% OK

**Total pruebas ejecutadas vinculadas:** 59 pruebas automáticas ejecutadas sin ningún fallo.

---

## 4. Archivos Modificados

* `lbwus/settings.py`
* `lbwus/urls.py`
* `lbwus/static/login.css`
* `lbwus/static/recuperar.css`
* `alumnos/views.py`
* `alumnos/static/alumnos/css/styles.css`
* `alumnos/static/alumnos/css/alumn_1.css`
* `alumnos/templates/alumnos/includes/navbar.html`
* `alumnos/templates/alumnos/Alumno_pag1.html`
* `admin_portal/views.py`
* `admin_portal/static/admin_portal/css/admin_panel.css`
* `admin_portal/templates/admin_portal/base_admin.html`
* `user_profesor/views.py`
* `user_profesor/static/panel.css`
* `user_profesor/templates/user_profesor/panel_profesor.html`
* `templates/registration/login.html`
* `tests/test_puerta.py`
* `tests/test_seguridad_s19_s20_s21.py` (Nuevo)
* `docs/INFORME_SEGURIDAD_S19_S20_S21.md` (Nuevo)
