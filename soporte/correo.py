"""Correos de soporte: ticket asignado, ticket sin asignar y resumen de atrasados.

Sin datos personales de apoderados ni profesores: solo numero, categoria y plazo.
El detalle se ve en el panel de soporte. Devuelven False si algun correo no salio.
"""

from django.utils import timezone

from alumnos.correo import enviar

from .models import AgenteSoporte, Ticket


def _lideres():
    return AgenteSoporte.objects.filter(es_lider=True, user__is_active=True).select_related('user')


def avisar_asignacion(ticket):
    agente = ticket.asignado
    return enviar(f'Ticket #{ticket.pk} asignado', 'soporte/correo_asignacion.txt',
                  {'nombre': agente.nombre, 'ticket': ticket}, agente.user.email)


def avisar_sin_asignar(ticket):
    return all([enviar(f'Ticket #{ticket.pk} sin asignar', 'soporte/correo_sin_asignar.txt',
                       {'nombre': lider.nombre, 'ticket': ticket}, lider.user.email)
                for lider in _lideres()])


def avisar_atrasados():
    """Un resumen a cada agente con sus tickets vencidos y otro a cada lider con todos.
    Devuelve cuantos tickets estan atrasados."""
    atrasados = list(Ticket.objects.filter(estado=Ticket.ABIERTO, vence__lt=timezone.now())
                     .select_related('asignado__user').order_by('vence', 'id'))
    por_agente = {}
    for ticket in atrasados:
        if ticket.asignado is not None:
            por_agente.setdefault(ticket.asignado, []).append(ticket)
    for agente, tickets in por_agente.items():
        enviar('Tickets atrasados', 'soporte/correo_atrasados.txt',
               {'nombre': agente.nombre, 'tickets': tickets, 'lider': False}, agente.user.email)
    if atrasados:
        for lider in _lideres():
            enviar('Tickets atrasados del equipo', 'soporte/correo_atrasados.txt',
                   {'nombre': lider.nombre, 'tickets': atrasados, 'lider': True}, lider.user.email)
    return len(atrasados)
