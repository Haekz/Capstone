"""{% load campana %} ... {% avisos_campana as avisos %}: los avisos de quien abre la pagina."""

from django import template

from admin_portal import avisos

register = template.Library()


@register.simple_tag(takes_context=True)
def avisos_campana(context):
    request = context.get('request')
    return avisos.para(request) if request is not None else []
