"""Aviso previo al chat (respuesta legal del 02-nov, E5): que se hace con los mensajes y con los datos.

Los plazos salen de las mismas constantes que aplican el borrado y la revision (retencion.py y revision.py), no se
escriben a mano en los HTML: si cambian, el aviso cambia con ellos.
"""

from django import template

from mensajes import retencion, revision

register = template.Library()


def _plazos():
    return {'dias': retencion.DIAS_SIN_ACTIVIDAD, 'meses': revision.MESES_REVISION}


@register.inclusion_tag('mensajes/_aviso.html')
def aviso_mensajes(rol, conversacion_activa=None):
    """Aviso para quien usa el chat. ``rol``: 'alumno', 'profesor' o 'apoderado'. Va desplegado mientras no haya
    una conversacion abierta (antes de usar el chat) y plegado dentro de ella."""
    return {**_plazos(), 'rol': rol, 'abierto': conversacion_activa is None}


@register.inclusion_tag('mensajes/_aviso_menor.html')
def aviso_mensajes_menor():
    """Version en lenguaje simple para el estudiante menor, que no usa el chat pero tiene derecho a saber."""
    return _plazos()
