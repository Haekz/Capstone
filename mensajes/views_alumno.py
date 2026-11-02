"""Enviar y abrir conversaciones desde el panel del alumno adulto (paso C1b-2).

Este panel no muestra los mensajes de Django, asi que un error vuelve en la sesion
(`mensajes_error`) y el Buzon lo muestra una sola vez.
"""

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from alumnos.decorators import alumno_required
from alumnos.models import Alumno, Profesor

from . import servicio
from .models import Conversacion

CLAVE_ERROR = 'mensajes_error'


def _alumno(request):
    return get_object_or_404(Alumno.objects.select_related('user'), id_alumno=request.session['alumno_id'])


def _al_panel(conversacion):
    return redirect(f"{reverse('alumno_pag1')}?c={conversacion.pk}")  # el panel abre el Buzon con ?c=


@require_POST
@alumno_required
def enviar_alumno(request, pk):
    alumno = _alumno(request)
    conversacion = get_object_or_404(Conversacion.objects.select_related('profesor__user'),
                                     pk=pk, alumno=alumno, cliente=alumno.user)  # solo las suyas
    try:
        servicio.enviar(alumno.user, conversacion, request.POST.get('texto'))
    except ValidationError as e:
        request.session[CLAVE_ERROR] = e.messages[0]
    return _al_panel(conversacion)


@require_POST
@alumno_required
def abrir_alumno(request, profesor_id):
    """\"Escribir\" a un profesor con quien tiene reserva o paquete, sin conversacion todavia."""
    profesor = get_object_or_404(Profesor, pk=profesor_id)
    try:
        conversacion = servicio.abrir_conversacion(_alumno(request), profesor)
    except ValidationError as e:
        request.session[CLAVE_ERROR] = e.messages[0]
        return redirect('alumno_pag1')
    return _al_panel(conversacion)
