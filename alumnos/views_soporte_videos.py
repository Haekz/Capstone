"""Soporte ve y retira un video reportado desde su ticket de Videos de apoyo (fase 5e, decidido 09-nov).

Mismo patron que el horario (agenda/views_soporte.py). Solo los videos que nombra el reclamo y que de verdad se
compartieron con ese estudiante (videos_compartidos.del_ticket). Ver: el agente asignado o un lider. Retirar: solo el
agente asignado (el lider, reasignandoselo antes). El retiro queda como mensaje de soporte en el ticket (el registro
de quien, que y cuando, y el aviso al que reclamo) y se avisa al profesor; si el mensaje falla, no se retira.

Fase 6e: con el mismo criterio (solo el agente asignado, mensaje en el ticket y aviso al profesor) soporte registra la
devolucion de videos que el profesor no entrego y despues la marca devuelta (reglas en devoluciones_videos.py).
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from soporte.models import Ticket
from soporte.permisos import tickets_del_agente, tickets_visibles
from soporte.tickets import agregar_mensaje

from . import avisos_profesor, devoluciones_videos, reembolsos, videos_compartidos
from .decorators import soporte_required
from .models import VideoCompartido
from .models.videos import DevolucionVideos
from .templatetags.dinero import clp
from .utils import entero


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


def _videos(cantidad):
    return f'{cantidad} video{"" if cantidad == 1 else "s"}'


def _devolver_por_transbank(request, ticket, devolucion):
    """Intenta el reembolso automatico (reembolsos.py) y, si sale, se lo cuenta al reclamante. True si quedo devuelta.

    Va fuera de toda transaccion: no se espera a la red con el paquete bloqueado. Si no sale, no se escribe nada al
    alumno: la devolucion sigue por devolver a mano y soporte ve el motivo en el panel.
    """
    if not reembolsos.intentar(devolucion):
        return False
    agregar_mensaje(ticket, request.user,
                    f'Ya te devolvimos {clp(devolucion.monto)} por {_videos(devolucion.cantidad)} que tu profesor no te '
                    'compartió, por el mismo medio de pago con que pagaste. Tu banco puede tardar unos días en mostrarlo.',
                    de_soporte=True)
    return True


@require_POST
@soporte_required
def devolver_videos(request, id_ticket):
    """Registra la devolucion de videos que el profesor no entrego y la intenta por Transbank. El monto lo calcula el servidor."""
    ticket = get_object_or_404(tickets_del_agente(request), pk=id_ticket, categoria=Ticket.VIDEOS)
    try:
        with transaction.atomic():  # si el mensaje al reclamante falla, no queda registrada
            devolucion = devoluciones_videos.registrar(
                ticket, request.POST.get('paquete'), entero(request.POST.get('cantidad')) or 0, request.user)
            agregar_mensaje(ticket, request.user,
                            f'Aprobamos devolverte {clp(devolucion.monto)} por {_videos(devolucion.cantidad)} que tu '
                            'profesor no te compartió.', de_soporte=True)
            avisos_profesor.videos_devueltos(devolucion)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect('soporte_reporte', ticket.pk)
    if _devolver_por_transbank(request, ticket, devolucion):
        messages.success(request, 'Devolución registrada y devuelta por Transbank. Se lo contamos en el ticket y le avisamos al profesor.')
    else:
        agregar_mensaje(ticket, request.user, 'Soporte te hará llegar el dinero y te avisará aquí cuando esté devuelto.',
                        de_soporte=True)
        messages.warning(request, 'Devolución registrada, pero no salió por Transbank (abajo está el motivo). '
                                  'Reintenta o devuélvela a mano. Le avisamos al profesor.')
    return redirect('soporte_reporte', ticket.pk)


@require_POST
@soporte_required
def pedir_aprobacion_devolucion(request, id_ticket, id_devolucion):
    """Soporte no pudo devolver por Transbank: le pide al administrador que apruebe transferir a mano (solo el agente asignado)."""
    ticket = get_object_or_404(tickets_del_agente(request), pk=id_ticket, categoria=Ticket.VIDEOS)
    devolucion = get_object_or_404(DevolucionVideos.objects.select_related('ticket', 'escalamiento'),
                                   pk=id_devolucion, ticket=ticket, devuelta__isnull=True)
    try:
        with transaction.atomic():
            devoluciones_videos.pedir_aprobacion(devolucion, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, 'Se lo pedimos al administrador. Cuando apruebe, podrás transferir y marcarla devuelta.')
    return redirect('soporte_reporte', ticket.pk)


@require_POST
@soporte_required
def reintentar_reembolso(request, id_ticket, id_devolucion):
    """Soporte vuelve a intentar por Transbank una devolucion que no salio (solo el agente asignado)."""
    ticket = get_object_or_404(tickets_del_agente(request), pk=id_ticket, categoria=Ticket.VIDEOS)
    devolucion = get_object_or_404(DevolucionVideos, pk=id_devolucion, ticket=ticket, devuelta__isnull=True)
    if _devolver_por_transbank(request, ticket, devolucion):
        messages.success(request, 'Devuelta por Transbank. Se lo contamos en el ticket.')
    else:
        messages.warning(request, 'Transbank tampoco pudo devolverla (abajo está el motivo). Puedes devolverla a mano.')
    return redirect('soporte_reporte', ticket.pk)


@require_POST
@soporte_required
def devolucion_hecha(request, id_ticket, id_devolucion):
    """Soporte ya transfirio el dinero: queda marcada (una sola vez) y se le cuenta al reclamante en el ticket."""
    ticket = get_object_or_404(tickets_del_agente(request), pk=id_ticket, categoria=Ticket.VIDEOS)
    try:
        with transaction.atomic():
            devolucion = devoluciones_videos.marcar_devuelta(ticket, id_devolucion)
            agregar_mensaje(ticket, request.user,
                            f'Ya te devolvimos {clp(devolucion.monto)} por {_videos(devolucion.cantidad)} que tu '
                            'profesor no te compartió.', de_soporte=True)
    except ValidationError:  # no es de este ticket o ya estaba marcada
        raise Http404
    messages.success(request, 'Devolución marcada como devuelta. Se lo contamos en el ticket.')
    return redirect('soporte_reporte', ticket.pk)
