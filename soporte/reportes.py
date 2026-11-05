"""Tickets que abren los usuarios (D10): alumno, profesor y apoderado.

El usuario ve solo los suyos y contesta mientras esten abiertos. Del lado de soporte,
el detalle lo ve el agente que tiene el ticket abierto o un lider (que supervisa
todos); responde y cierra solo el agente asignado.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from alumnos.decorators import soporte_required
from alumnos.models import PaqueteClases
from alumnos.portales import contexto_de_marco

from .forms import MensajeForm, ReporteForm, RespuestaForm
from .models import Ticket
from .permisos import (agente_en_sesion, categorias_que_reporta, estudiantes_que_reporta, reporta_required,
                       tickets_del_agente)
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
    return render(request, 'soporte/mis_tickets.html',
                  {'tickets': tickets, **contexto_de_marco(request, seccion='ayuda')})


@never_cache
@reporta_required
def nuevo_ticket(request):
    inicial = _inicial_de_pago(request, request.GET['pago']) if 'pago' in request.GET else None
    form = ReporteForm(request.POST or None, initial=inicial, categorias=categorias_que_reporta(request),
                       estudiantes=estudiantes_que_reporta(request))
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
        **contexto_de_marco(request, seccion='ayuda'),
    })


def _inicial_de_pago(request, orden):
    """Boton "Reportar problema con este pago" (6e): precarga un ticket de Pagos. La orden
    llega por la URL: se usa solo si es de un paquete del usuario o de su estudiante."""
    inicial = {'categoria': Ticket.PAGOS}
    paquete = PaqueteClases.objects.filter(
        Q(alumno__user=request.user) | Q(alumno__in=estudiantes_que_reporta(request)),
        buy_order=orden).select_related('alumno').first() if orden else None
    if paquete:
        inicial.update(titulo=f'Problema con el pago {orden}', descripcion=f'Orden de compra: {orden}\n\n')
        if paquete.alumno.user_id != request.user.pk:  # el apoderado reporta por su estudiante
            inicial['estudiante'] = paquete.alumno.pk
    return inicial


@never_cache
@reporta_required
def mi_ticket(request, id_ticket):
    ticket = get_object_or_404(Ticket, pk=id_ticket, autor=request.user)
    form = MensajeForm(request.POST or None) if ticket.estado == Ticket.ABIERTO else None
    if _publicar(request, ticket, form, de_soporte=False):
        return redirect('mi_ticket', ticket.pk)
    return render(request, 'soporte/mi_ticket.html',
                  _contexto(ticket, form, **contexto_de_marco(request, seccion='ayuda')))


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
