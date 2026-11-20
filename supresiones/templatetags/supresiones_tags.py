from django import template

from supresiones.evaluacion import evaluar
from supresiones.models import SolicitudSupresion

register = template.Library()


@register.simple_tag
def evaluacion_pendiente(ticket):
    """Evaluacion de la cuenta si el ticket es una solicitud todavia abierta; None si no. Asi el detalle del
    ticket (app soporte) no importa esta app."""
    solicitud = getattr(ticket, 'solicitud_supresion', None)
    if solicitud is None or solicitud.estado != SolicitudSupresion.ABIERTA or solicitud.usuario_id is None:
        return None
    return evaluar(solicitud.usuario, ticket)
