"""Vistas del profesor para su biblioteca de videos (agregado de videos, fase 1). La lógica está en videoteca.py.

Si MongoDB no está configurado o no responde, contestan {'disponible': False} y el panel lo avisa.
"""

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from alumnos.decorators import profesor_required_json
from comunidad import mongo

from . import entregas, videoteca

ERRORES_MONGO = mongo.ERRORES


def _no_disponible():
    return JsonResponse({'success': False, 'disponible': False,
                         'message': 'Los videos no están disponibles por ahora. Intenta más tarde.'})


@require_GET
@profesor_required_json
def videos_profesor(request):
    profesor_id = request.session['profesor_id']
    try:
        videos = videoteca.listar(profesor_id)
    except ERRORES_MONGO:
        return _no_disponible()
    return JsonResponse({'success': True, 'disponible': True, 'videos': videos,
                         'asignaturas': videoteca.materias(profesor_id),
                         'entregas': entregas.pendientes(profesor_id)})


@require_POST
@profesor_required_json
def subir_video(request):
    try:
        videoteca.subir(request.session['profesor_id'], request.POST.get('asignatura'),
                        request.POST.get('titulo'), request.FILES.get('archivo'))
    except ValidationError as e:
        return JsonResponse({'success': False, 'disponible': True, 'message': e.messages[0]})
    except ERRORES_MONGO:
        return _no_disponible()
    return JsonResponse({'success': True, 'disponible': True, 'message': 'Video publicado en tu biblioteca.'})


@require_POST
@profesor_required_json
def compartir_video(request):
    try:
        entregas.compartir(request.session['profesor_id'], request.POST.get('paquete'), request.POST.get('video'))
    except ValidationError as e:
        return JsonResponse({'success': False, 'disponible': True, 'message': e.messages[0]})
    except ERRORES_MONGO:
        return _no_disponible()
    return JsonResponse({'success': True, 'disponible': True, 'message': 'Video compartido con tu alumno.'})


@require_POST
@profesor_required_json
def eliminar_video(request, video_id):
    try:
        borrado = videoteca.eliminar(request.session['profesor_id'], video_id)
    except ERRORES_MONGO:
        return _no_disponible()
    if not borrado:
        return JsonResponse({'success': False, 'disponible': True, 'message': 'No encontramos ese video en tu biblioteca.'})
    return JsonResponse({'success': True, 'disponible': True, 'message': 'Video eliminado.'})
