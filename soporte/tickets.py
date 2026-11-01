"""Abrir, cerrar y reasignar tickets. Unico lugar que cambia su estado o su agente.

Los correos salen al confirmar la transaccion: nunca avisan de un ticket que se deshizo.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .correo import (avisar_asignacion, avisar_conducta, avisar_contestacion, avisar_respuesta,
                     avisar_sin_asignar)
from .models import AgenteSoporte, Asignacion, Mensaje, Ticket
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
        _crear(categoria, **revisado)


def abrir_reporte(autor, categoria, titulo, descripcion):
    """Ticket que abre un usuario (D10). Puede tener varios abiertos a la vez."""
    with transaction.atomic():
        return _crear(categoria, autor=autor, titulo=titulo, descripcion=descripcion)


def _crear(categoria, **campos):
    """Crea el ticket con su plazo y lo asigna al agente con menos carga. Conducta:
    los lideres se enteran siempre (N5), y ese aviso ya dice si quedo sin asignar."""
    agente = _agente_con_menos_carga(categoria)
    ticket = Ticket.objects.create(categoria=categoria, asignado=agente,
                                   vence=vencimiento(timezone.now(), Ticket.DIAS_HABILES[categoria]),
                                   **campos)
    if categoria == Ticket.CONDUCTA:
        transaction.on_commit(lambda: avisar_conducta(ticket))
    elif agente is None:
        transaction.on_commit(lambda: avisar_sin_asignar(ticket))
    if agente is not None:
        Asignacion.objects.create(ticket=ticket, agente=agente)
        transaction.on_commit(lambda: avisar_asignacion(ticket))
    return ticket


def cerrar_tickets(tickets):
    """Cierra los tickets abiertos de un related manager (``revisado.tickets``)."""
    tickets.filter(estado=Ticket.ABIERTO).update(estado=Ticket.CERRADO, cerrado=timezone.now())


def agregar_mensaje(ticket, autor, texto, de_soporte, cerrar=False):
    """Respuesta en un ticket de usuario abierto. Soporte puede cerrarlo con ella, y su
    primera respuesta cumple el plazo. Avisa a la otra parte, sin el texto: se lee en LBWUS."""
    if ticket.estado != Ticket.ABIERTO:
        raise ValidationError('Ese ticket ya está cerrado.')
    with transaction.atomic():
        Mensaje.objects.create(ticket=ticket, autor=autor, texto=texto, de_soporte=de_soporte)
        if de_soporte:
            Ticket.objects.filter(pk=ticket.pk, respondido__isnull=True).update(respondido=timezone.now())
        if cerrar:
            cerrar_tickets(Ticket.objects.filter(pk=ticket.pk))
        ticket.refresh_from_db()
        if de_soporte:
            transaction.on_commit(lambda: avisar_respuesta(ticket))
        elif ticket.asignado_id:
            transaction.on_commit(lambda: avisar_contestacion(ticket))


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
