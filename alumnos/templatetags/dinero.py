"""Formato de dinero en las plantillas: {% load dinero %} ... {{ monto|clp }}."""

from django import template

register = template.Library()


@register.filter
def clp(monto):
    """59000 -> '$59.000'."""
    return '$' + f'{int(monto):,}'.replace(',', '.')
