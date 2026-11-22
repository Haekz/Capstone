"""Clase extra: el alumno propone un dia y hora fuera del horario del profesor y este decide.

Pedirla exige lo mismo que reservar (paquete vigente con ese profesor; un menor, a traves de su apoderado)
y que la hora quede de verdad fuera de lo que el profesor ya ofrece. El modelo y el plazo: models/clase_extra.py.
"""

from datetime import datetime, time

from django.db import IntegrityError, transaction
from django.utils import timezone

from agenda import avisos_alumno
from agenda.models import HorarioSemanal

from . import avisos_profesor
from .exceptions import InscripcionError, SinClasesDisponiblesError, SolicitudExtraError
from .models import Inscripcion, SesionClase, SolicitudClaseExtra
from .sala_virtual import es_profesor_habilitado_de
from .services import InscripcionService, _paquete_con_clases, exigir_mayor_de_edad, paquetes_vigentes

MAXIMO_MENSAJE = 500
HORAS_DEL_DIA = range(8, 22)  # las que ofrece la pantalla: de 08:00 a 21:00, en punto (la ultima termina a las 22)
PLAZO_VENCIDO = 'Ya pasó el plazo para responder.'
NADIE_RESPONDIO = 'Nadie respondió a tiempo.'


def _dentro_del_horario(profesor, inicio, fin):
    """La hora cae en una franja semanal del profesor, o ya hay un bloque libre suyo que se cruza.

    Una franja cuenta aunque todavia no tenga bloques (las proximas 4 semanas son las unicas que se crean).
    """
    local = timezone.localtime(inicio)
    en_una_franja = HorarioSemanal.objects.filter(
        profesor=profesor, dia_semana=local.weekday(), hora_inicio__lte=local.time(), hora_fin__gt=local.time(),
    ).exists()
    return en_una_franja or SesionClase.objects.disponibles().filter(
        clase__profesor=profesor, fecha_hora_inicio__lt=fin, fecha_hora_fin__gt=inicio,
    ).exists()


def _exigir_alumno_y_profesor(alumno, profesor):
    """Lo que no depende de la hora: si falla, no se puede pedir ninguna."""
    exigir_mayor_de_edad(alumno)
    if not profesor.puede_hacer_clases:
        raise SolicitudExtraError('Este profesor aún no tiene su título validado.')


def _exigir_la_hora(profesor, inicio, ahora):
    """Las reglas de la hora que no necesitan bloquear nada, de la mas barata a la que consulta la base."""
    local = timezone.localtime(inicio)
    if local.minute or local.second or local.microsecond:
        raise SolicitudExtraError('Elige una hora en punto (por ejemplo 15:00): cada clase dura 60 minutos.')
    anticipacion = SolicitudClaseExtra.ANTICIPACION_MINIMA
    if inicio - ahora < anticipacion:
        raise SolicitudExtraError(
            f'Pide la clase con al menos {int(anticipacion.total_seconds() // 3600)} horas de anticipación.')
    fin = inicio + SolicitudClaseExtra.DURACION
    if Inscripcion.objects.que_se_cruzan(profesor, inicio, fin).exists():
        raise SolicitudExtraError('El profesor ya tiene una clase a esa hora. Elige otro horario.')
    if _dentro_del_horario(profesor, inicio, fin):
        raise SolicitudExtraError(
            'Esa hora ya es parte de los horarios del profesor: reserva uno de sus bloques disponibles.')


def _vence_el_paquete(alumno, profesor, ahora):
    """Hasta cuando puede empezar una clase con ese profesor: el paquete con clases que vence mas tarde.

    Lo mismo que exige la reserva (`_paquete_con_clases`), pero solo mirando: no bloquea.
    """
    vencimientos = [p.fecha_fin for p in paquetes_vigentes(alumno, profesor, ahora) if p.clases_disponibles]
    if not vencimientos:
        raise SinClasesDisponiblesError(
            f'No tienes clases disponibles con {profesor.nombre}. Compra un paquete en Planes.')
    return max(vencimientos)


def horas_para_pedir(alumno, clase, fecha, ahora=None):
    """Las horas de `fecha` (dia local) para una clase extra: [(inicio, motivo)], motivo '' si se puede pedir.

    Mismas reglas que solicitar(), sin bloquear nada (solo muestra). Si no se puede pedir ninguna (menor de
    edad, profesor sin titulo, sin clases con ese profesor) lanza el error, con un mensaje para el alumno.
    """
    ahora = ahora or timezone.now()
    profesor = clase.profesor
    _exigir_alumno_y_profesor(alumno, profesor)
    vence = _vence_el_paquete(alumno, profesor, ahora)
    horas = []
    for hora in HORAS_DEL_DIA:
        inicio = timezone.make_aware(datetime.combine(fecha, time(hora)))
        try:
            _exigir_la_hora(profesor, inicio, ahora)
            if inicio > vence:
                raise SolicitudExtraError('Tu paquete con este profesor vence antes de esa hora.')
            horas.append((inicio, ''))
        except SolicitudExtraError as exc:
            horas.append((inicio, exc.messages[0]))
    return horas


