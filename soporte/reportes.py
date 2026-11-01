"""Tickets que abren los usuarios (D10): alumno, profesor y apoderado.

El usuario ve solo los suyos. Del lado de soporte, el detalle lo ve el agente que
tiene el ticket abierto o un lider (que supervisa todos).
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from alumnos.decorators import soporte_required

from .forms import ReporteForm
from .models import Ticket
from .permisos import agente_en_sesion, categorias_que_reporta, reporta_required, tickets_del_agente
from .tickets import abrir_reporte


@never_cache
@reporta_required
def mis_tickets(request):
    tickets = Ticket.objects.filter(autor=request.user).order_by('-creado', '-id')
    return render(request, 'soporte/mis_tickets.html', {'tickets': tickets})


@never_cache
@reporta_required
def nuevo_ticket(request):
    form = ReporteForm(request.POST or None, categorias=categorias_que_reporta(request))
    if request.method == 'POST' and form.is_valid():
        ticket = abrir_reporte(request.user, **form.cleaned_data)
        plazo = timezone.localtime(ticket.vence)
        messages.success(request, f'Abrimos el ticket #{ticket.pk}. Te responderemos a más tardar el '
                                  f'{plazo:%d-%m-%Y} a las {plazo:%H:%M}.')
        return redirect('mis_tickets')
    return render(request, 'apoderados/formulario.html', {
        'form': form, 'titulo': 'Abrir un ticket', 'subtitulo': 'Cuéntanos qué pasó', 'boton': 'Enviar',
        'volver_url': reverse('mis_tickets'),
        'intro': 'Pagos y clases: respondemos en 2 días hábiles. Lo demás, en 5 días hábiles.',
    })


@never_cache
@soporte_required
def ver_reporte(request, id_ticket):
    agente = agente_en_sesion(request)
    visibles = Ticket.objects.all() if agente.es_lider else tickets_del_agente(request)
    ticket = get_object_or_404(visibles.select_related('autor', 'asignado__user'),
                               pk=id_ticket, autor__isnull=False)
    return render(request, 'soporte/reporte.html', {'agente': agente, 'ticket': ticket})
