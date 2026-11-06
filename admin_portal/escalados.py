"""Casos que soporte escala al administrador (D5, revisada 05-nov): el admin decide, soporte ejecuta.

El admin ve el asunto, la categoria, el plazo y los motivos; no los documentos ni la
conversacion del ticket, que siguen siendo solo del agente asignado.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from alumnos.decorators import admin_required
from soporte.forms import IndicacionForm
from soporte.models import Escalamiento
from soporte.tickets import indicar
from soporte.views import TICKET_RELACIONADOS

RELACIONADOS = ('autor', 'indicado_por', *(f'ticket__{campo}' for campo in TICKET_RELACIONADOS))


@never_cache
@admin_required
def casos_escalados(request):
    al_admin = (Escalamiento.objects.filter(destino=Escalamiento.AL_ADMIN).select_related(*RELACIONADOS)
                .prefetch_related('ticket__escalamientos__autor'))  # el motivo del agente, si lo hubo
    return render(request, 'admin_portal/casos_escalados.html', {
        'pendientes': al_admin.filter(indicado__isnull=True),
        'respondidos': al_admin.filter(indicado__isnull=False).order_by('-indicado')[:20],
        'largo_maximo': IndicacionForm.base_fields['indicacion'].max_length,
    })


@require_POST
@admin_required
def indicar_escalado(request, pk):
    escalamiento = get_object_or_404(Escalamiento, pk=pk, destino=Escalamiento.AL_ADMIN)
    form = IndicacionForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors['indicacion'][0])
        return redirect('casos_escalados')
    try:
        indicar(escalamiento, request.user, form.cleaned_data['indicacion'])
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f'Indicación enviada a soporte (ticket #{escalamiento.ticket_id}).')
    return redirect('casos_escalados')
