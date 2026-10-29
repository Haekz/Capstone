"""Panel del equipo de soporte: tickets propios y, para el lider, todos los abiertos.

Las revisiones en si (documentos y decisiones) siguen en su pantalla de siempre
(apoderados_revision, titulos_adm), filtradas por los tickets del agente.
"""

from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from alumnos.decorators import soporte_required

from .forms import ReasignarForm
from .models import AgenteSoporte, Asignacion, Ticket
from .permisos import agente_en_sesion, lider_required, tickets_del_agente
from .tickets import agentes_habilitados, reasignar

TICKET_RELACIONADOS = ('asignado__user', 'apoderado__user', 'vinculo__apoderado__user',
                       'vinculo__alumno__user', 'profesor__user')


def _supervision():
    """Lo que solo ve el lider: todos los abiertos, la carga del equipo y las asignaciones."""
    candidatos = {categoria: list(agentes_habilitados(categoria).select_related('user'))
                  for categoria, _ in Ticket.CATEGORIAS}
    abiertos = list(Ticket.objects.filter(estado=Ticket.ABIERTO).select_related(*TICKET_RELACIONADOS))
    for ticket in abiertos:
        ticket.candidatos = candidatos[ticket.categoria]
    return {
        'abiertos': abiertos,
        'equipo': (AgenteSoporte.objects.select_related('user').prefetch_related('habilitaciones')
                   .annotate(carga=Count('tickets', filter=Q(tickets__estado=Ticket.ABIERTO)))),
        'asignaciones': Asignacion.objects.select_related('agente__user', 'autor', 'ticket')[:50],
    }


@never_cache
@soporte_required
def panel(request):
    agente = agente_en_sesion(request)
    contexto = {'agente': agente, 'mis_tickets': tickets_del_agente(request).select_related(*TICKET_RELACIONADOS)}
    if agente.es_lider:
        contexto.update(_supervision())
    return render(request, 'soporte/panel.html', contexto)


@require_POST
@lider_required
def reasignar_ticket(request, id_ticket):
    ticket = get_object_or_404(Ticket, pk=id_ticket)
    form = ReasignarForm(request.POST)
    if not form.is_valid():
        messages.error(request, next(iter(form.errors.values()))[0])
        return redirect('panel_soporte')
    agente = form.cleaned_data['agente']
    try:
        reasignar(ticket, agente, request.user)
        messages.success(request, f'Ticket #{ticket.pk} asignado a {agente.nombre}.')
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return redirect('panel_soporte')


def logout_soporte(request):
    auth_logout(request)
    return redirect('home')
