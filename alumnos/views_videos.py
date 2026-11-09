"""Vistas del alumno para ver los videos que su profesor le compartio. La logica esta en videos_compartidos.py.

Si el alumno es menor, solo ve los que su apoderado ya reviso y habilito.
"""

from django.views.decorators.http import require_GET

from . import videos_compartidos
from .decorators import alumno_required, alumno_required_json
from .models import Alumno
from .utils import es_menor


def _alumno(request):
    """(id del alumno de la sesion, si es menor y por lo tanto solo ve lo que su apoderado habilito)."""
    alumno = Alumno.objects.select_related('user').get(pk=request.session['alumno_id'])
    return alumno.pk, es_menor(alumno.user)


@require_GET
@alumno_required_json
def videos_alumno(request):
    alumno_id, solo_habilitados = _alumno(request)
    return videos_compartidos.lista_json(alumno_id, solo_habilitados)


@require_GET
@alumno_required
def ver_video(request, video_id):
    alumno_id, solo_habilitados = _alumno(request)
    return videos_compartidos.video_respuesta(request, alumno_id, video_id, solo_habilitados)
