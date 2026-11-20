"""Soporte resuelve una solicitud de eliminar la cuenta: ejecutarla o rechazarla.

Solo el agente que tiene el ticket asignado (el lider, reasignandoselo antes): es una accion que no se deshace.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from alumnos.decorators import soporte_required
from soporte.permisos import agente_en_sesion, tickets_del_agente

from . import solicitud as flujo
from .forms import EjecutarForm, RechazarForm


def _de_la_solicitud(request, id_ticket):
    ticket = get_object_or_404(tickets_del_agente(request), pk=id_ticket, solicitud_supresion__isnull=False)
    return ticket, ticket.solicitud_supresion


def _resolver(request, id_ticket, formulario, accion, exito):
    """Aplica ``accion(solicitud, agente, datos)`` y vuelve al ticket (o al panel si ya se cerro)."""
    ticket, solicitud = _de_la_solicitud(request, id_ticket)
    form = formulario(request.POST)
    if not form.is_valid():
        messages.error(request, next(iter(form.errors.values()))[0])
        return redirect('soporte_reporte', ticket.pk)
    try:
        resultado = accion(solicitud, agente_en_sesion(request), form.cleaned_data)
    except flujo.SolicitudError as error:
        messages.error(request, str(error))
        return redirect('soporte_reporte', ticket.pk)
    messages.success(request, exito(resultado))
    return redirect('panel_soporte')


@require_POST
@soporte_required
def ejecutar(request, id_ticket):
    def aplicar(solicitud, agente, _datos):
        return flujo.ejecutar(solicitud, agente)

    def exito(resultado):
        borrada, avisada = resultado
        texto = 'Cuenta borrada por completo.' if borrada else 'Cuenta eliminada: se seudonimizó y se conserva lo que corresponde.'
        return texto + ('' if avisada else ' No se pudo enviar el correo con el resultado al usuario.')

    return _resolver(request, id_ticket, EjecutarForm, aplicar, exito)


@require_POST
@soporte_required
def rechazar(request, id_ticket):
    return _resolver(request, id_ticket, RechazarForm,
                     lambda solicitud, agente, datos: flujo.rechazar(solicitud, agente, datos['motivo']),
                     lambda _: 'Le respondimos al usuario y cerramos la solicitud.')
