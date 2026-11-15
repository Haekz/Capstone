"""Casilla de aceptacion de Terminos y Privacidad: {% load legal %} ... {% acepta_terminos %} dentro del formulario."""

from django import template

from alumnos import aceptacion

register = template.Library()


@register.inclusion_tag('alumnos/includes/acepta_terminos.html', takes_context=True)
def acepta_terminos(context):
    """Dibuja la casilla solo si quien compra aun no acepto la version vigente (si ya acepto, no se repite)."""
    user = context['request'].user
    return {'pendiente': user.is_authenticated and aceptacion.pendiente(user), 'campo': aceptacion.CAMPO}