def solicitar(alumno, clase, inicio, mensaje='', ahora=None):
    """Registra el pedido y le avisa al profesor. Devuelve la solicitud pendiente.

    Lanza SolicitudExtraError (o los errores de reserva: menor de edad, sin clases en un paquete) con un
    mensaje que se le puede mostrar tal cual al alumno.
    """
    ahora = ahora or timezone.now()
    _exigir_alumno_y_profesor(alumno, clase.profesor)
    _exigir_la_hora(clase.profesor, inicio, ahora)
    repetida = SolicitudExtraError('Ya pediste esa clase extra y el profesor aún no responde.')
    with transaction.atomic():
        _paquete_con_clases(alumno, clase.profesor, inicio)  # solo comprueba: el cupo se gasta al aceptar
        try:
            with transaction.atomic():  # la restriccion unica de la base detecta el pedido repetido
                solicitud = SolicitudClaseExtra.objects.create(
                    alumno=alumno, clase=clase, fecha_hora_inicio=inicio, mensaje=mensaje.strip()[:MAXIMO_MENSAJE],
                    vence_el=SolicitudClaseExtra.plazo(ahora, inicio),
                )
        except IntegrityError as exc:
            raise repetida from exc
        transaction.on_commit(lambda: avisos_profesor.clase_extra_solicitada(solicitud))
    return solicitud


def _bloquear(pk):
    """La solicitud con su fila bloqueada: dos respuestas a la vez se atienden en fila y la segunda ve a la primera."""
    return (SolicitudClaseExtra.objects.select_for_update(of=('self',))
            .select_related('alumno__user', 'clase__asignatura', 'clase__profesor__user').get(pk=pk))


def _cerrar(solicitud, estado, ahora, motivo=''):
    solicitud.estado, solicitud.fecha_resolucion, solicitud.motivo_rechazo = estado, ahora, motivo
    solicitud.save(update_fields=['estado', 'fecha_resolucion', 'motivo_rechazo', 'sesion'])


def _vencer(solicitud, ahora, motivo):
    _cerrar(solicitud, SolicitudClaseExtra.VENCIDA, ahora)
    transaction.on_commit(lambda: avisos_alumno.clase_extra_vencida(solicitud, motivo))


def _responder(solicitud, usuario, ahora, resolver):
    """Resuelve la solicitud con `resolver(solicitud, ahora)`, solo si responde el profesor de la clase y sigue pendiente.

    Si ya paso el plazo, o `resolver` choca con una regla de reserva (el paquete se agoto o vencio, el profesor
    ya tomo esa hora), la solicitud queda **vencida** (eso se guarda) y se lanza el motivo. Lo que `resolver` alcanzo a
    crear se deshace: va dentro de su propio punto de guardado.
    """
    ahora = ahora or timezone.now()
    with transaction.atomic():
        solicitud = _bloquear(solicitud.pk)
        if not es_profesor_habilitado_de(solicitud.clase, usuario):
            raise SolicitudExtraError('Solo el profesor de esta clase puede responder la solicitud.')
        if solicitud.estado != SolicitudClaseExtra.PENDIENTE:
            raise SolicitudExtraError(f'Esta solicitud ya está {solicitud.get_estado_display().lower()}.')
        problema = PLAZO_VENCIDO if solicitud.vence_el <= ahora else None
        if problema is None:
            try:
                with transaction.atomic():
                    resolver(solicitud, ahora)
            except InscripcionError as exc:
                problema = exc.messages[0]
        if problema is not None:
            _vencer(solicitud, ahora, problema)
    if problema is not None:  # fuera de la transaccion: lanzarlo adentro habria deshecho el cierre
        raise SolicitudExtraError(f'{problema} La solicitud quedó vencida.')
    return solicitud


def _reservar(solicitud, ahora):
    """Crea la sesion de 60 min y reserva al alumno con el servicio de siempre (cupo, profesor libre y paquete)."""
    sesion = SesionClase.objects.create(
        clase=solicitud.clase, fecha_hora_inicio=solicitud.fecha_hora_inicio,
        fecha_hora_fin=solicitud.fecha_hora_fin, cupo_maximo=1,
    )
    InscripcionService.inscribir_alumno_en_sesion(solicitud.alumno, sesion.pk, avisar_alumno=False)
    solicitud.sesion = sesion
    _cerrar(solicitud, SolicitudClaseExtra.ACEPTADA, ahora)
    transaction.on_commit(lambda: avisos_alumno.clase_extra_aceptada(solicitud))


def aceptar(solicitud, usuario, ahora=None):
    """El profesor acepta: queda la clase reservada, con una clase menos en el paquete del alumno."""
    return _responder(solicitud, usuario, ahora, _reservar)


def rechazar(solicitud, usuario, motivo='', ahora=None):
    """El profesor la rechaza, con un mensaje opcional que ve el alumno."""
    def rechazada(pendiente, momento):
        _cerrar(pendiente, SolicitudClaseExtra.RECHAZADA, momento, motivo.strip()[:MAXIMO_MENSAJE])
        transaction.on_commit(lambda: avisos_alumno.clase_extra_rechazada(pendiente))
    return _responder(solicitud, usuario, ahora, rechazada)


def vencer_las_vencidas(ahora=None):
    """Cierra las pendientes cuyo plazo ya pasó y le avisa al alumno. Devuelve cuántas cerró (se puede repetir)."""
    ahora = ahora or timezone.now()
    por_cerrar = list(SolicitudClaseExtra.objects.filter(
        estado=SolicitudClaseExtra.PENDIENTE, vence_el__lte=ahora).values_list('pk', flat=True))
    cerradas = 0
    for pk in por_cerrar:
        with transaction.atomic():
            solicitud = _bloquear(pk)
            if solicitud.estado == SolicitudClaseExtra.PENDIENTE:  # el profesor pudo responder mientras tanto
                _vencer(solicitud, ahora, NADIE_RESPONDIO)
                cerradas += 1
    return cerradas
