"""Abrir, cerrar y reasignar tickets. Unico lugar que cambia su estado o su agente.

Los correos salen al confirmar la transaccion: nunca avisan de un ticket que se deshizo.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .correo import avisar_asignacion, avisar_sin_asignar
from .models import AgenteSoporte, Asignacion, Ticket
from .plazos import vencimiento


def agentes_habilitados(categoria):
    """Agentes con cuenta activa que reciben tickets de ``categoria``."""
    return AgenteSoporte.objects.filter(user__is_active=True, habilitaciones__categoria=categoria)


def _agente_con_menos_carga(categoria):
    """Habilitado con menos tickets abiertos; empate: el mas antiguo. None si no hay."""
    return (agentes_habilitados(categoria)
            .annotate(abiertos=Count('tickets', filter=Q(tickets__estado=Ticket.ABIERTO)))
            .order_by('abiertos', 'id_agente').first())


def abrir_ticket(categoria, **revisado):
    """Abre el ticket de ``revisado`` (apoderado=, vinculo= o profesor=) si no tiene
    uno abierto, con su plazo, y lo asigna solo. Sin agente habilitado queda sin
    asignar y se avisa a los lideres."""
    with transaction.atomic():
        if Ticket.objects.filter(estado=Ticket.ABIERTO, **revisado).exists():
            return
        agente = _agente_con_menos_carga(categoria)
        ticket = Ticket.objects.create(categoria=categoria, asignado=agente,
                                       vence=vencimiento(timezone.now(), Ticket.DIAS_HABILES[categoria]),
                                       **revisado)
        if agente is None:
            transaction.on_commit(lambda: avisar_sin_asignar(ticket))
        else:
            Asignacion.objects.create(ticket=ticket, agente=agente)
            transaction.on_commit(lambda: avisar_asignacion(ticket))


def cerrar_tickets(tickets):
    """Cierra los tickets abiertos de un related manager (``revisado.tickets``)."""
    tickets.filter(estado=Ticket.ABIERTO).update(estado=Ticket.CERRADO, cerrado=timezone.now())


def reasignar(ticket, agente, autor):
    """El lider pasa un ticket abierto a otro agente habilitado en su categoria.
    El plazo no cambia."""
    if ticket.estado != Ticket.ABIERTO:
        raise ValidationError('Ese ticket ya está cerrado.')
    if not agentes_habilitados(ticket.categoria).filter(pk=agente.pk).exists():
        raise ValidationError('Ese agente no atiende tickets de esta categoría.')
    with transaction.atomic():
        ticket.asignado = agente
        ticket.save(update_fields=['asignado'])
        Asignacion.objects.create(ticket=ticket, agente=agente, autor=autor)
        transaction.on_commit(lambda: avisar_asignacion(ticket))
