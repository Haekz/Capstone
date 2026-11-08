"""Soporte cambia el horario del profesor desde su ticket de Horario (fase 7, commit 2, decidido 07-nov).

Solo el agente que tiene el ticket asignado (el lider, reasignandoselo antes), con las mismas reglas que el
profesor (agenda/franjas.py). Cada cambio queda como mensaje de soporte en el ticket: es el registro (quien, que y
cuando) y el aviso al profesor (soporte/tickets.agregar_mensaje). Si el mensaje falla, el cambio no se guarda.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from alumnos.decorators import soporte_required
from alumnos.models import Profesor
from soporte.models import Ticket
from soporte.permisos import tickets_del_agente
from soporte.tickets import agregar_mensaje

from . import bloques, franjas
from .models import HorarioSemanal


def _del_ticket(request, id_ticket):
    """El ticket de Horario abierto asignado al agente en sesion, y el profesor que lo abrio. Si no, 404."""
    ticket = get_object_or_404(tickets_del_agente(request), pk=id_ticket, categoria=Ticket.HORARIO)
    return ticket, get_object_or_404(Profesor, user_id=ticket.autor_id)


@require_POST
@soporte_required
def agregar_franja(request, id_ticket):
    ticket, profesor = _del_ticket(request, id_ticket)
    try:
        with transaction.atomic():
            franja, nuevos = franjas.agregar(profesor, request.POST)
            publicados = (f'{nuevos} bloques nuevos en tu agenda' if nuevos is not None
                          else 'tus bloques se publican cuando LBWUS apruebe tu t\u00edtulo')
            agregar_mensaje(ticket, request.user, f'Agregamos a tu horario la franja del {franjas.descripcion(franja)}: '
                                                  f'{publicados}.', de_soporte=True)
    except ValidationError as e:
        messages.error(request, e.messages[0])
    else:
        messages.success(request, 'Franja agregada. Se lo contamos al profesor en el ticket.')
    return redirect('soporte_reporte', ticket.pk)


@require_POST
@soporte_required
def quitar_franja(request, id_ticket, pk):
    ticket, profesor = _del_ticket(request, id_ticket)
    franja = get_object_or_404(HorarioSemanal.objects.select_related('clase__asignatura'), pk=pk, profesor=profesor)
    texto = (f'Quitamos de tu horario la franja del {franjas.descripcion(franja)}. Las clases ya reservadas se '
             'mantienen en tu agenda.')
    with transaction.atomic():
        bloques.quitar_franja(franja)
        agregar_mensaje(ticket, request.user, texto, de_soporte=True)
    messages.success(request, 'Franja quitada. Se lo contamos al profesor en el ticket.')
    return redirect('soporte_reporte', ticket.pk)
