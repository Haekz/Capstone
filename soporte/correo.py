"""Correos de soporte: ticket asignado, ticket sin asignar, documentos por vencer,
resumen de atrasados (al equipo y a quien espera), respuestas en tickets de usuarios y
casos escalados (a los administradores y su indicacion de vuelta a soporte).

Sin datos personales de apoderados ni profesores: solo numero, categoria y plazo.
Tampoco el texto de las respuestas, los motivos ni las indicaciones. El detalle se ve en
LBWUS. Excepcion: al visitante de Contactanos le llega la respuesta, porque no tiene cuenta
donde leerla. Devuelven False si algun correo no salio.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone

from alumnos.correo import enviar

from .models import AgenteSoporte, Ticket
from .plazos import dias_habiles_entre

# Para Ticket.solicitante sin una consulta por ticket.
SOLICITANTE = ('autor', 'apoderado__user', 'vinculo__apoderado__user', 'profesor__user')


def lideres():
    return AgenteSoporte.objects.filter(es_lider=True, user__is_active=True).select_related('user')


def avisar_asignacion(ticket, escalado=False):
    """``escalado``: un agente se lo paso al lider por ser grave."""
    agente = ticket.asignado
    asunto = f'Ticket #{ticket.pk} escalado a ti' if escalado else f'Ticket #{ticket.pk} asignado'
    return enviar(asunto, 'soporte/correo_asignacion.txt',
                  {'nombre': agente.nombre, 'ticket': ticket, 'escalado': escalado}, agente.user.email)


def avisar_sin_asignar(ticket):
    return all([enviar(f'Ticket #{ticket.pk} sin asignar', 'soporte/correo_sin_asignar.txt',
                       {'nombre': lider.nombre, 'ticket': ticket}, lider.user.email)
                for lider in lideres()])


def avisar_conducta(ticket):
    """Ruta urgente (N5): los lideres saben de inmediato de cada reporte de conducta,
    tenga agente o no. Sin el contenido."""
    return all([enviar(f'Reporte de conducta #{ticket.pk}', 'soporte/correo_conducta.txt',
                       {'nombre': lider.nombre, 'ticket': ticket}, lider.user.email)
                for lider in lideres()])


def avisar_respuesta(ticket, texto):
    """Al usuario que abrio el ticket: soporte respondio (o lo cerro). Un menor puede no
    tener correo: lo ve al entrar."""
    if ticket.contacto_id:
        return _responder_contacto(ticket, texto)
    if not ticket.autor.email:
        return False
    return enviar(f'Respuesta en tu ticket #{ticket.pk}', 'soporte/correo_respuesta.txt',
                  {'nombre': ticket.autor.first_name, 'ticket': ticket}, ticket.autor.email)


def _responder_contacto(ticket, texto):
    """Al visitante de Contactanos, con la respuesta: es su unico canal. No repite lo que
    escribio: el correo no esta verificado, y citarlo dejaria a cualquiera mandar su propio
    texto a un tercero con el remitente de LBWUS."""
    contacto = ticket.contacto
    return enviar('Respuesta a tu mensaje a LBWUS', 'soporte/correo_respuesta_contacto.txt',
                  {'nombre': contacto.nombre, 'texto': texto}, contacto.correo)


def avisar_contestacion(ticket):
    """Al agente del ticket: el usuario contesto."""
    agente = ticket.asignado
    return enviar(f'Ticket #{ticket.pk}: el usuario contestó', 'soporte/correo_contestacion.txt',
                  {'nombre': agente.nombre, 'ticket': ticket}, agente.user.email)


def avisar_escalamiento_admin(escalamiento):
    """A cada administrador activo: un lider le escalo un caso."""
    administradores = (get_user_model().objects.filter(perfil_tutor__isnull=False, is_active=True)
                       .exclude(email=''))
    ticket = escalamiento.ticket
    return all([enviar(f'Caso escalado: ticket #{ticket.pk}', 'soporte/correo_escalamiento_admin.txt',
                       {'nombre': admin.first_name, 'ticket': ticket}, admin.email)
                for admin in administradores])


def avisar_indicacion(escalamiento):
    """Al lider que escalo y al agente del ticket (si es otro): el administrador respondio."""
    ticket = escalamiento.ticket
    personas = {escalamiento.autor, ticket.asignado.user if ticket.asignado else None} - {None}
    return all([enviar(f'Ticket #{ticket.pk}: indicación del administrador', 'soporte/correo_indicacion.txt',
                       {'nombre': persona.first_name, 'ticket': ticket}, persona.email)
                for persona in personas if persona.email])


def avisar_documentos_por_vencer(ticket, borra_el):
    """Al agente del ticket; si no tiene, a los lideres."""
    destinos = [ticket.asignado] if ticket.asignado else lideres()
    return all([enviar(f'Ticket #{ticket.pk}: documentos por vencer', 'soporte/correo_documentos_por_vencer.txt',
                       {'nombre': agente.nombre, 'ticket': ticket, 'borra_el': borra_el}, agente.user.email)
                for agente in destinos])


def _toca_avisar(ticket, hoy, cada=None):
    """El primer dia habil de atraso y despues cada ``cada`` dias habiles (por defecto,
    ticket.aviso_cada: el ritmo del aviso al equipo)."""
    atraso = dias_habiles_entre(timezone.localtime(ticket.vence).date(), hoy)
    return (atraso - 1) % (cada or ticket.aviso_cada) == 0


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
        for lider in lideres():
            enviar('Tickets atrasados del equipo', 'soporte/correo_atrasados.txt',
                   {**contexto, 'nombre': lider.nombre, 'tickets': atrasados, 'lider': True}, lider.user.email)
    for ticket in atrasados:
        # Al usuario, siempre cada AVISO_CADA: en Conducta el equipo se avisa a diario,
        # pero una disculpa diaria seria insistente (D17, revisada el 01-nov).
        if _toca_avisar(ticket, hoy, cada=Ticket.AVISO_CADA):
            _disculpar_atraso(ticket)
    return len(atrasados)


def _disculpar_atraso(ticket):
    """A quien espera: sin datos del caso, solo numero y categoria. Sin correo, nada.
    Tampoco al visitante de Contactanos: el aviso lo manda a una cuenta que no tiene."""
    persona = ticket.solicitante
    if persona is None or not persona.email:
        return False
    return enviar(f'Tu solicitud #{ticket.pk} va con atraso', 'soporte/correo_atraso_usuario.txt',
                  {'nombre': persona.first_name, 'ticket': ticket}, persona.email)
