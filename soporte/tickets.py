"""Abrir, cerrar y reasignar tickets. Unico lugar que cambia su estado o su agente."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import AgenteSoporte, Asignacion, Ticket


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
    uno abierto, y lo asigna solo. Sin agente habilitado queda sin asignar."""
    with transaction.atomic():
        if Ticket.objects.filter(estado=Ticket.ABIERTO, **revisado).exists():
            return
        agente = _agente_con_menos_carga(categoria)
        ticket = Ticket.objects.create(categoria=categoria, asignado=agente, **revisado)
        if agente is not None:
            Asignacion.objects.create(ticket=ticket, agente=agente)


def cerrar_tickets(tickets):
    """Cierra los tickets abiertos de un related manager (``revisado.tickets``)."""
    tickets.filter(estado=Ticket.ABIERTO).update(estado=Ticket.CERRADO, cerrado=timezone.now())


def reasignar(ticket, agente, autor):
    """El lider pasa un ticket abierto a otro agente habilitado en su categoria."""
    if ticket.estado != Ticket.ABIERTO:
        raise ValidationError('Ese ticket ya está cerrado.')
    if not agentes_habilitados(ticket.categoria).filter(pk=agente.pk).exists():
        raise ValidationError('Ese agente no atiende tickets de esta categoría.')
    with transaction.atomic():
        ticket.asignado = agente
        ticket.save(update_fields=['asignado'])
        Asignacion.objects.create(ticket=ticket, agente=agente, autor=autor)
