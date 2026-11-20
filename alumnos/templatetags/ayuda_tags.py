from django import template

from alumnos import ayuda

register = template.Library()


@register.inclusion_tag('alumnos/includes/lineas_ayuda.html')
def lineas_de_ayuda(user):
    """Bloque de ayuda con los telefonos que corresponden a ``user`` (alumnos/ayuda.py)."""
    return {'lineas': ayuda.lineas_para(user)}
