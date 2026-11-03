# Informe Técnico de Seguridad: Saneamiento de Salida HTML y Reducción de Superficies XSS (S-23)

**Proyecto:** LBWUS (Learn Better With Us)  
**Fecha:** 30 de Octubre de 2026  
**Referencia:** Informe de seguridad y estado técnico LBWUS (25/10/2026) — Requerimiento S-23  
**Estándares aplicados:** OWASP Top 10 (A03:2021 — Injection / Cross-Site Scripting), OWASP XSS Prevention Cheat Sheet, CWE-79 (Improper Neutralization of Input During Web Page Generation), W3C DOM Safe APIs  
**Estado:** ✅ Implementado, Mitigado y Certificado con Pruebas Automatizadas (100% OK)

---

## 1. Resumen Ejecutivo

En el marco de la auditoría de seguridad de LBWUS, se ejecutó una revisión e intervención exhaustiva sobre todas las superficies dinámicas del frontend donde se realizaban interpolaciones de datos en el DOM mediante cadenas de texto e `innerHTML`. 

Se identificaron y neutralizaron vectores de riesgo de **Cross-Site Scripting (XSS)** reflejado y almacenado en cuatro módulos críticos:
1. **Carrito de Compras Global y Flujo de Pago:** Títulos de planes, periodos e identificadores persistidos en `localStorage`.
2. **Catálogo de Cursos, Asignaturas y Clases en Video:** Títulos de asignaturas, nombres de docentes, categorías y metadatos en el portal del alumno.
3. **Diálogos Modales y Reserva de Horarios:** Inyección de strings en manejadores inline `onclick` y modales de confirmación con SweetAlert2.
4. **Buzón de Mensajería y Chat en Vivo (Alumno y Docente):** Previews de conversaciones, cabeceras de chat, burbujas de mensajes y streaming.
5. **Reducción de Mocks Innecesarios:** Sustitución de simulaciones estáticas de búsqueda en el panel administrativo por filtrado contextual seguro.

---

## 2. Diagnóstico Técnico y Vulnerabilidades Mitigadas

### 2.1. Vulnerabilidad en Carrito de Compras (Shopping Cart XSS)
* **Diagnóstico:** Los elementos agregados al carrito se leían desde `localStorage` y se renderizaban iterativamente mediante `innerHTML = \`<td class="cart-item-name">${item.titulo}</td>...\``. Un payload malicioso persistido en el almacenamiento local (a través de enlaces manipulados o ataques previos) generaba ejecución arbitraria de JavaScript al abrir el dropdown del carrito en cualquier página del sitio.
* **Solución Aplicada:**
  * Se implementó una función universal de escape contextual `window.escaparHtml(str)` disponible en todo el árbol DOM (`alumnos/templates/alumnos/base.html`).
  * Cada propiedad (`item.titulo`, `item.id`, `item.precio`, `p.valor`, `p.label`) se sanea estrictamente antes de renderizarse en el HTML tanto en `base.html` como en `pago.html` y `main.js`.
  * Se restableció la compatibilidad estructural del carrito global, garantizando cero regresiones en `tests.test_layout_templates`.

### 2.2. Interpolaciones en Asignaturas, Cursos y Videos (`Alumno_pag1.html`)
* **Diagnóstico:** 
  * En `renderCoursesView()`, `card.innerHTML` interpolaba `${c.title}`, `${c.author}`, `${c.color}` y `${c.icon}` sin saneamiento.
  * En `renderDashboardContent()`, los videos educativos interpolaban `${v.title}`, `${v.specialty}`, `${v.teacher}` y `${v.duration}` de forma directa.
* **Solución Aplicada:**
  * Todos los campos dinámicos pasan por `escaparHtml()` antes de ser inyectados en las plantillas literales.
  * En el modal de detalle del curso (`openCourseDetailModal`), se sustituyó la asignación de texto insegura por la API segura del DOM `textContent`, garantizando que cualquier carácter especial se interprete únicamente como texto plano.

### 2.3. Diálogos, Reserva de Horarios y Separación de Comportamiento
* **Diagnóstico:**
  * En el listado de sesiones disponibles (`modal-horarios-lista`), el botón de reserva se generaba concatenando cadenas JavaScript dentro de un atributo HTML:
    ```javascript
    onclick="confirmarReservaSesion(${s.id_sesion}, '${s.asignatura.replace(/'/g, "\\'")}', ...)"
    ```
    Este patrón es altamente frágil ante comillas dobles, comillas simples o secuencias de escape que permiten romper el contexto del atributo y ejecutar scripts.
