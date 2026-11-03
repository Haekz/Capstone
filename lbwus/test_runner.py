"""Runner de pruebas: lo que en produccion da Railway y en pruebas no existe.

- Estaticos sin manifiesto: ``CompressedManifestStaticFilesStorage`` exige haber
  corrido collectstatic y, sin el, cada pagina da error. Que todo archivo
  referenciado exista lo comprueba ``tests.test_configuracion_produccion``.
- ``DOCUMENTOS_CLAVE`` nueva en cada corrida: las pruebas corren con DEBUG=False,
  donde es obligatoria (apoderados/documentos.py).
"""

from cryptography.fernet import Fernet
from django.conf import settings
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class RunnerLBWUS(DiscoverRunner):

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._ajustes = override_settings(
            STORAGES={
                **settings.STORAGES,
                'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
            },
            DOCUMENTOS_CLAVE=settings.DOCUMENTOS_CLAVE or Fernet.generate_key().decode(),
        )
        self._ajustes.enable()

    def teardown_test_environment(self, **kwargs):
        self._ajustes.disable()
        super().teardown_test_environment(**kwargs)
