# LBWUS: pendientes

Actualizado: 08-nov-2026. Aqui queda solo lo que falta. Todo lo que listaba la version anterior ya esta en `main`
(35 de sus 38 ramas; las otras 3 se cierran sin mergear, LBW-16). El historial de lo hecho sigue en git:
`git show c8f3341:docs/PENDIENTES_LBWUS.md`. Las decisiones estan en DECISIONES_SOPORTE_Y_PAGOS.md.

Los codigos LBW-xx y Dx son los del backlog y las decisiones grupales del 08-nov (se cargan en Jira).

## Railway: una sola vez (ver CONFIGURACION_PRODUCCION.md)
- Servicio Cron `python manage.py tareas_diarias` a las 9:00 UTC (LBW-01). Corre las 8 tareas diarias.
- Correr una vez: `manage.py pasar_reportes_a_tickets` y `manage.py pasar_titulos_a_base` (LBW-07).
- Habilitar al menos un agente en cada tema nuevo: `manage.py habilitar_soporte <RUT> --agregar especializaciones
  horario contacto privacidad` (LBW-07). Sin agente, esos tickets quedan sin asignar.
- Definir `SUPRESIONES_CLAVE` aparte y guardarla junto a los respaldos, nunca en la base. Sin ella se deriva de
  `SECRET_KEY`. Hoy no figura en CONFIGURACION_PRODUCCION.md.
- Programar `exportar_supresiones RUTA` a diario, con el archivo fuera de la base (LBW-13; falta decidir donde, D3).
  Tras restaurar cualquier respaldo: `reaplicar_supresiones --archivo RUTA` antes de reabrir el servicio.
- Confirmar que Railway agrega la IP del cliente al final de `X-Forwarded-For` (S4-02, LBW-08).
- Respaldos automaticos y una restauracion probada (LBW-14). La politica de privacidad debe decir que los
  respaldos conservan los documentos durante su retencion.

## Despues de ese despliegue
- 9b-3: quitar `titulo_archivo` (alumnos/models/usuarios.py) y actualizar `usabilidad/verificar_google_titulo.py`.
  Solo despues de correr `pasar_titulos_a_base` en produccion. Sin ticket todavia.

## Seguridad y calidad (detalle en el backlog)
- LBW-03 DEBUG seguro en Railway, LBW-04 versiones fijas, LBW-05 gunicorn, LBW-06 CI, LBW-10 Dependabot,
  LBW-11 y LBW-21 escape en el JS, LBW-12 suite en paralelo, LBW-22 a LBW-26 deuda tecnica.
- Revision visual en navegador de todos los flujos de apoderados (LBW-15).
- Posible CSS muerto en `pago/01_pago.css` (paneles de resumen y Webpay). Sin revisar, sin ticket.

## Pagos
- Transbank en produccion: checklist en CONCILIACION_Y_TRANSBANK_7_6.md, seccion 6 (LBW-09).
- Reporte de conciliacion (LBW-18) y retiros con dinero real: falta el contador y Webpay en produccion (LBW-19).
- Cuanto se guardan los registros de pago: contador y abogada (LBW-20, D2).

## Menores y legal
- **No habilitar menores reales** hasta la revision juridica (LBW-02, D1): declaracion de facultad, revocacion,
  transicion a los 18, aviso de documentos y declaraciones v2. Y definir quien verifica certificados y como.
- Fuera de desarrollo: responsable del tratamiento, proveedores reales, respaldos, correo
  de derechos y plazos contables. Cuanto se conserva al seudonimizar una cuenta: con asesoria legal.

## En espera (solo si hace falta)
- Sala de Jitsi privada con JWT: hoy es la sala publica `meet.jit.si` (LBW-28, D4).
- Tope de reintentos para apoderados rechazados, si aparece abuso. Invitacion del adolescente tambien para el
  tutor legal (hoy solo madre o padre; cambia textos legales). Observaciones del profesor en una futura descarga
  de datos del alumno. Historial de personas que entran por dia (hoy solo la tarjeta de hoy). Ver D9.

## Notas vigentes
- Si cambia `SECRET_KEY`, lo cifrado con `alumnos/cifrado.py` sin clave propia (por ejemplo, las cuentas
  bancarias) deja de leerse, y cambian los nombres de las salas de Jitsi. Si cambia `DOCUMENTOS_CLAVE`, los
  documentos pendientes se piden de nuevo.
- Al crear un correo nuevo, mandarlo por `alumnos.correo.enviar` (no por `send_mail` directo).
- El enlace de cambio de cuenta bancaria exige sesion: si el profesor no la tiene, entra y vuelve a abrirlo.

## Limpieza local
- Sacar el repo de OneDrive y limpiar los worktrees huerfanos de `.git/worktrees` (LBW-29).
