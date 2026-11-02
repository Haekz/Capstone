"""Datos del Buzon del panel del profesor (paso C1b). Solo nombres de pila (privacidad)."""

from . import servicio
from .models import Conversacion

MAX_VISIBLES = 200


def contexto_profesor(profesor, activa_id):
    """Sus conversaciones y, si pidio una (?c=), sus mensajes; abrirla la marca como leida."""
    conversaciones = list(Conversacion.objects.filter(profesor=profesor).select_related('alumno__user')
                          .bandeja(profesor.user, 'visto_profesor'))
    activa = next((c for c in conversaciones if str(c.pk) == str(activa_id)), None)
    mensajes = []
    if activa:
        recientes = activa.mensajes.order_by('-creado', '-pk')[:MAX_VISIBLES]
        mensajes = list(recientes)[::-1]
        servicio.marcar_visto(profesor.user, activa)
        activa.sin_leer = False
    return {'buzon': conversaciones, 'buzon_activa': activa, 'buzon_mensajes': mensajes}
