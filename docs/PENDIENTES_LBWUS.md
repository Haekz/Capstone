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
- ~~Posible CSS muerto en `pago/01_pago.css`.~~ **Hecho (21-nov).** Ese archivo ya se había borrado (`cfc420f`); lo que
  quedaba muerto era `pago/02_confirmacion.css`: 19 de sus 40 clases (los paneles de resumen y Webpay, el «stepper» y
  sus variantes en oscuro) no las usa ninguna plantilla, JS, vista ni prueba. Se quitaron 33 selectores (180 líneas) y se
  recortaron dos reglas mixtas; comparado contra `HEAD`: ninguna clase viva perdida ni alterada.
- ~~Porcentajes escritos a mano~~ **Hecho (21-nov).** «15 %», «85 %» y «25 %» de `finanzas.html` (admin) y `saldo.html`
  (docente) salen ahora de `paquetes.porcentajes()` (`COMISION`, `1 - COMISION`, `COMISION_VIDEOS`); `porcentaje()` no corta
  decimales (`int(COMISION * 100)` mostraba 12,5 como 12; lo usan también Planes y Términos). Pruebas:
  `test_porcentajes_en_pantalla.py`, que cambia la tasa y mira la pantalla, y una guardia que falla si cualquier plantilla
  vuelve a escribir uno de esos números.
- ~~«Detalle de liquidaciones» del docente siempre salía vacía.~~ **Hecho (21-nov).** La tabla recorría `desgloses_profesor`,
  que ninguna vista pasaba desde que la migración `0024` quitó `DesgloseOperacion`. Ahora la arma
  `user_profesor/detalle_liquidaciones.py` con la misma cuenta que el saldo: una fila por cada clase dictada (o cancelada
  con menos de 4 h, que también se paga) y por cada video compartido, con lo que pagó el alumno, la comisión (15 % en
  clases, 25 % en videos) y el abono; las 50 más recientes y un aviso con el total. Para no duplicar la cuenta de videos,
  `saldos.valores_videos` pasa a apoyarse en `saldos.videos_con_valor`. Una prueba exige que la suma de las filas sea
  exactamente `calcular_saldos` (total, disponible y pendiente), y una mutación (cobrar a los videos la comisión de
  clases) la hace fallar. Se quitaron las columnas N.º y Estado: venían del modelo borrado, y los retiros no son por
  operación (están en el historial). En celular los importes quedaban fuera de pantalla: celdas más apretadas y un aviso
  sobre la tabla («Desliza la tabla…»). Contraste medido en el navegador con datos reales (24 casos, claro y oscuro,
  escritorio y celular): peor 5,1:1.
- ~~Token `--ok` no llegaba a 4,5:1 en claro.~~ **Hecho (21-nov).** Era peor que lo anotado: 4,35:1 es sobre blanco, pero
  casi todos los usos son chips sobre `--ok-soft` y fondos lila, donde daba 3,55 a 3,83:1. Ahora `--ok` claro es
  `#066b4c` (mismo tono) en los cuatro archivos que lo definen (alumno y apoderado, docente, admin y soporte); el oscuro
  (`#34d399`) no cambia. Medido en el navegador con datos de la demo, 5 portales en claro y oscuro, con el tema puesto como
  lo pone la app (`theme` y `admin-theme`): antes 27 fallas, ahora 0; peor uso real 5,33:1 (modalidad y Valores) y 4,9:1
  en el peor chip de prueba (`puppy_workspace/ok_medir_contraste.py`). De paso: `.tc-vence` (tarjeta de clases del banner,
  blanca también en oscuro) llevaba `#0f8a60` fijo y fallaba en los dos temas: va con el verde nuevo, fijo a propósito;
  el abono del Detalle de liquidaciones ya no necesita su verde propio (usa `--ok`); y se quitaron los respaldos
  `var(--ok, #0f8a60)` de `16_portal_apoderado.css`, que nunca se usaban (ese portal siempre carga `13_pulido.css`).
  Pruebas: `test_contraste_tokens.py` (contraste en cada portal, las cuatro copias iguales y la tarjeta con el mismo verde);
  volver a `#0f8a60` la hace fallar.
