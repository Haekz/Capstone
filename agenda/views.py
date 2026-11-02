"""Agregar y quitar franjas del horario semanal (paso B1c). Vuelven al panel con un mensaje."""

from datetime import time

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from alumnos.decorators import profesor_required
from alumnos.models import Profesor

from . import bloques
from .models import HorarioSemanal


def _profesor(request):
    return get_object_or_404(Profesor, id_profesor=request.session.get('profesor_id'))


@require_POST
@profesor_required
def agregar_franja(request):
    profesor = _profesor(request)
    try:
        franja = HorarioSemanal(profesor=profesor, dia_semana=int(request.POST.get('dia_semana', '')),
                                hora_inicio=time.fromisoformat(request.POST.get('hora_inicio', '')),
                                hora_fin=time.fromisoformat(request.POST.get('hora_fin', '')))
        franja.full_clean()
    except ValueError:
        messages.error(request, 'Elige el día y las horas de la franja.')
    except ValidationError as e:
        messages.error(request, e.messages[0])
    else:
        franja.save()
        if profesor.puede_hacer_clases:
            messages.success(request, f'Franja guardada: {bloques.generar(profesor)} bloques nuevos en tu agenda.')
        else:
            messages.success(request, 'Franja guardada. Tus bloques se publican cuando LBWUS apruebe tu título.')
    return redirect('panel_profesor')


@require_POST
@profesor_required
def quitar_franja(request, pk):
    franja = get_object_or_404(HorarioSemanal, pk=pk, profesor=_profesor(request))  # solo las propias
    bloques.quitar_franja(franja)
    messages.success(request, 'Franja quitada. Las clases ya reservadas se mantienen en tu agenda.')
    return redirect('panel_profesor')
