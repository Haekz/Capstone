from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def meses_de_conservacion():
    """El plazo real (settings.OBSERVACIONES_MESES): el aviso de las pantallas nunca dice otra cosa que lo que se hace."""
    return settings.OBSERVACIONES_MESES
