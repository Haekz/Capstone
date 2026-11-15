"""Runner de pruebas: lo que en produccion da Railway y en pruebas no existe.

- Estaticos sin manifiesto: ``CompressedManifestStaticFilesStorage`` exige haber
  corrido collectstatic y, sin el, cada pagina da error. Que todo archivo
  referenciado exista lo comprueba ``tests.test_configuracion_produccion``.
- ``DOCUMENTOS_CLAVE`` nueva en cada corrida: las pruebas corren con DEBUG=False,
  donde es obligatoria (apoderados/documentos.py).
- ``VIDEOS_A_LA_VENTA`` prendida: en Railway la da MONGODB_URI; aqui Mongo es mongomock (comunidad/tests/base.py).
  tests.test_videos_sin_mongo la apaga para probar que sin Mongo no se cobran videos.
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
            VIDEOS_A_LA_VENTA=True,
        )
        self._ajustes.enable()

    def teardown_test_environment(self, **kwargs):
        self._ajustes.disable()
        super().teardown_test_environment(**kwargs)
