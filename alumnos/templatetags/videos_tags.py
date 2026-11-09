from django import template

from .. import videos_compartidos

register = template.Library()


@register.simple_tag
def videos_del_ticket(ticket):
    """Videos que nombra un reclamo de Videos de apoyo (fase 5e); vacio si no lo es. Asi el detalle del ticket
    (app soporte) no importa la logica de videos."""
    return list(videos_compartidos.del_ticket(ticket))
