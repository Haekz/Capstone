"""Recordatorio a los lideres de soporte: conversaciones reportadas que esperan su decision (C1f-2b).

Pensado para un cron diario en Railway: python manage.py avisar_revisiones_pendientes
Mismo ritmo que los avisos de atraso (D11): el primer dia habil de espera y despues cada
Ticket.AVISO_CADA dias habiles. Un solo correo por lider, con la cantidad y sin nombres ni contenido:
el detalle se ve en LBWUS.
"""

from alumnos.correo import enviar
from soporte.correo import lideres
from soporte.models import Ticket
from soporte.plazos import dias_habiles_entre

from . import revision

PLANTILLA = 'mensajes/correo_revision_pendiente.txt'


def _toca_avisar(conversacion, hoy):
    esperando = dias_habiles_entre(revision.pendiente_desde(conversacion), hoy)
    return esperando >= 1 and (esperando - 1) % Ticket.AVISO_CADA == 0


def avisar_pendientes(hoy):
    """Avisa a cada lider las conversaciones que hoy toca recordar. Devuelve cuantas eran."""
    cantidad = sum(_toca_avisar(conversacion, hoy) for conversacion in revision.pendientes(hoy))
    if cantidad:
        for lider in lideres():
            enviar('Conversaciones reportadas por revisar', PLANTILLA,
                   {'nombre': lider.nombre, 'cantidad': cantidad, 'cada': Ticket.AVISO_CADA}, lider.user.email)
    return cantidad
