from django import template

from .. import devoluciones_videos, videos_compartidos, videos_extra

register = template.Library()


@register.simple_tag
def ofertas_videos_extra(alumno):
    """Lo que ``alumno`` puede comprar como videos extra (fase 6c); vacío si nada. Asi la plantilla no depende de que
    la vista del alumno ni la del apoderado lo calculen."""
    return videos_extra.ofertas(alumno.pk)


@register.simple_tag
def videos_del_ticket(ticket):
    """Videos que nombra un reclamo de Videos de apoyo (fase 5e); vacio si no lo es. Asi el detalle del ticket
    (app soporte) no importa la logica de videos."""
    return list(videos_compartidos.del_ticket(ticket))


@register.simple_tag
def devoluciones_del_ticket(ticket):
    """Para el panel de soporte de un reclamo de Videos (fase 6e): {'paquetes': los que tienen videos sin entregar,
    'devoluciones': las ya registradas en el ticket}. Vacio si no es un ticket de Videos."""
    return devoluciones_videos.casos_del_ticket(ticket)