- ~~Admin, Nosotros: «Fundación», «Sede» y «Contacto» casi no se leían.~~ **Hecho (21-nov), visto en las capturas de `--ok`.**
  Usaban `--text-muted`: 2,75:1 en claro (4,56:1 en oscuro). Ahora `--text-secondary`, como el placeholder: 5,1:1 y 8,0:1,
  medido en el navegador. `.stat-mini` solo existe en esa pantalla. Prueba en `test_pulido_admin_paginas.py`.
- ~~Token `--warn` (`#b45309`): mismo problema que tenía `--ok`.~~ **Hecho (21-nov).** Medido en el navegador como `--ok`
  (5 portales, claro y oscuro, tema puesto como lo pone la app; los usos que dependen de datos, como contadores casi llenos
  o plazos por vencer, con su marcado real insertado junto a un ancla y quitado después): antes 7 fallas (ícono de Visión
  4,2:1, `.tc-vence--pronto` 4,44:1 en los dos temas, chips 3,9:1) y cuatro usos en 4,51:1 justo; ahora 0, el peor 4,88:1.
  Ahora `--warn` claro es `#9c4708` (mismo tono) en los cuatro archivos; el oscuro (`#fbbf24`) no cambia. Las copias fijas
  (`.tc-vence--pronto`, `.badge-pendiente`, `.horario__cupos--pocos`, `.auth-icon--warn`) usan ese mismo color: solo
  aplican en claro o sobre fondo blanco también en oscuro. Fuera `.badge-admin` (sin uso: la clase sale de la modalidad, y
  solo existe `online`) y los respaldos `var(--warn, …)` del apoderado. `.pp-vence--pronto` no sale con los datos de la
  demo: es el mismo `var(--warn)` sobre `--warn-soft` que mide la sonda (5,69:1 y 8,48:1). Pruebas: `test_contraste_tokens.py`
  (los dos tokens, y que cada copia fija coincida con su token); volver al color viejo, o separar una copia, la hace fallar.
- ~~Token `--bad` (soporte) no llegaba a 4,5:1 en claro.~~ **Hecho (21-nov), visto en las capturas de `--warn`.** El chip
  «Vencido» (`.sop-plazo--vencido`, su único uso) daba 4,44:1 y 3,78:1 en la tarjeta de la revisión. Ahora `#a8380a`
  (mismo tono que `#c2410c`): antes 6 fallas, ahora 0, el peor 4,73:1; el oscuro no cambia. Prueba en
  `test_contraste_tokens.py`.
- **`--text-muted` se usa como color de texto y no llega a 4,5:1 ni en claro ni en oscuro (visto el 21-nov, sin resolver).**
  Medido en el navegador: etiquetas del detalle de ticket de soporte (`dt`: «Abierto por», «Vence»…) 2,99:1 en claro y
  4,30:1 en oscuro; antes ya se arreglaron, una a una, el placeholder y «Fundación / Sede / Contacto» (2,75:1). Es un token
  global de los portales admin, docente y soporte (`04_rediseno_marco.css`: `#9892ab` claro, `#7d7794` oscuro; y
  `01_base.css`), con 53 usos en 17 hojas y 16 estilos en línea en plantillas (p. ej. banco y cuenta en Finanzas). Decidir
  antes de tocar: oscurecer el token (arregla todo, pero acerca «muted» a `--text-secondary` y se pierde un nivel de
  jerarquía) o pasar los usos que son texto a `--text-secondary` y dejar `--text-muted` solo para lo decorativo.

## Arreglos acordados (20-nov): orden de trabajo, en `fran-pulido-apoderado`
Decididos con Fran el 20-nov. Van en este orden (bugs primero) y cada uno con sus pruebas, su commit y esta lista al día.
Antes (16-nov) las etapas A1 a A6 dejaron las 10 pantallas del admin iguales a la copia (0 px de diferencia, salvo datos
de la demo); los puntos 3 y 4 son lo que se vio al comparar y no se tocó porque cambia comportamiento.

