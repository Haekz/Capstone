"""Vista del profesor para subir una especializacion (fase 2). La logica esta en especializaciones.py."""

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from alumnos.decorators import profesor_required_json
from alumnos.models import Profesor

from . import especializaciones


@require_POST
@profesor_required_json
def subir_especializacion(request):
    profesor = get_object_or_404(Profesor, id_profesor=request.session['profesor_id'])
    try:
        especializaciones.subir(profesor, request.POST.get('nombre'), request.FILES.get('archivo'),
                                request.POST.getlist('asignaturas'), request.POST.get('otra_asignatura'))
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': e.messages[0]})
    return JsonResponse({
        'success': True,
        'message': 'Especialización recibida. Nuestro equipo de soporte la revisará; '
                   'verás el resultado en esta sección.',
    })
