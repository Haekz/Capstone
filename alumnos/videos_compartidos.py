"""Videos que el profesor le compartió a un alumno (agregado de videos, fase 3b): listarlos y reproducirlos.

Lo usan el alumno y el apoderado (de su estudiante); cada uno valida primero su propio acceso y luego llama aqui.
Regla unica: se ve un video solo si esta compartido con ESE alumno y su paquete sigue vigente. Si no, 404 (no se
revela si el video existe). Si el alumno es menor, ademas su apoderado tiene que haberlo habilitado (solo_habilitados).
Con acceso, se redirige a un enlace firmado de Cloudflare R2 que vence (user_profesor/almacen_videos.py): R2 entrega el
archivo y resuelve Range (adelantar y retroceder). Cada vez que se abre se revisa el acceso y se firma uno nuevo.

Soporte (fase 5e) ve los videos que nombra un reclamo de Videos de apoyo: del_ticket() decide cuales, y la vista de
soporte entrega el archivo con archivo_respuesta(), sin las reglas del alumno.
"""

import re

from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.utils import timezone

from soporte.models import Ticket
from user_profesor import videoteca

from .models import Alumno, PaqueteClases
from .models.videos import VideoCompartido

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


def transmitir(alumno_id, video_id, solo_habilitados=False):
    """Redireccion al video si es del alumno y esta vigente; Http404 si no."""
    if not _compartidos(alumno_id, solo_habilitados).filter(video_id=video_id).exists():
        raise Http404
    return _archivo(video_id)


def _archivo(video_id):
    """Redireccion al enlace firmado del archivo en R2. Quien llama ya valido el acceso."""
    ficha = videoteca.ficha(video_id)
    if not ficha:
        raise Http404
    videoteca.registrar_vista(ficha.pk)  # actividad: si nadie lo abre en 30 dias, se borra (limpieza_videos.py)
    respuesta = HttpResponseRedirect(videoteca.enlace(ficha))
    respuesta['Cache-Control'] = 'no-store'  # que el navegador vuelva a pasar por aqui: se revisa el acceso cada vez
    return respuesta


def lista_json(alumno_id, solo_habilitados=False):
    """Respuesta JSON de la lista; si los videos no estan disponibles (R2) lo avisa en vez de caerse.

    por_revisar: los que el menor todavia no puede ver porque su apoderado no los habilito.
    """
    por_revisar = _compartidos(alumno_id).filter(habilitado_menor__isnull=True).count() if solo_habilitados else 0
    try:
        return JsonResponse({'success': True, 'disponible': True, 'videos': listar(alumno_id, solo_habilitados),
                             'por_revisar': por_revisar})
    except videoteca.ERRORES:
        return JsonResponse({'success': False, 'disponible': False,
                             'message': 'Los videos no están disponibles por ahora. Intenta más tarde.'})


def video_respuesta(alumno_id, video_id, solo_habilitados=False):
    """transmitir() con los videos no disponibles (R2) convertido en 503."""
    try:
        return transmitir(alumno_id, video_id, solo_habilitados)
    except videoteca.ERRORES:
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


def archivo_respuesta(video_id):
    """Para soporte, ya autorizado por su ticket: el archivo sin las reglas del alumno. Sin videos disponibles = 503."""
    try:
        return _archivo(video_id)
    except videoteca.ERRORES:
        return HttpResponse(status=503)