1. ~~Planes: las vigencias de «Condiciones» están mal.~~ **Hecho (20-nov).** Se leen de `PLANES`; la prueba
   `test_condiciones_dicen_las_vigencias_de_planes` compara la sección con `PLANES`. Términos y Privacidad ya usaban
   variables: no había otras cifras escritas a mano.
2. ~~Planes: no se leen los enlaces de Términos y Privacidad en la tarjeta oscura.~~ **Hecho (20-nov).** En `planes.css`
   (el único CSS que carga Planes en todos sus marcos): enlaces en lila `#c4b5fd` (9,7:1; 8,2:1 en oscuro), foco y check
   con `--accent`, y una variante con `#portal-alumno` que le gana a `13_pulido.css`. Pruebas en
   `test_planes_en_portal.py` (leen los colores de los CSS). Medido en el navegador en los marcos público, alumno y
   apoderado, claro y oscuro: 6/6 (`puppy_workspace/verificar_contraste_planes.py`).
3. ~~Admin: Ajustes no guarda nada.~~ **Hecho (21-nov).** `POST /admin_portal/ajustes/` (`ajustes_admin`, solo admin) con
   `AjustesAdminForm`: nombre y correo obligatorios, teléfono y dirección opcionales (`crear_admin` no los pide). El
   **RUT es de solo lectura** y no viaja en el formulario. Correo único sin distinguir mayúsculas; teléfono chileno de
   9 dígitos, guardado normalizado (`normalizar_telefono`, acepta `+56 9 1234 5678`). Con errores vuelve a Ajustes con
   lo escrito, cada mensaje junto a su campo (`aria-invalid` y `aria-describedby`) y el foco en el primero; el menú
   conserva el nombre guardado. El color de acento sigue siendo solo de la sesión. Pruebas: `test_admin_ajustes.py`.
   Medido en el navegador, claro y oscuro: error 6,5:1 y 9,6:1; RUT 5,1:1 y 8,0:1
   (`puppy_workspace/verificar_ajustes_admin.py`, solo envía datos inválidos).
   **Arreglado de paso:** un RUT es el mismo con o sin puntos y guion, con k o K, pero `usuario_existe` y el
   formulario de alumnos del admin comparaban el texto tal cual: con `12.345.678-5` se creaba una segunda cuenta de
   quien ya era `12345678-5`. Ahora todos usan `rut_en_uso` y `correo_en_uso` (`alumnos/utils.py`; `crear_admin`
   también). Pruebas: `test_rut_en_otro_formato.py`.
4. ~~Admin: un solo «Usuarios».~~ **Hecho (21-nov).**
   - (a) `crud` y `reporte_alumnos` (misma vista) solo redirigen a `dashboard_admin#usuarios`, con `@admin_required`; se
     borró `alumnos_list.html` y el `.alert-ok` que solo él usaba. (b) `alumnos_del` redirige a Usuarios con su aviso
     por `messages` (eliminado o seudonimizado). (c) El menú de `base_admin.html` siempre va a Usuarios del dashboard
     (se quitó el bloque `nav_usuarios_href`). Pruebas: `test_admin_un_solo_usuarios.py`; ajustadas las que nombraban
     `crud` (`test_control_acceso`, `test_boton_atras`, `test_portales_por_rol`, `test_qa_acceso`,
     `test_mensajes_supresion`). `usabilidad/recorrido.py`: el paso 24 ahora abre `dashboard/#usuarios`; los resultados
     guardados (`resultados_antes/despues.json`) son del listado viejo.
   - (d) **Cambió por una decisión (21-nov): el admin ya no agrega ni edita alumnos; solo ve el listado y elimina.** Crear y
     editar dejaba al admin con la clave, el correo y el RUT de otra persona, y la cuenta nacía sin que el titular
     aceptara Términos ni Privacidad. Se borraron las vistas `alumnos_Add`, `alumnos_findEdit` y `alumnos_Update`, sus
     rutas, `alumnos_add.html`, `alumnos_edit.html`, el formulario `AdminAlumnoForm`, el botón «Agregar alumno» y el lápiz
     «Editar» del listado. Adultos: se registran solos; menores: los registra su apoderado (que ya les pone y renueva la
     clave); un dato mal escrito, por ahora, lo corrige un superusuario en `/admin/`. S-03 (clave igual al RUT) queda
     cerrado porque ya no hay dónde fijarle la clave a un alumno (`MATRIZ_IDENTIDAD.md`). Pruebas: `test_admin_un_solo_usuarios.py`,
     `S03ClaveInicialTests`; se retiraron las que probaban ese formulario. Quedó de esa pasada el placeholder y el campo de
     solo lectura legibles en todo `.form-input` del panel (5,1:1 y 8,0:1; antes 2,75:1 en claro).
   - **Idea, no hacer ahora (YAGNI):** una herramienta de soporte para corregir un dato o crear la cuenta de un alumno cuando
     algo falle (el caso real sería el de apoderados). Condiciones si se hace: atada a un ticket, con registro de quién
     cambió qué, sin tocar RUT ni correo, con clave temporal que el alumno (o su apoderado) cambia al entrar y
     aceptando Términos. Hoy los agentes no pueden crear ni editar cuentas. Tampoco hay pantalla donde un alumno adulto
     edite su nombre, teléfono o dirección (los profesores sí la tienen): si se vuelve frecuente, es la mejor opción.
