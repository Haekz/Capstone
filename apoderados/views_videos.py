"""Vistas del apoderado para ver los videos de su estudiante. La logica esta en alumnos/videos_compartidos.py.

El vinculo se valida igual que en el resto del portal del apoderado (_vinculo_o_404): un vinculo ajeno es 404.
"""

from django.views.decorators.http import require_GET

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
