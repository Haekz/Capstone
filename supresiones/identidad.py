"""Verificar que quien pide eliminar la cuenta es su dueno (respuesta legal, E3 paso 2: identidad proporcional).

No se pide carnet: la persona ya tiene sesion abierta, y ademas debe abrir un enlace firmado que solo llega al
correo registrado (vale 24 h). Sirve igual para quien entra con contrasena que para quien entra con Google.
El enlace no guarda nada: lleva solo el id del usuario, firmado.
"""

from datetime import timedelta

from django.core import signing
from django.core.exceptions import ValidationError
from django.urls import reverse

from . import correo

SAL = 'supresiones.confirmar'
VIGENCIA = timedelta(hours=24)


def pedir(request, user):
    """Manda el enlace de confirmacion al correo registrado. False si no hay correo o no salio."""
    if not user.email:
        return False
    token = signing.dumps({'usuario': user.pk}, salt=SAL)
    return correo.enlace_de_confirmacion(
        user, request.build_absolute_uri(reverse('confirmar_eliminar_cuenta', args=[token])),
        int(VIGENCIA.total_seconds() // 3600))


def verificar(token, user):
    """ValidationError si el enlace es falso, vencio o es de otra cuenta."""
    try:
        datos = signing.loads(token, salt=SAL, max_age=VIGENCIA)
    except signing.BadSignature:  # incluye SignatureExpired
        raise ValidationError('El enlace no es válido o venció. Pide uno nuevo.')
    if datos.get('usuario') != user.pk:
        raise ValidationError('Este enlace es de otra cuenta. Entra con la cuenta que pidió la eliminación.')
