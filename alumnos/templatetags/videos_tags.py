from django import template

from .. import videos_compartidos, videos_extra

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
