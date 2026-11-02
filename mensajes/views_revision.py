"""Revision de las conversaciones reportadas por el lider de soporte (paso C1f-2).

Solo el lider. Se ven nombres de pila y fechas; el contenido solo se lee desde el ticket (lo que deja
registro de quien lo abre). La decision y sus reglas viven en revision.py.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from soporte.permisos import agente_en_sesion, lider_required

from . import revision
from .forms import ConservarForm
from .models import Conversacion, DecisionRetencion


@never_cache
@lider_required
def revision_lista(request):
    hoy = timezone.localdate()
    pendientes = list(revision.pendientes(hoy).select_related('alumno__user', 'profesor__user'))
    for conversacion in pendientes:
        conversacion.desde = revision.pendiente_desde(conversacion)
    conservadas = list(revision.conservadas(hoy).select_related('alumno__user', 'profesor__user'))
    motivos = dict(DecisionRetencion.MOTIVOS)
    for conversacion in conservadas:
        conversacion.motivo = motivos.get(conversacion.ultima_motivo, '')
    return render(request, 'mensajes/soporte_revision.html', {
        'agente': agente_en_sesion(request), 'pendientes': pendientes, 'conservadas': conservadas,
    })


def _decidir(request, agente, conversacion, hoy):
    """Aplica la decision enviada. Devuelve el formulario con errores si hay que corregirlo, o None."""
    try:
        if request.POST.get('accion') == 'liberar':
            revision.liberar(agente, conversacion, hoy)
            messages.success(request, 'Conversación liberada: vuelve a la regla de borrado a los 90 días sin mensajes.')
            return None
        form = ConservarForm(request.POST)
        if form.is_valid():
            revision.conservar(agente, conversacion, **form.cleaned_data, hoy=hoy)
            messages.success(request, 'Retención excepcional registrada. Se vuelve a revisar en 6 meses.')
            return None
        return form
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return None


@never_cache
@lider_required
def revision_detalle(request, pk):
    agente, hoy = agente_en_sesion(request), timezone.localdate()
    conversacion = get_object_or_404(Conversacion.objects.reportadas().select_related('alumno__user', 'profesor__user'), pk=pk)
    espera = revision.pendientes(hoy).filter(pk=pk).exists()
    form = ConservarForm()
    if request.method == 'POST':
        form = _decidir(request, agente, conversacion, hoy)
        if form is None:
            return redirect('mensajes_revision')
        espera = True  # tenia errores: sigue esperando
    return render(request, 'mensajes/soporte_revision_detalle.html', {
        'agente': agente, 'conversacion': conversacion, 'espera': espera, 'form': form,
        'reportes': conversacion.reportes.select_related('ticket').order_by('-creado'),
        'decisiones': conversacion.decisiones.select_related('decidida_por__user'),
    })
