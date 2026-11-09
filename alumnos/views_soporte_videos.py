"""Soporte ve y retira un video reportado desde su ticket de Videos de apoyo (fase 5e, decidido 09-nov).

Mismo patron que el horario (agenda/views_soporte.py). Solo los videos que nombra el reclamo y que de verdad se
compartieron con ese estudiante (videos_compartidos.del_ticket). Ver: el agente asignado o un lider. Retirar: solo el
agente asignado (el lider, reasignandoselo antes). El retiro queda como mensaje de soporte en el ticket (el registro
de quien, que y cuando, y el aviso al que reclamo) y se avisa al profesor; si el mensaje falla, no se retira.
"""

from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from soporte.models import Ticket
from soporte.permisos import tickets_del_agente, tickets_visibles
from soporte.tickets import agregar_mensaje

from . import avisos_profesor, videos_compartidos
from .decorators import soporte_required
from .models import VideoCompartido


def _del_ticket(tickets, id_ticket, video_id):
    """El ticket de Videos (entre ``tickets``) y sus registros de ese video; 404 si no es uno de los suyos."""
    ticket = get_object_or_404(tickets, pk=id_ticket, categoria=Ticket.VIDEOS)
    return ticket, videos_compartidos.del_ticket(ticket).filter(video_id=video_id)


@require_GET
@soporte_required
def ver_video(request, id_ticket, video_id):
    _, compartidos = _del_ticket(tickets_visibles(request), id_ticket, video_id)
    if not compartidos.exists():
        raise Http404
    return videos_compartidos.archivo_respuesta(request, video_id)


@require_POST
@soporte_required
def retirar_video(request, id_ticket, video_id):
    ticket, compartidos = _del_ticket(tickets_del_agente(request), id_ticket, video_id)
    compartido = compartidos.entregados().first()
    if compartido is None:  # ajeno o ya retirado
        raise Http404
    with transaction.atomic():
        VideoCompartido.objects.filter(pk=compartido.pk).update(retirado=timezone.now())
        agregar_mensaje(ticket, request.user, 'Retiramos el video que reportaste: ya no aparece en tus videos. '
                                              'Tu profesor puede compartirte otro.', de_soporte=True)
        avisos_profesor.video_retirado(compartido)
    messages.success(request, 'Video retirado. Se lo contamos en el ticket y le avisamos al profesor.')
    return redirect('soporte_reporte', ticket.pk)
