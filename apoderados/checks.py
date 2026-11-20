"""Chequeos de despliegue de apoderados: corren con ``manage.py check --deploy``."""

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def documentos_clave(app_configs, **kwargs):
    """Sin DOCUMENTOS_CLAVE valida, en produccion no se suben ni se ven documentos."""
    if not settings.DOCUMENTOS_CLAVE:
        return [Error('Falta DOCUMENTOS_CLAVE.', id='apoderados.E001',
                      hint='Definela en Railway antes de desplegar. Ver docs/CONFIGURACION_PRODUCCION.md.')]
    try:
        Fernet(settings.DOCUMENTOS_CLAVE)
    except ValueError:
        return [Error('DOCUMENTOS_CLAVE no es una clave Fernet valida.', id='apoderados.E002',
                      hint='Generala con Fernet.generate_key(). Ver docs/CONFIGURACION_PRODUCCION.md.')]
    return []
