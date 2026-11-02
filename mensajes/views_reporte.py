"""Reportar una conversacion y que soporte la lea (paso C1c).

Reportar lo hace un participante (alumno adulto o profesor). Leerla: solo soporte, desde el
ticket, con la misma visibilidad que ya tiene (el agente asignado, o un lider); el administrador
no. Cada lectura queda registrada.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from alumnos.decorators import soporte_required
from soporte.models import Ticket
from soporte.permisos import agente_en_sesion, reporta_required, tickets_del_agente

from . import servicio
from .forms import ReportarConversacionForm
from .models import Conversacion


@never_cache
@reporta_required
def reportar_conversacion(request, pk):
    conversacion = get_object_or_404(Conversacion.objects.visibles().select_related('alumno__user', 'profesor__user'), pk=pk)
    if not conversacion.es_participante(request.user):  # una ajena ni se confirma que existe
        raise Http404
    form = ReportarConversacionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            reporte = servicio.reportar(request.user, conversacion, form.cleaned_data['descripcion'])
        except ValidationError as error:
            form.add_error(None, error.messages[0])
        else:
            plazo = timezone.localtime(reporte.ticket.vence)
            messages.success(request, f'Reportamos la conversación: ticket #{reporte.ticket_id}. '
                                      f'Te responderemos a más tardar el {plazo:%d-%m-%Y} a las {plazo:%H:%M}.')
            return redirect('mis_tickets')
    es_profesor = conversacion.profesor.user_id == request.user.pk
    ruta = 'panel_profesor' if es_profesor else 'mensajes_apoderado' if conversacion.es_de_apoderado else 'alumno_pag1'
    volver = reverse(ruta)
    return render(request, 'apoderados/formulario.html', {
        'form': form, 'titulo': 'Reportar esta conversación', 'subtitulo': 'Cuéntanos qué pasó', 'boton': 'Reportar',
        'volver_url': f'{volver}?c={conversacion.pk}',
        'intro': 'Soporte podrá leer esta conversación para revisarla, y cada lectura queda registrada. '
                 'Responderemos en 2 días hábiles.',
    })


@never_cache
@soporte_required
def leer_conversacion(request, id_ticket):
    agente = agente_en_sesion(request)
    visibles = Ticket.objects.all() if agente.es_lider else tickets_del_agente(request)
    ticket = get_object_or_404(visibles, pk=id_ticket, reporte_conversacion__isnull=False)
    reporte = ticket.reporte_conversacion
    mensajes = servicio.leer_reportada(reporte, agente)
    conversacion = reporte.conversacion
    return render(request, 'mensajes/soporte_conversacion.html', {
        'agente': agente, 'ticket': ticket, 'reporte': reporte, 'conversacion': conversacion, 'mensajes': mensajes,
        'accesos': reporte.accesos.select_related('agente__user')[:20],
    })
