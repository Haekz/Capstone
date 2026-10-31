"""Enlaces firmados del modulo: confirmar correos e invitar al apoderado.

Confirmaciones: reutilizan el generador de Django de "olvide mi contrasena",
firmado y con vencimiento (PASSWORD_RESET_TIMEOUT). El hash incluye la fecha de
confirmacion y el correo: el enlace deja de servir al usarse o si cambia el correo.

Invitaciones: el enlace firma el id; la vigencia (7 dias, un solo uso, solo la
ultima) la decide la base de datos.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import signing
from django.utils.encoding import DjangoUnicodeDecodeError, force_str
from django.utils.http import urlsafe_base64_decode

from .models import Invitacion

SAL_INVITACION = 'apoderados.invitacion'


def user_id_de_uid(uidb64):
    """Id de usuario del enlace, o None si viene alterado."""
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
    except (ValueError, TypeError, OverflowError, DjangoUnicodeDecodeError):
        return None
    return user_id if user_id.isdigit() else None


def firmar_invitacion(invitacion):
    return signing.dumps(invitacion.pk, salt=SAL_INVITACION)


def invitacion_vigente(token):
    """La invitacion del enlace, o None si es falsa, vencida, usada o reemplazada."""
    try:
        pk = signing.loads(token, salt=SAL_INVITACION)
    except signing.BadSignature:
        return None
    invitacion = Invitacion.objects.select_related('solicitud__alumno__user').filter(pk=pk).first()
    return invitacion if invitacion is not None and invitacion.vigente() else None


class _TokenCorreo(PasswordResetTokenGenerator):
    def confirmado(self, user):
        raise NotImplementedError

    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{user.email}{self.confirmado(user)}{timestamp}'


class TokenCorreoApoderado(_TokenCorreo):
    key_salt = 'apoderados.tokens.TokenCorreoApoderado'

    def confirmado(self, user):
        return user.perfil_apoderado.correo_verificado


class TokenCorreoAdolescente(_TokenCorreo):
    key_salt = 'apoderados.tokens.TokenCorreoAdolescente'

    def confirmado(self, user):
        return user.perfil_alumno.solicitud_apoderado.correo_confirmado


token_correo = TokenCorreoApoderado()
token_correo_adolescente = TokenCorreoAdolescente()
