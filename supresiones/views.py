"""Lo que ve quien pide eliminar su cuenta: que se elimina y que se conserva, el enlace al correo y la confirmacion.

Disponible para alumno, profesor y apoderado adultos (soporte.permisos.reporta_required); un alumno menor no:
su apoderado habla por el.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from soporte.models import Ticket
from soporte.permisos import reporta_required

from . import identidad, solicitud
from .evaluacion import evaluar
from .forms import ConfirmarForm, EntiendoForm


def _datos(request):
    """Un checkbox sin marcar manda un POST vacio: ``request.POST or None`` lo dejaria sin enlazar y sin errores."""
    return request.POST if request.method == 'POST' else None


@never_cache
@reporta_required
def eliminar_cuenta(request):
    abierta = solicitud.abierta_de(request.user)
    if abierta:
        return render(request, 'supresiones/en_curso.html', {'solicitud': abierta})
    form = EntiendoForm(_datos(request))
    if request.method == 'POST' and form.is_valid():
        if identidad.pedir(request, request.user):
            messages.success(request, f'Te enviamos un enlace a {request.user.email}. Ábrelo con tu sesión iniciada '
                                      'para confirmar que eres tú.')
        elif not request.user.email:
            messages.error(request, 'No tenemos un correo registrado para confirmar tu identidad. '
                                    'Escríbenos desde un ticket de soporte.')
        else:
            messages.error(request, 'No pudimos enviar el correo. Intenta de nuevo en unos minutos.')
        return redirect('eliminar_cuenta')
    return render(request, 'supresiones/eliminar_cuenta.html',
                  {'form': form, 'evaluacion': evaluar(request.user),
                   'plazo_dias': Ticket.DIAS_HABILES[Ticket.PRIVACIDAD]})


@never_cache
@reporta_required
def confirmar(request, token):
    """Abrir el enlace solo muestra la pregunta; la solicitud se crea al confirmar (un POST), no al abrir un enlace."""
    try:
        identidad.verificar(token, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect('eliminar_cuenta')
    form = ConfirmarForm(_datos(request))
    if request.method == 'POST' and form.is_valid():
        abierta, creada = solicitud.abrir(request.user)
        plazo = timezone.localtime(abierta.ticket.vence)
        messages.success(request, (f'Recibimos tu solicitud #{abierta.pk}. Te respondemos a más tardar el '
                                   f'{plazo:%d-%m-%Y}.') if creada else 'Ya tenías una solicitud abierta.')
        return redirect('mi_ticket', abierta.ticket_id)
    return render(request, 'supresiones/confirmar.html', {'form': form, 'evaluacion': evaluar(request.user)})
