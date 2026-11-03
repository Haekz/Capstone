"""Nombre de la sala de Jitsi de cada clase.

Antes era ``lbwus-clase-privada-<id>``: cualquiera podia probar numeros y entrar. Ahora es una firma HMAC con la clave
secreta del proyecto: no se puede deducir del id, es siempre la misma para la misma clase (profesor y alumno coinciden)
y no hace falta guardarla en la base. Reduce el riesgo, no lo elimina: la sala sigue siendo del servidor publico de
Jitsi y quien consiga el enlace puede entrar.
"""

import hashlib
import hmac

from django.conf import settings


def nombre_sala(clase_id):
    firma = hmac.new(settings.SECRET_KEY.encode(), f'sala-clase-{clase_id}'.encode(), hashlib.sha256).hexdigest()
    return f'lbwus-{firma[:24]}'
