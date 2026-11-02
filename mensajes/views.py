"""Enviar y abrir conversaciones desde el panel del profesor (paso C1b). Vuelven al panel."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from alumnos.decorators import profesor_required
from alumnos.models import Inscripcion, Profesor

from . import servicio
from .models import Conversacion


def _profesor(request):
    return get_object_or_404(Profesor, id_profesor=request.session.get('profesor_id'))


def _al_panel(conversacion):
    return redirect(f"{reverse('panel_profesor')}?c={conversacion.pk}")  # el panel abre el Buzon con ?c=


@require_POST
@profesor_required
def enviar_profesor(request, pk):
    conversacion = get_object_or_404(Conversacion.objects.select_related('profesor__user'),
                                     pk=pk, profesor=_profesor(request))  # solo las suyas
    try:
        servicio.enviar(conversacion.profesor.user, conversacion, request.POST.get('texto'))
    except ValidationError as e:
        messages.error(request, e.messages[0])
    return _al_panel(conversacion)


@require_POST
@profesor_required
def abrir_profesor(request, inscripcion_id):
    """\"Escribir al alumno\" desde una reserva de Mi Agenda."""
    profesor = _profesor(request)
    inscripcion = get_object_or_404(Inscripcion.objects.select_related('alumno__user'),
                                    pk=inscripcion_id, clase__profesor=profesor)
    try:
        conversacion = servicio.abrir_conversacion(inscripcion.alumno, profesor)
    except ValidationError as e:
        messages.error(request, e.messages[0])
        return redirect('panel_profesor')
    return _al_panel(conversacion)
