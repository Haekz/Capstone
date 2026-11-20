"""Enviar y abrir conversaciones desde el panel del profesor (paso C1b). Vuelven al panel."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from alumnos.decorators import profesor_required
from alumnos.models import Inscripcion, Profesor
from alumnos.utils import es_menor

from . import servicio
from .models import Conversacion


def _profesor(request):
    return get_object_or_404(Profesor, id_profesor=request.session.get('profesor_id'))


def _al_panel(conversacion):
    return redirect(f"{reverse('panel_profesor')}?c={conversacion.pk}")  # el panel abre el Buzon con ?c=


@require_POST
@profesor_required
def enviar_profesor(request, pk):
    conversacion = get_object_or_404(Conversacion.objects.visibles().select_related('profesor__user'),
                                     pk=pk, profesor=_profesor(request))  # solo las suyas
    try:
        servicio.enviar(conversacion.profesor.user, conversacion, request.POST.get('texto'))
    except ValidationError as e:
        messages.error(request, e.messages[0])
    return _al_panel(conversacion)


@require_POST
@profesor_required
def abrir_profesor(request, inscripcion_id):
    """\"Escribir\" desde una reserva de Mi Agenda: al alumno adulto, o a los apoderados de un menor."""
    profesor = _profesor(request)
    inscripcion = get_object_or_404(Inscripcion.objects.select_related('alumno__user'),
                                    pk=inscripcion_id, clase__profesor=profesor)
    alumno = inscripcion.alumno
    try:
        if es_menor(alumno.user):
            conversaciones = servicio.abrir_conversaciones_con_apoderados(alumno, profesor)
        else:
            conversaciones = [servicio.abrir_conversacion(alumno, profesor)]
    except ValidationError as e:
        messages.error(request, e.messages[0])
        return redirect('panel_profesor')
    if not conversaciones:
        messages.error(request, 'Este estudiante no tiene un apoderado con vínculo activo.')
        return redirect('panel_profesor')
    if len(conversaciones) > 1:
        messages.info(request, 'Este estudiante tiene más de un apoderado: escríbele a cada uno desde tu Buzón.')
    return _al_panel(conversaciones[0])
