"""Cifrado simetrico (Fernet) para datos sensibles guardados en la base de datos."""

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def cifrador(proposito, clave=None):
    """Fernet con ``clave`` o, si no hay, una derivada de SECRET_KEY y ``proposito``.

    Cada proposito tiene su propia clave: lo cifrado para uno no se lee con otro.
    Si SECRET_KEY (o ``clave``) cambia, lo ya cifrado deja de poder leerse.
    """
    clave = clave or base64.urlsafe_b64encode(
        hashlib.sha256(f'{proposito}:{settings.SECRET_KEY}'.encode()).digest())
    return Fernet(clave)
