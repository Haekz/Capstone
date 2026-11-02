"""Mensajes del apoderado con los profesores de su estudiante menor (paso C2a).

Cada apoderado con vinculo vigente tiene su propia conversacion con el profesor. Una conversacion
de un vinculo terminado se puede leer, pero no escribir (mensajes/servicio.es_solo_lectura).
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from alumnos.decorators import apoderado_required
from alumnos.models import Profesor
from alumnos.roles import APODERADO
from apoderados.models import Apoderado
from apoderados.permisos import vinculo_contratable

from . import panel, servicio
from .models import Conversacion


def _apoderado(request):
    return get_object_or_404(Apoderado.objects.select_related('user'),
                             id_apoderado=request.session[APODERADO.clave_sesion])


def _al_buzon(conversacion=None):
    destino = reverse('mensajes_apoderado')
    return redirect(f'{destino}?c={conversacion.pk}' if conversacion else destino)


@never_cache
@apoderado_required
def buzon_apoderado(request):
    apoderado = _apoderado(request)
    return render(request, 'mensajes/buzon_apoderado.html',
                  {'apoderado': apoderado, **panel.contexto_apoderado(apoderado, request.GET.get('c'))})


@require_POST
@apoderado_required
def enviar_apoderado(request, pk):
    apoderado = _apoderado(request)
    conversacion = get_object_or_404(Conversacion.objects.visibles().select_related('alumno__user', 'profesor__user'),
                                     pk=pk, cliente=apoderado.user)  # solo las suyas
    try:
        servicio.enviar(apoderado.user, conversacion, request.POST.get('texto'))
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return _al_buzon(conversacion)


@require_POST
@apoderado_required
def abrir_apoderado(request, id_vinculo, profesor_id):
    """\"Escribir\" a un profesor con quien el estudiante tiene reserva o paquete, sin conversacion todavia."""
    vinculo = vinculo_contratable(request, id_vinculo)
    if vinculo is None:
        raise Http404
    try:
        conversacion = servicio.abrir_conversacion_de_apoderado(vinculo, get_object_or_404(Profesor, pk=profesor_id))
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return _al_buzon()
    return _al_buzon(conversacion)