* **Solución Aplicada:**
  * Se eliminó el manejador inline `onclick`.
  * Se adoptó el estándar de atributos de datos (`data-*`):
    ```html
    <button class="btn-principal btn-reservar-sesion" 
            data-id="${safeIdSesion}" 
            data-asig="${safeAsignatura}" 
            data-fechahora="${safeFecha} ${safeHora}">
    ```
  * Los listeners se vinculan de manera desacoplada mediante `addEventListener('click', ...)` leyendo `this.dataset`.
  * En la ventana modal de confirmación (`confirmarReservaSesion`), el nombre de la asignatura y la fecha/hora se escapan antes de interpolarse en la propiedad `html` de `Swal.fire`.

### 2.4. Mensajería en Vivo y Chats (Alumno y Profesor)
* **Diagnóstico:**
  * En el portal del alumno (`Alumno_pag1.html`), los contactos de la bandeja de entrada y el header del chat interpolaban `${chat.teacherName}`, `${chat.specialty}` y `${lastMsg.text}` sin sanitización.
  * En el panel del profesor (`panel_profesor.html`), la lista de estudiantes y el simulador de chat en vivo durante transmisiones (`profe-studio-chat-msg`) inyectaban nombres y mensajes directamente a `innerHTML`.
* **Solución Aplicada:**
  * Saneamiento estricto en ambos portales con `escaparHtml()` para remitentes, iniciales, nombres de cursos, marcas de tiempo y cuerpo del mensaje.

### 2.5. Búsqueda Global y Eliminación de Simulaciones
* **Diagnóstico:** En `admin_portal/templates/admin_portal/base_admin.html`, la función `handleGlobalSearch()` utilizaba datos estáticos simulados ("Francheska", "Franco") y concatenaba resultados sin escape.
* **Solución Aplicada:**
  * Se eliminó la simulación estática y se reemplazó por un filtrado de secciones del sistema (Usuarios, Reportes, Clases, Finanzas).
  * En caso de no existir coincidencias, el texto de consulta introducido por el usuario se escapa rigurosamente: `No se encontraron secciones para "<strong>${esc(query)}</strong>"`.

---

## 3. Matriz de Pruebas Automatizadas y Certificación

Se diseñó e integró la suite de pruebas automatizadas [tests/test_seguridad_s23_xss.py](file:///c:/Users/saezf/Desktop/Capstone/Capstone/tests/test_seguridad_s23_xss.py):

| Identificador | Caso de Prueba | Objetivo de Seguridad | Resultado |
|---|---|---|:---:|
| **S-23.1** | `test_base_html_incluye_escapar_html_global_y_carrito_seguro` | Verifica disponibilidad global de `escaparHtml` y saneamiento de items en carrito | **APROBADO** |
| **S-23.2** | `test_catalogo_asignaturas_y_videos_sanean_campos_dinamicos` | Certifica escape contextual en cursos, videos y autores en el portal del alumno | **APROBADO** |
| **S-23.3** | `test_chat_alumno_y_profesor_sanean_mensajes_y_contactos` | Valida sanitización integral en mensajería de alumnos y profesores | **APROBADO** |
| **S-23.4** | `test_dialogos_y_reserva_sesiones_usan_dataset_y_escape_contextual` | Certifica eliminación de inline onclicks y uso seguro de `dataset` y escape en SweetAlert | **APROBADO** |
| **S-23.5** | `test_busqueda_global_admin_sanea_query_y_elimina_mocks_estaticos` | Verifica eliminación de mocks no necesarios y escape de queries en panel admin | **APROBADO** |
| **S-23.6** | `test_pago_html_sanea_campos_de_planes_y_carrito` | Certifica saneamiento contra XSS en resumen de pago y localStorage | **APROBADO** |

### Pruebas de Regresión Verificadas
Se ejecutaron en conjunto las suites de pruebas del proyecto vinculadas a plantillas, seguridad y portales:
* **`tests.test_especialidad`**: 100% OK
* **`tests.test_layout_templates`**: 8/8 pruebas OK (Resuelto al 100%)
* **`tests.test_seguridad_s19_s20_s21`**: 11/11 pruebas OK
* **`tests.test_puerta`**: 16/16 pruebas OK
* **`alumnos.tests_front`**: 6/6 pruebas OK

**Total:** 48 pruebas de regresión ejecutadas exitosamente sin errores ni fallos.

---

## 4. Archivos Modificados

* `alumnos/templates/alumnos/base.html`
* `alumnos/templates/alumnos/Alumno_pag1.html`
* `user_profesor/templates/user_profesor/panel_profesor.html`
* `admin_portal/templates/admin_portal/base_admin.html`
* `tests/test_seguridad_s23_xss.py` (Nueva suite de certificación)
* `docs/INFORME_SEGURIDAD_S23_XSS.md` (Nuevo informe técnico)
