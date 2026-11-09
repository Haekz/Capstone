"""Vistas del alumno para ver los videos que su profesor le compartio. La logica esta en videos_compartidos.py."""

from django.views.decorators.http import require_GET

from . import videos_compartidos
from .decorators import alumno_required, alumno_required_json


@require_GET
@alumno_required_json
def videos_alumno(request):
    return videos_compartidos.lista_json(request.session['alumno_id'])


@require_GET
@alumno_required
def ver_video(request, video_id):
    return videos_compartidos.video_respuesta(request, request.session['alumno_id'], video_id)
