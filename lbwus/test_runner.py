"""Runner de pruebas: lo que en produccion da Railway y en pruebas no existe.

- Estaticos sin manifiesto: ``CompressedManifestStaticFilesStorage`` exige haber
  corrido collectstatic y, sin el, cada pagina da error. Que todo archivo
  referenciado exista lo comprueba ``tests.test_configuracion_produccion``.
- ``DOCUMENTOS_CLAVE`` nueva en cada corrida: las pruebas corren con DEBUG=False,
  donde es obligatoria (apoderados/documentos.py).
- Hasher MD5: crear miles de usuarios con PBKDF2 hacia lenta la suite. Solo en pruebas;
  ninguna verifica el algoritmo (PR #107, Franco).
- ``MEDIA_ROOT`` temporal y borrado al final: las pruebas no ensucian ``media/`` (PR #107).
"""

import shutil
import tempfile

from cryptography.fernet import Fernet
from django.conf import settings
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class RunnerLBWUS(DiscoverRunner):

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media = tempfile.mkdtemp(prefix='lbwus_test_media_')
        self._ajustes = override_settings(
            STORAGES={
                **settings.STORAGES,
                'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
            },
            DOCUMENTOS_CLAVE=settings.DOCUMENTOS_CLAVE or Fernet.generate_key().decode(),
            PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
            MEDIA_ROOT=self._media,
        )
        self._ajustes.enable()

    def teardown_test_environment(self, **kwargs):
        self._ajustes.disable()
        shutil.rmtree(self._media, ignore_errors=True)
        super().teardown_test_environment(**kwargs)
