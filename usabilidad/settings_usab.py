"""Settings para pruebas de usabilidad: base SQLite aparte, correo a consola."""
import os

os.environ.setdefault('SECRET_KEY', 'solo-pruebas-usabilidad')
os.environ.pop('DATABASE_URL', None)

from lbwus.settings import *  # noqa: E402,F401,F403
from lbwus.settings import BASE_DIR  # noqa: E402

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'usab.sqlite3'}}
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEBUG = True
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