5. ~~Soporte: el menú de Verificaciones según quién entra.~~ **Hecho (21-nov).** `AgenteSoporte.ve_apoderados` y
   `ve_documentos` (una consulta por página) mandan en `base_soporte.html`: el agente ve **Apoderados** solo si atiende
   `apoderados` y **Documentos de profesores** solo si atiende `titulos` o `especializaciones`, bajo **«Verificaciones»**
   (sin ningún tema, el grupo no sale). El líder las ve siempre, bajo **«Supervisión»**, porque para él es control
   (historial, vínculos con «Revocar», quien abrió cada documento). El buscador Ctrl+K lee los enlaces del menú, así que
   se ajusta solo. Es solo el menú: las pantallas siguen abiertas por URL (vacías) y filtran por ticket como antes.
   Pruebas: `VerificacionesDelMenuTests` en `test_menu_soporte.py`; `test_pulido_soporte_marco.py` ajustada.
6. ~~Planes: diseño más profesional.~~ **Hecho (21-nov), salvo el nombre del menú (ver abajo).** En `planes.html` y `planes.css`:
   - **Casilla de Términos** (se queda en cada tarjeta): ahora es una cajita con aire, antes del botón, con su propio
     estilo en `planes.css`, que carga en todos los marcos (el estilo estaba solo en `styles/10_legal.css`, que
     únicamente carga el sitio público). En la tarjeta oscura su texto va en blanco: el primer intento lo dejaba oscuro
     sobre oscuro («Acepto los» no se veía).
   - **Desglose** (comisión con IVA y «El profesor recibe») en un `<details>` «Ver desglose», plegado: sigue en la
     página, sin competir con el precio, y funciona con teclado y lector de pantalla sin JS.
   - **Jerarquía del precio:** precio del paquete, luego el precio por clase en su propia línea y de color, y la letra
     chica solo con las clases, los minutos y «Sin renovación obligatoria». Beneficios con el mismo ícono (check).
   - **Etiqueta «Mejor precio por clase»** (antes «Mayor descuento», que no decía de qué), sobre el borde de la tarjeta:
     antes ocupaba sitio dentro y el título «Plan Intensivo» se partía en dos líneas, empujando el precio y el botón
     de esa tarjeta más abajo que en las otras dos.
   - **«Ver perfil del profesor»** en su propio enlace, con ícono y sin partirse.
   - **Arreglado de paso:** en el portal del apoderado, en celular, el selector de profesor meduía cientos de píxeles de
     alto (`flex: 1 1 260px` de `16_portal_apoderado.css` pasaba a ser su alto cuando `planes.css` apila la fila).
   - **Condiciones, explicación y caja del apoderado (pedido de Fran, 21-nov):** «Condiciones» dejó de ser una caja grande y es
     un control «(?) Condiciones» **bajo las tarjetas** (portales y sitio público): la ventanita se abre al pasar el mouse
     y también con clic, teclado o toque (es un `<details>` con un poco de JS en la página); Esc o un clic afuera la
     cierran, y se puede llegar a ella con el mouse (WCAG 1.4.13). La explicación («Compras un paquete…» y los datos de 60
     minutos, comisión y Webpay) pasa **bajo las tarjetas** en el portal del alumno y del docente (en el sitio público y en
     el del apoderado sigue en el hero); es el fragmento `includes/planes_resumen.html`. En el portal del apoderado se
     **quitó la caja lila** («Contratando para Nico…» / «Precios con …»): repetía la barra, el selector y cada botón. El
     alumno conserva su encabezado con el profesor y el enlace al perfil. De paso se borraron los estilos que quedaron sin
     uso (`.pl-intro--portal` y las reglas de esa caja en `16_portal_apoderado.css`).
   - Un comentario `{# #}` de Django partido en dos líneas salió como texto crudo en la página (lo mostraron las
     capturas): solo vale en una línea. Hay una prueba que impide que algún comentario salga en esta página.
   - Contraste medido en el navegador: 106 casos (visitante, alumno, docente y apoderado, en claro y oscuro), todos ≥ 4,5:1
     (peor: 5,1:1). La medición encontró «Ver perfil del profesor» en 2,3:1 en oscuro: en el portal el `body` ES
     `#portal-alumno`, así que se escribe `body.dark-mode#portal-alumno` (pegado), no con espacio.
   - Pruebas: `test_planes_diseno.py`. Capturas del antes y el después en `puppy_workspace/capturas_punto6`.
   - **A decidir (no se cambió):** el menú dice «Mis paquetes» (lo que ya compró) y la barra, en esta página, «Planes y
     precios» (lo que puede comprar): son dos pantallas distintas, unidas por los botones «Ver planes y precios» /
     «Comprar más clases», y la vista deja marcado «Mis paquetes» a propósito (hay una prueba que lo fija). Si se quiere
     otro nombre, hay que cambiar a la vez el título, esos botones y esa prueba.
   - Quedan como estaban: los botones «Inicia sesión para buscar un profesor» del
     visitante se parten en dos líneas; el recuadro «Portal del alumno · Ana, alumna» del video lo pone
     `video_demo/guion.py`, no la app.

