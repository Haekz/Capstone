"""Escalar un caso grave (D5, revisada 05-nov): el agente al lider; el lider a un administrador.

El motivo es obligatorio. La misma pantalla muestra el historial del ticket, con la
indicacion del administrador cuando llega.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from alumnos.decorators import soporte_required

from .forms import EscalarForm
from .models import Escalamiento, Ticket
from .permisos import agente_en_sesion, tickets_del_agente
from .tickets import escalar
from .views import TICKET_RELACIONADOS


@never_cache
@soporte_required
def escalar_ticket(request, id_ticket):
    """El agente, sus tickets; el lider, cualquier ticket abierto (los supervisa todos)."""
    agente = agente_en_sesion(request)
    visibles = Ticket.objects.filter(estado=Ticket.ABIERTO) if agente.es_lider else tickets_del_agente(request)
    ticket = get_object_or_404(visibles.select_related(*TICKET_RELACIONADOS), pk=id_ticket)
    historial = list(ticket.escalamientos.select_related('autor', 'indicado_por'))
    pendiente = any(e.pendiente for e in historial)
    form = None if pendiente else EscalarForm(request.POST or None)
    if form is not None and request.method == 'POST' and form.is_valid():
        try:
            escalamiento = escalar(ticket, agente, form.cleaned_data['motivo'])
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, f'Ticket #{ticket.pk} escalado '
                             + ('a los administradores.' if escalamiento.destino == Escalamiento.AL_ADMIN
                                else f'a {ticket.asignado.nombre}.'))
            return redirect('panel_soporte')
    return render(request, 'soporte/escalar.html', {
        'ticket': ticket, 'form': form, 'historial': historial, 'pendiente': pendiente,
        'destino': 'un administrador' if agente.es_lider else 'el líder de soporte',
    })
