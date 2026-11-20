"""Videos que el profesor le compartió a un alumno (agregado de videos, fase 3b): listarlos y reproducirlos.

Lo usan el alumno y el apoderado (de su estudiante); cada uno valida primero su propio acceso y luego llama aqui.
Regla unica: se ve un video solo si esta compartido con ESE alumno y su paquete sigue vigente. Si no, 404 (no se
revela si el video existe). Si el alumno es menor, ademas su apoderado tiene que haberlo habilitado (solo_habilitados).
Se entrega por partes con soporte de Range: es lo que permite adelantar y retroceder.

Soporte (fase 5e) ve los videos que nombra un reclamo de Videos de apoyo: del_ticket() decide cuales, y la vista de
soporte entrega el archivo con archivo_respuesta(), sin las reglas del alumno.
"""

import re

from django.http import Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.utils import timezone

from comunidad import mongo
from soporte.models import Ticket
from user_profesor import videoteca

from .models import Alumno, PaqueteClases
from .models.videos import VideoCompartido

TROZO = 256 * 1024
RANGO = re.compile(r'^bytes=(\d*)-(\d*)$')
ID_VIDEO = re.compile(r'\b[0-9a-f]{24}\b')


def _compartidos(alumno_id, solo_habilitados=False):
    compartidos = VideoCompartido.objects.entregados().filter(
        paquete__in=PaqueteClases.objects.vigentes().filter(alumno_id=alumno_id))
    return compartidos.filter(habilitado_menor__isnull=False) if solo_habilitados else compartidos


def listar(alumno_id, solo_habilitados=False):
    """Sus videos vigentes, del mas nuevo al mas antiguo. Los que el profesor ya borro no aparecen."""
    compartidos = list(_compartidos(alumno_id, solo_habilitados).select_related('paquete__profesor__user'))
    videos = videoteca.por_id([c.video_id for c in compartidos])
    return [{
        'id': c.video_id, 'titulo': videos[c.video_id]['titulo'], 'asignatura': videos[c.video_id]['asignatura'],
        'duracion': videos[c.video_id]['duracion'], 'profesor': c.paquete.profesor.nombre if c.paquete.profesor else '',
        'habilitado': c.habilitado_menor is not None,
    } for c in compartidos if c.video_id in videos]


def habilitar(alumno_id, video_id, habilitado):
    """El apoderado habilita (o quita) un video de su estudiante menor. Http404 si no es suyo o no esta vigente."""
    if not _compartidos(alumno_id).filter(video_id=video_id).update(
            habilitado_menor=timezone.now() if habilitado else None):
        raise Http404


def _rango(cabecera, total):
    """(desde, hasta) de un solo tramo; None si no hay Range o esta mal escrito (RFC 7233: se ignora y va completo).

    ValueError si el tramo cae fuera del archivo (se responde 416).
    """
    pedido = RANGO.match(cabecera or '')
    if not pedido or not any(pedido.groups()):
        return None
    inicio, fin = pedido.groups()
    if not inicio:  # bytes=-N: los ultimos N
        if int(fin) == 0:
            raise ValueError
        return max(total - int(fin), 0), total - 1
    desde = int(inicio)
    if fin and int(fin) < desde:
        return None
    if desde >= total:
        raise ValueError
    return desde, min(int(fin), total - 1) if fin else total - 1


def _trozos(lector, desde, hasta):
    try:
        lector.seek(desde)
        restante = hasta - desde + 1
        while restante > 0:
            dato = lector.read(min(TROZO, restante))
            if not dato:
                break
            restante -= len(dato)
            yield dato
    finally:
        lector.close()


def transmitir(request, alumno_id, video_id, solo_habilitados=False):
    """El video (completo o el tramo pedido) si es del alumno y esta vigente; Http404 si no."""
    if not _compartidos(alumno_id, solo_habilitados).filter(video_id=video_id).exists():
        raise Http404
    return _archivo(request, video_id)


def _archivo(request, video_id):
    """El archivo, completo o el tramo pedido. Quien llama ya valido el acceso."""
    ficha = videoteca.ficha(video_id)
    if not ficha:
        raise Http404
    total = ficha['length']
    try:
        tramo = _rango(request.headers.get('Range'), total)
    except ValueError:
        respuesta = HttpResponse(status=416)
        respuesta['Content-Range'] = f'bytes */{total}'
        return respuesta
    desde, hasta = tramo or (0, total - 1)
    respuesta = StreamingHttpResponse(_trozos(videoteca.abrir(ficha['_id']), desde, hasta),
                                      status=206 if tramo else 200, content_type='video/mp4')
    respuesta['Content-Length'] = hasta - desde + 1
    respuesta['Accept-Ranges'] = 'bytes'
    respuesta['Cache-Control'] = 'private'
    if tramo:
        respuesta['Content-Range'] = f'bytes {desde}-{hasta}/{total}'
    return respuesta


def lista_json(alumno_id, solo_habilitados=False):
    """Respuesta JSON de la lista; si Mongo no esta disponible lo avisa en vez de caerse.

    por_revisar: los que el menor todavia no puede ver porque su apoderado no los habilito.
    """
    por_revisar = _compartidos(alumno_id).filter(habilitado_menor__isnull=True).count() if solo_habilitados else 0
    try:
        return JsonResponse({'success': True, 'disponible': True, 'videos': listar(alumno_id, solo_habilitados),
                             'por_revisar': por_revisar})
    except mongo.ERRORES:
        return JsonResponse({'success': False, 'disponible': False,
                             'message': 'Los videos no están disponibles por ahora. Intenta más tarde.'})


def video_respuesta(request, alumno_id, video_id, solo_habilitados=False):
    """transmitir() con Mongo caido convertido en 503."""
    try:
        return transmitir(request, alumno_id, video_id, solo_habilitados)
    except mongo.ERRORES:
        return HttpResponse(status=503)


def alumno_id_del_ticket(ticket):
    """El estudiante de un reclamo de Videos de apoyo: el que indico el apoderado o, si no, el alumno que lo abrio.
    None si no es un ticket de Videos o no hay a quien se refiera."""
    if ticket.categoria != Ticket.VIDEOS:
        return None
    return (ticket.estudiante_id
            or Alumno.objects.filter(user_id=ticket.autor_id).values_list('pk', flat=True).first())


def del_ticket(ticket):
    """Videos que nombra un reclamo de Videos de apoyo y que de verdad se compartieron con su estudiante (fase 5e).

    El texto lo escribe el usuario: un id que no se le compartio a ese estudiante se ignora. Incluye los ya retirados
    (para mostrarlo).
    """
    alumno_id = alumno_id_del_ticket(ticket)
    if alumno_id is None:
        return VideoCompartido.objects.none()
    return (VideoCompartido.objects
            .filter(paquete__alumno_id=alumno_id, video_id__in=set(ID_VIDEO.findall(ticket.descripcion)))
            .select_related('paquete__alumno__user', 'paquete__profesor__user'))


def archivo_respuesta(request, video_id):
    """Para soporte, ya autorizado por su ticket: el archivo sin las reglas del alumno. Mongo caido = 503."""
    try:
        return _archivo(request, video_id)
    except mongo.ERRORES:
        return HttpResponse(status=503)
