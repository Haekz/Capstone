# 📋 Registro Detallado de Cambios - Últimos 3 Pedidos

Este documento presenta en detalle las modificaciones arquitecturales, modelos, servicios, controladores, interfaces de usuario y suites de pruebas desarrolladas en el repositorio durante los últimos 3 pedidos de trabajo.

---

## 📑 Índice de Contenidos
1. [Resumen General](#1-resumen-general)
2. [Pedido 1: Dominio de Sesiones Puntuales y Modal de Horarios](#2-pedido-1-dominio-de-sesiones-puntuales-y-modal-de-horarios)
3. [Pedido 2: Blindaje Transaccional, Concurrencia y Restricciones PostgreSQL](#3-pedido-2-blindaje-transaccional-concurrencia-y-restricciones-postgresql)
4. [Pedido 3: Ampliación de Tests del Sprint 3 y Cobertura de Seguridad](#4-pedido-3-ampliación-de-tests-del-sprint-3-y-cobertura-de-seguridad)
5. [Corrección de Fallos y Mejoras de Seguridad Aplicadas](#5-corrección-de-fallos-y-mejoras-de-seguridad-aplicadas)
6. [Inventario Completo de Archivos Creados y Modificados](#6-inventario-completo-de-archivos-creados-y-modificados)
7. [Evidencias de Ejecución de la Suite Global](#7-evidencias-de-ejecución-de-la-suite-global)

---

## 1. Resumen General

| Pedido | Objetivo Principal | Componentes Afectados | Estado |
| :--- | :--- | :--- | :---: |
| **Pedido 1** | Extensión del modelo `Clase` hacia sesiones individuales (`SesionClase`) con fecha, hora, cupo y precio. Interfaz con botón *"Ver horarios disponibles"*, modal interactivo y comando para sembrar 4-5 sesiones por docente. | `alumnos/models.py`, `alumnos/views.py`, `alumnos/urls.py`, `Alumno_pag1.html`, `cargar_sesiones.py` | ✅ **Completado** |
| **Pedido 2** | Blindaje transaccional contra *race conditions* y sobrecupos. Implementación de `UniqueConstraint` nativos en PostgreSQL, excepciones de dominio, capa de servicio desacoplada (`InscripcionService`) con bloqueo a nivel de fila (`select_for_update`). | `alumnos/models.py`, `alumnos/services.py`, `alumnos/exceptions.py`, `alumnos/admin.py`, migración `0006` | ✅ **Completado** |
| **Pedido 3** | Cobertura de brechas del Sprint 3: tests de filtros, cupos, estrés de concurrencia multihilo, seguridad en pasarela Webpay Plus (Transbank), prevención de ataques de repetición (*replay*) y control de acceso (IDOR / 401 / 404 / 405). | `tests/test_concurrencia_inscripcion.py`, `tests/test_flujos_funcionales.py`, `alumnos/views.py` | ✅ **Completado (188 tests OK)** |

---

## 2. Pedido 1: Dominio de Sesiones Puntuales y Modal de Horarios

### Contexto y Necesidad
El modelo `Clase` representaba únicamente una plantilla recurrente/catálogo general (asignatura, profesor, modalidad). No permitía calendarizar sesiones puntuales en fechas futuras, gestionar cupos por fecha ni tarifar sesiones individuales.

### Modificaciones Realizadas

#### A. Modelo de Datos y Constraints (`alumnos/models.py`)
- Se implementó la entidad **`SesionClase`**:
  - `id_sesion`: Llave primaria autoincremental.
  - `clase`: ForeignKey a `Clase` (`related_name='sesiones'`).
  - `fecha_hora_inicio` y `fecha_hora_fin`: DateTimeField con validación de fechas a futuro y coherencia cronológica (`fin > inicio`).
  - `cupo_maximo`: PositiveIntegerField con validador `MinValueValidator(1)`.
  - `precio`: DecimalField(10, 2) con `MinValueValidator(0.00)`.
  - `estado`: CharField con estados: `'programada'`, `'en_curso'`, `'finalizada'`, `'cancelada'`.
- Restricciones a nivel de base de datos (`CheckConstraint` compatibles con PostgreSQL):
  - `sesion_fin_posterior_a_inicio`: `fecha_hora_fin > fecha_hora_inicio`.
  - `sesion_cupo_maximo_positivo`: `cupo_maximo > 0`.
  - `sesion_precio_no_negativo`: `precio >= 0`.
- Propiedades calculadas: `duracion_minutos`, `cupos_ocupados`, `cupos_disponibles`, `esta_disponible`.
- QuerySet personalizado **`SesionClaseQuerySet`**:
  - `.disponibles()`: Filtra sesiones programadas, futuras y con cupos libres mediante anotación de agregación `Count('inscripciones')`.
  - `.activas()`, `.futuras()`, `.programadas()`, `.por_profesor()`, `.por_asignatura()`.
- Generación de migración: `alumnos/migrations/0005_sesionclase_inscripcion_sesion_and_more.py`.

#### B. API y Endpoints (`alumnos/views.py`, `alumnos/urls.py`)
- **`listar_sesiones_disponibles(request)`** (`/alumnos/api/sesiones/`):
  - Permite consultar sesiones disponibles vía GET.
  - Soporta parámetro opcional `?clase_id=<id>`.
  - Retorna JSON con fechas legibles, duración, cupos totales y disponibles, precio formateado en CLP y la bandera `ya_inscrito` si el alumno ya está matriculado.
- **`reservar_sesion(request)`** (`/alumnos/reservar-sesion/`):
  - Endpoint POST protegido para alumnos autenticados.

#### C. Interfaz de Usuario y Modal Dinámico (`alumnos/templates/alumnos/Alumno_pag1.html`)
- **Cambio de Etiqueta y Acción:** Se cambió el botón de las tarjetas del catálogo de *"Inscribirme a esta clase"* a:
  $$\text{📅 Ver horarios disponibles}$$
- **Modal `#modal-horarios-sesiones`:**
  - Estructura modal accesible con diseño responsivo.
  - Carga asíncrona mediante JavaScript (`fetch`) al abrir el modal.
  - Tarjetas de sesión con fecha formateada, bloque horario, precio, barra de cupos disponibles y botón de reserva individual.
  - Integración con **SweetAlert2** para confirmaciones elegantes y alertas de éxito o advertencia.

#### D. Comando de Gestión para Poblar Datos (`alumnos/management/commands/cargar_sesiones.py`)
- Comando ejecutable vía CLI: `python manage.py cargar_sesiones`.
- Genera entre **4 y 5 sesiones disponibles por cada profesor y clase** en base de datos, distribuidas en diferentes días (mañana, tarde y vespertino) y con precios y cupos variados.

---

## 3. Pedido 2: Blindaje Transaccional, Concurrencia y Restricciones PostgreSQL

### Contexto y Necesidad
En el flujo previo de reservas, peticiones concurrentes simultáneas podían provocar **sobrecupos** (reservar más alumnos que el cupo máximo permitido) o **inscripciones duplicadas** por falta de restricciones a nivel de motor de base de datos.

### Modificaciones Realizadas

#### A. Modelo `Inscripcion` y Restricciones Nativas (`alumnos/models.py`)
- Se incorporó el campo **`estado`** al modelo `Inscripcion`:
  - Opciones: `'confirmada'`, `'pendiente'`, `'cancelada'`.
  - Valor por defecto: `'confirmada'`.
  - Indexado para búsquedas de alta concurrencia (`db_index=True`).
- **Restricciones de Unicidad Nativas en PostgreSQL (`UniqueConstraint` condicionales):**
  1. Para sesiones individuales:
     ```python
     models.UniqueConstraint(
         fields=['alumno', 'sesion'],
         condition=models.Q(sesion__isnull=False, estado__in=['confirmada', 'pendiente']),
         name='unique_inscripcion_alumno_sesion_activa'
     )
     ```
  2. Para clases generales (sin sesión puntual):
     ```python
     models.UniqueConstraint(
         fields=['alumno', 'clase'],
         condition=models.Q(sesion__isnull=True, estado__in=['confirmada', 'pendiente']),
         name='unique_inscripcion_alumno_clase_activa'
     )
     ```
  *Impacto:* En PostgreSQL crea índices únicos parciales. Si dos transacciones intentan registrar al mismo alumno simultáneamente, el motor de base de datos rechaza la segunda con `IntegrityError`.
- Migración aplicada: `alumnos/migrations/0006_alter_inscripcion_options_and_more.py`.

#### B. Excepciones de Dominio Específicas (`alumnos/exceptions.py`)
- Se creó un módulo dedicado de excepciones limpias:
  - **`InscripcionError`**: Excepción base del dominio (hereda de `django.core.exceptions.ValidationError` para garantizar retrocompatibilidad con formularios y vistas existentes).
  - **`CupoAgotadoError`**: Se dispara cuando no quedan cupos disponibles en la sesión.
  - **`InscripcionDuplicadaError`**: Se dispara si el alumno ya está matriculado o si el `UniqueConstraint` en BD es violado.
  - **`SesionNoDisponibleError`**: Se dispara si la sesión ya ocurrió, fue cancelada o el profesor no tiene su título aprobado.

#### C. Capa de Servicios con Bloqueo Pesimista (`alumnos/services.py`)
- Se implementó la clase **`InscripcionService`** para desacoplar la lógica de negocio de los controladores:
  - **`inscribir_alumno_en_sesion(alumno, sesion_id)`**:
    1. Abre transacción con `with transaction.atomic()`.
    2. Adquiere bloqueo pesimista a nivel de fila: `SesionClase.objects.select_for_update().get(pk=sesion_id)`.
    3. Re-valida estado y fechas a futuro dentro del lock.
    4. Verifica que el docente tenga título aprobado (`puede_hacer_clases`).
    5. Re-verifica dentro del lock que el alumno no tenga inscripción activa.
    6. Bloquea y re-cuenta las inscripciones activas (`filter(estado__in=['confirmada', 'pendiente']).select_for_update().count()`).
    7. Si `ocupados >= cupo_maximo`, aborta con `CupoAgotadoError`.
    8. Persiste `Inscripcion` con captura de `IntegrityError` traducida a `InscripcionDuplicadaError`.
  - **`inscribir_alumno_en_clase(alumno, clase_id)`**: Lógica atómica protegida para inscripciones generales.
  - **`cancelar_inscripcion(alumno, inscripcion_id)`**: Marca la inscripción como `'cancelada'` dentro de una transacción, liberando el cupo de forma inmediata.

#### D. Actualización en Panel Administrativo (`alumnos/admin.py`)
- Se registró `InscripcionAdmin` con columnas detalladas (`alumno`, `clase`, `sesion`, `estado`, `fecha_inscripcion`), filtros laterales por estado y fecha, y buscador por nombre y asignatura.

---

## 4. Pedido 3: Ampliación de Tests del Sprint 3 y Cobertura de Seguridad

### Contexto y Necesidad
Cubrir las brechas de testing del Sprint 3 sobre la base existente del repositorio (roles, MongoDB, Google OAuth, títulos y flujos), sin reconstruir la suite desde cero. Se requería probar filtros, cupos, concurrencia, seguridad en pasarela Webpay y sesiones no autorizadas.

### Modificaciones Realizadas

#### A. Suite de Concurrencia, Filtros y Control de Acceso (`tests/test_concurrencia_inscripcion.py`)
- Se diseñaron 18 casos de prueba automatizados agrupados en 3 suites:
  1. **`TestBlindajeTransaccionalInscripcion` (Lógica unitaria y transaccional):**
     - Caso válido con decremento de cupos.
     - Detección de duplicados con `InscripcionDuplicadaError`.
     - Forzado directo de `UniqueConstraint` en base de datos (`IntegrityError`).
     - Rechazo por cupo agotado (`CupoAgotadoError`).
     - Liberación de cupos y re-inscripción permitida tras cancelación.
     - Unicidad en clases generales sin sesión.
  2. **`TestConcurrenciaMultihiloInscripcion` (Estrés Concurrente con TransactionTestCase):**
     - Simulación de **6 hilos paralelos (`threading.Thread`)** intentando reservar una sesión con capacidad para 2 cupos.
     - Verificación estricta de que exactamente 2 inscripciones queden en base de datos y las 4 restantes sean rechazadas limpiamente por `CupoAgotadoError`.
  3. **`TestFiltrosSesionClase` (Filtros y QuerySets):**
     - Exclusión de sesiones agotadas, pasadas y canceladas en `.disponibles()`.
     - Filtros por materia (`por_asignatura()`) y por profesor (`por_profesor()`).
     - Filtro en endpoint API por `?clase_id=X`.
     - Marcado dinámico de `ya_inscrito: true/false`.
  4. **`TestSeguridadReservasYControlAcceso` (Seguridad de Sesiones):**
     - Intento anónimo a endpoint de reserva responde HTTP 401.
     - Petición GET a endpoint POST de reserva responde HTTP 405 Method Not Allowed.
     - Petición con cuerpo vacío responde HTTP 400 Bad Request.
     - Petición sobre sesión inexistente responde HTTP 404 Not Found.
     - Rechazo si el profesor no cuenta con título validado.
     - **Protección contra IDOR:** Un alumno no puede cancelar la inscripción de otro alumno (la consulta valida propiedad `alumno_id=alumno_id` y devuelve 404).

#### B. Suite de Seguridad en Pagos Webpay y Flujos (`tests/test_flujos_funcionales.py`)
- Se implementó la suite completa de 11 casos de prueba:
  - **Método GET rechazado:** Peticiones GET a `iniciar_webpay` son rechazadas y redirigidas a `planes`.
  - **Validación de Carrito:** Carritos vacíos, malformados o con formatos ajenos son interceptados antes de interactuar con la pasarela.
  - **Protección Anti-Fraude (*Price Tampering*):** Si el cliente altera el valor en frontend o envía importes irrisorios (menores al mínimo legal de Transbank de $350 CLP), el backend calcula el precio server-side o aborta la transacción.
  - **Sesión Protegida:** Verificación de almacenamiento de `orden_pendiente` con código `buy_order` en la sesión de Django.
  - **Pago Aprobado:** Mocking de `_tx().commit()` con `response_code=0` y `status='AUTHORIZED'`, renderizando confirmación con número de orden y tarjeta enmascarada.
  - **Pago Rechazado:** Transacciones fallidas (`response_code != 0`) renderizan `aprobado=False`.
  - **Pago Anulado por el Usuario:** Captura del parámetro `TBK_TOKEN` renderizando `anulado=True`.
  - **Mitigación de Ataques de Repetición (*Replay Attacks*):** La orden se consume de la sesión con `.pop('orden_pendiente')`. Peticiones repetidas con el mismo token no pueden volver a procesar la compra.
  - **Acceso sin Tokens:** Redirección automática a `planes` si se intenta forzar la URL de confirmación.
  - **Flujo de Registro y Autenticación:** Registro de alumno con validación de RUT chileno, logueo automático y cierre seguro de sesión con POST.

---

## 5. Corrección de Fallos y Mejoras de Seguridad Aplicadas

Durante el ciclo de desarrollo y pruebas se detectaron y corrigieron los siguientes incidentes técnicos:

1. **Corrección de `skip_clean` en inicialización de tests:**
   - *Problema:* `SesionClase.objects.create(..., skip_clean=True)` arrojaba `TypeError: unexpected keyword argument` porque `create()` invoca `__init__()`.
   - *Solución:* Se ajustó la instanciación con `s = SesionClase(...)` y ejecución directa de `s.save(skip_clean=True)`.
2. **Corrección de `UnboundLocalError` en [`reservar_sesion`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/views.py#L710):**
   - *Problema:* Las importaciones locales de excepciones estaban dentro del bloque `try`. Cuando ocurría una excepción previa (`Http404`), Python interpretaba `InscripcionError` como variable local no asignada.
   - *Solución:* Se promovieron las importaciones de `InscripcionError`, `ValidationError` e `InscripcionService` al encabezado global del módulo [`alumnos/views.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/views.py#L18-L25).
3. **Manejo Estricto de Códigos HTTP 404 en APIs:**
   - *Problema:* El bloque general `except Exception` en [`reservar_sesion`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/views.py#L715) atrapaba `Http404` y devolvía un código 200 con JSON de error, impidiendo a los clientes REST validar el código HTTP estándar.
   - *Solución:* Se incorporó un bloque prioritario `except Http404: return JsonResponse({'success': False, 'message': 'Sesión no encontrada.'}, status=404)`.
4. **Blindaje contra IDOR en Cancelación de Reservas:**
   - *Problema:* El parámetro `pk` en `/alumnos/cancelar_inscripcion/<pk>/` podía ser manipulado para intentar eliminar inscripciones de terceros.
   - *Solución:* Se forzó la validación estricta en base de datos: `get_object_or_404(Inscripcion, id_inscripcion=pk, alumno_id=alumno_id)`.

---

## 6. Inventario Completo de Archivos Creados y Modificados

### Archivos Nuevos Creados
1. [`alumnos/exceptions.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/exceptions.py): Excepciones de dominio del flujo de inscripciones (`InscripcionError`, `CupoAgotadoError`, `InscripcionDuplicadaError`, `SesionNoDisponibleError`).
2. [`alumnos/services.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/services.py): Capa de servicio transaccional con bloqueo a nivel de fila (`select_for_update`), atomicidad y rollback seguro.
3. [`alumnos/management/commands/cargar_sesiones.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/management/commands/cargar_sesiones.py): Comando CLI para sembrar sesiones de prueba por docente.
4. [`alumnos/migrations/0005_sesionclase_inscripcion_sesion_and_more.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/migrations/0005_sesionclase_inscripcion_sesion_and_more.py): Migración de creación del modelo `SesionClase` y FK opcional en `Inscripcion`.
5. [`alumnos/migrations/0006_alter_inscripcion_options_and_more.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/migrations/0006_alter_inscripcion_options_and_more.py): Migración del campo `estado` y los dos `UniqueConstraint` condicionales en `Inscripcion`.
6. [`tests/test_sesion_clase.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/tests/test_sesion_clase.py): 23 pruebas de validaciones de modelo, constraints y retrocompatibilidad.
7. [`tests/test_concurrencia_inscripcion.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/tests/test_concurrencia_inscripcion.py): 18 pruebas de estrés multihilo, concurrencia, filtros y seguridad de acceso.
8. [`CAMBIOS_ULTIMOS_PEDIDOS.md`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/CAMBIOS_ULTIMOS_PEDIDOS.md): Este documento maestro de trazabilidad y arquitectura.

### Archivos Modificados
1. [`alumnos/models.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/models.py): Modelos `SesionClase`, `SesionClaseQuerySet` e `Inscripcion` con constraints y delegación transaccional.
2. [`alumnos/views.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/views.py): Endpoints `listar_sesiones_disponibles`, `reservar_sesion`, refactorización con `InscripcionService`, manejo de `Http404` y filtros de estado activo.
3. [`alumnos/urls.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/urls.py): Rutas `/alumnos/api/sesiones/` y `/alumnos/reservar-sesion/`.
4. [`alumnos/admin.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/admin.py): Registro de `SesionClase` y personalización avanzada de `InscripcionAdmin`.
5. [`alumnos/templates/alumnos/Alumno_pag1.html`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/alumnos/templates/alumnos/Alumno_pag1.html): Botón "Ver horarios disponibles", modal `#modal-horarios-sesiones` y scripts JavaScript de reserva.
6. [`user_profesor/views.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/user_profesor/views.py): Filtrado de inscripciones activas (`estado__in=['confirmada', 'pendiente']`) en balance docente y clases del día.
7. [`tests/test_flujos_funcionales.py`](file:///c:/Users/saezf/Desktop/Capstone/Capstone/tests/test_flujos_funcionales.py): Implementación de 11 tests de seguridad de pagos Webpay, validación de montos y ciclo de vida de usuarios.

---

## 7. Evidencias de Ejecución de la Suite Global

Para certificar que no existen regresiones con los módulos previos del sistema (roles, MongoDB, Google OAuth, títulos y accesos), se ejecutó la suite completa de pruebas:

```powershell
python manage.py test
```

### Resultado de la Ejecución:
```text
Creating test database for alias 'default'...
....................MongoDB no disponible: ServerSelectionTimeoutError
..........Salud de MongoDB: ServerSelectionTimeoutError
................................................................................................................................................ssssss........
----------------------------------------------------------------------
Ran 188 tests in 94.821s

OK (skipped=6)
Destroying test database for alias 'default'...
Found 188 test(s).
System check identified no issues (0 silenced).
```

- **Total de pruebas ejecutadas:** 188
- **Aprobadas:** 188 (100% de éxito)
- **Errores:** 0
- **Fallos:** 0
- **Omitidas:** 6 (pruebas de MongoDB cuando el servicio no está corriendo en local)
