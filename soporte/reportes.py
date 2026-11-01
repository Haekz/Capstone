"""Tickets que abren los usuarios (D10): alumno, profesor y apoderado.

El usuario ve solo los suyos y contesta mientras esten abiertos. Del lado de soporte,
el detalle lo ve el agente que tiene el ticket abierto o un lider (que supervisa
todos); responde y cierra solo el agente asignado.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from alumnos.decorators import soporte_required

from .forms import MensajeForm, ReporteForm, RespuestaForm
from .models import Ticket
from .permisos import agente_en_sesion, categorias_que_reporta, reporta_required, tickets_del_agente
from .tickets import abrir_reporte, agregar_mensaje


def _publicar(request, ticket, form, de_soporte):
    """Guarda la respuesta de un formulario enviado y valido. True si hubo envio."""
    if request.method != 'POST' or form is None or not form.is_valid():
        return False
    try:
        agregar_mensaje(ticket, request.user, form.cleaned_data['texto'], de_soporte,
                        cerrar=form.cleaned_data.get('cerrar', False))
    except ValidationError as error:  # se cerro mientras escribia
        messages.error(request, error.messages[0])
    else:
        messages.success(request, 'Respuesta enviada.')
    return True


def _contexto(ticket, form, **extra):
    return {'ticket': ticket, 'form': form, 'mensajes': ticket.mensajes.select_related('autor'), **extra}


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
        'intro': 'Pagos, clases y conducta: respondemos en 2 días hábiles. Lo demás, en 5 días hábiles.',
    })


@never_cache
@reporta_required
def mi_ticket(request, id_ticket):
    ticket = get_object_or_404(Ticket, pk=id_ticket, autor=request.user)
    form = MensajeForm(request.POST or None) if ticket.estado == Ticket.ABIERTO else None
    if _publicar(request, ticket, form, de_soporte=False):
        return redirect('mi_ticket', ticket.pk)
    return render(request, 'soporte/mi_ticket.html', _contexto(ticket, form))


@never_cache
@soporte_required
def ver_reporte(request, id_ticket):
    agente = agente_en_sesion(request)
    visibles = Ticket.objects.all() if agente.es_lider else tickets_del_agente(request)
    ticket = get_object_or_404(visibles.select_related('autor', 'asignado__user'),
                               pk=id_ticket, autor__isnull=False)
    # Responde solo quien lo tiene asignado; el lider, reasignandoselo antes.
    propio = tickets_del_agente(request).filter(pk=ticket.pk).exists()
    form = RespuestaForm(request.POST or None) if propio else None
    if _publicar(request, ticket, form, de_soporte=True):
        # Cerrado ya no es del agente: vuelve a su panel en vez de un 404.
        return redirect('soporte_reporte', ticket.pk) if ticket.estado == Ticket.ABIERTO else redirect('panel_soporte')
    return render(request, 'soporte/reporte.html', _contexto(ticket, form, agente=agente))
