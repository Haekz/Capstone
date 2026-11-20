"""Cuantas notificaciones sin leer tiene el usuario, para el contador de la campanita."""

from .models import Notificacion


def sin_leer(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    return {'notificaciones_sin_leer': Notificacion.objects.filter(usuario=user, leida=False).count()}
