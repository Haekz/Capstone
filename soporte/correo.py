"""Correos de soporte: ticket asignado, ticket sin asignar, documentos por vencer,
resumen de atrasados (al equipo y a quien espera) y respuestas en tickets de usuarios.

Sin datos personales de apoderados ni profesores: solo numero, categoria y plazo.
Tampoco el texto de las respuestas. El detalle se ve en LBWUS. Devuelven False si
algun correo no salio.
"""

from django.utils import timezone

from alumnos.correo import enviar

from .models import AgenteSoporte, Ticket
from .plazos import dias_habiles_entre

# Para Ticket.solicitante sin una consulta por ticket.
SOLICITANTE = ('autor', 'apoderado__user', 'vinculo__apoderado__user', 'profesor__user')


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


def avisar_respuesta(ticket):
    """Al usuario que abrio el ticket: soporte respondio (o lo cerro). Un menor puede no
    tener correo: lo ve al entrar."""
    if not ticket.autor.email:
        return False
    return enviar(f'Respuesta en tu ticket #{ticket.pk}', 'soporte/correo_respuesta.txt',
                  {'nombre': ticket.autor.first_name, 'ticket': ticket}, ticket.autor.email)


def avisar_contestacion(ticket):
    """Al agente del ticket: el usuario contesto."""
    agente = ticket.asignado
    return enviar(f'Ticket #{ticket.pk}: el usuario contestó', 'soporte/correo_contestacion.txt',
                  {'nombre': agente.nombre, 'ticket': ticket}, agente.user.email)


def avisar_documentos_por_vencer(ticket, borra_el):
    """Al agente del ticket; si no tiene, a los lideres."""
    destinos = [ticket.asignado] if ticket.asignado else _lideres()
    return all([enviar(f'Ticket #{ticket.pk}: documentos por vencer', 'soporte/correo_documentos_por_vencer.txt',
                       {'nombre': agente.nombre, 'ticket': ticket, 'borra_el': borra_el}, agente.user.email)
                for agente in destinos])


def _toca_avisar(ticket, hoy):
    """El primer dia habil de atraso y despues cada Ticket.AVISO_CADA dias habiles."""
    atraso = dias_habiles_entre(timezone.localtime(ticket.vence).date(), hoy)
    return (atraso - 1) % Ticket.AVISO_CADA == 0


def avisar_atrasados(hoy):
    """Un resumen a cada agente con sus tickets atrasados que toca avisar hoy, otro a
    cada lider con todos ellos y una disculpa a quien espera cada uno (D11).
    Devuelve cuantos tickets se avisaron."""
    atrasados = [ticket for ticket in Ticket.objects.filter(estado=Ticket.ABIERTO, respondido__isnull=True,
                                                           vence__date__lt=hoy)
                 .select_related('asignado__user', *SOLICITANTE).order_by('vence', 'id')
                 if _toca_avisar(ticket, hoy)]
    por_agente = {}
    for ticket in atrasados:
        if ticket.asignado is not None:
            por_agente.setdefault(ticket.asignado, []).append(ticket)
    contexto = {'cada': Ticket.AVISO_CADA}
    for agente, tickets in por_agente.items():
        enviar('Tickets atrasados', 'soporte/correo_atrasados.txt',
               {**contexto, 'nombre': agente.nombre, 'tickets': tickets, 'lider': False}, agente.user.email)
    if atrasados:
        for lider in _lideres():
            enviar('Tickets atrasados del equipo', 'soporte/correo_atrasados.txt',
                   {**contexto, 'nombre': lider.nombre, 'tickets': atrasados, 'lider': True}, lider.user.email)
    for ticket in atrasados:
        _disculpar_atraso(ticket)
    return len(atrasados)


def _disculpar_atraso(ticket):
    """A quien espera: sin datos del caso, solo numero y categoria. Sin correo, nada."""
    persona = ticket.solicitante
    if not persona.email:
        return False
    return enviar(f'Tu solicitud #{ticket.pk} va con atraso', 'soporte/correo_atraso_usuario.txt',
                  {'nombre': persona.first_name, 'ticket': ticket}, persona.email)
