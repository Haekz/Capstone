"""Vistas del apoderado para ver los videos de su estudiante. La logica esta en alumnos/videos_compartidos.py.

El vinculo se valida igual que en el resto del portal del apoderado (_vinculo_o_404): un vinculo ajeno es 404.
El apoderado ve todos los videos de su estudiante, para revisarlos y habilitarlos si es menor.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from alumnos import videos_compartidos
from alumnos.decorators import apoderado_required

from .views import _vinculo_o_404


@require_GET
@apoderado_required
def videos_estudiante(request, id_vinculo):
    return videos_compartidos.lista_json(_vinculo_o_404(request, id_vinculo).alumno_id)


@require_GET
@apoderado_required
def ver_video_estudiante(request, id_vinculo, video_id):
    return videos_compartidos.video_respuesta(request, _vinculo_o_404(request, id_vinculo).alumno_id, video_id)


@require_POST
@apoderado_required
def habilitar_video_estudiante(request, id_vinculo, video_id):
    """Despues de revisarlo, el apoderado habilita (habilitar=1) o quita (0) un video para su estudiante menor."""
    habilitado = request.POST.get('habilitar') == '1'
    videos_compartidos.habilitar(_vinculo_o_404(request, id_vinculo).alumno_id, video_id, habilitado)
    return JsonResponse({'success': True, 'habilitado': habilitado})