- Para una demo sin conexión: SweetAlert viene de internet (ver el pendiente de abajo); sin él, «Eliminar» usa el
  `confirm()` del navegador.
- Los scripts de verificación (comparador con la copia, claro, oscuro y celular; Resumen; Usuarios; HTML de Soporte)
  están en `puppy_workspace`, fuera del repositorio.

## Antes de abrir al publico: lo que faltaba en esta lista (revision del 15-nov)
- **Cerrar la CSP.** Sigue en Report-Only (`CSP_OBLIGATORIA`), permite `'unsafe-inline'` (hay scripts, `onclick=` y
  `style=` en linea en las plantillas) y no tiene destino para reportes: hoy no bloquea nada. Es trabajo grande:
  sacar lo que esta en linea, mirar los reportes y recien ahi hacerla obligatoria.
- ~~SweetAlert2 sigue viniendo de internet.~~ **Hecho (21-nov).** Alojado en `lbwus/static/vendor/sweetalert2/` (v11.26.25,
  fija, con su licencia MIT y su SHA-256 en `LEEME.txt`); las 6 plantillas lo cargan con `{% static %}` y se quitó
  `https://cdn.jsdelivr.net` de `script-src` (ahora solo queda Jitsi). Medido en el navegador con jsDelivr bloqueado:
  las 6 pantallas que lo usan abren su aviso, sin peticiones a internet ni avisos de CSP; `collectstatic` como en Railway
  lo recoge con hash. Tampoco es propia la letra del correo de recuperar clave: un correo no puede traer archivos.
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
