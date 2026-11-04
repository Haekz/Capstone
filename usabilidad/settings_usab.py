"""Settings para pruebas de usabilidad: base PostgreSQL aparte, correo a consola.

La base de la demo es USAB_DATABASE_URL (una base distinta de la real, p. ej. .../lbwus_usab).
"""
import os

os.environ.setdefault('SECRET_KEY', 'solo-pruebas-usabilidad')
if 'USAB_DATABASE_URL' not in os.environ:
    raise RuntimeError('Define USAB_DATABASE_URL con una base PostgreSQL aparte para la demo de usabilidad.')
# La demo nunca usa la DATABASE_URL real: se le pone la de la demo antes de cargar los settings.
os.environ['DATABASE_URL'] = os.environ['USAB_DATABASE_URL']

from lbwus.settings import *  # noqa: E402,F401,F403

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEBUG = True
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
