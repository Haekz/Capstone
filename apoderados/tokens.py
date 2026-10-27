"""Enlace para confirmar el correo del apoderado.

Reutiliza el generador de Django de "olvide mi contrasena": firmado y con
vencimiento (PASSWORD_RESET_TIMEOUT). El hash incluye ``correo_verificado`` y
el correo, asi que el enlace deja de servir al usarse o si cambia el correo.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class TokenCorreoApoderado(PasswordResetTokenGenerator):
    key_salt = 'apoderados.tokens.TokenCorreoApoderado'

    def _make_hash_value(self, user, timestamp):
        perfil = user.perfil_apoderado
        return f'{user.pk}{user.email}{perfil.correo_verificado}{timestamp}'


token_correo = TokenCorreoApoderado()
