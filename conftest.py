"""Ajustes de pytest: los mismos que lbwus/test_runner.py da a `manage.py test`.

- Estaticos sin manifiesto (no hace falta collectstatic).
- DOCUMENTOS_CLAVE nueva en cada corrida, si el entorno no trae una.
- Marcadores por modulo: integracion_atlas y postgres (pytest.ini).
- Pruebas de bugs abiertos (@bug_qa, tests/bugs_qa.py) como xfail estricto.
"""

import pytest
from cryptography.fernet import Fernet
from django.conf import settings
from django.test.utils import override_settings

from tests import bugs_qa

bugs_qa.EN_PYTEST = True  # @bug_qa usa xfail(strict=True) y no unittest.expectedFailure

MARCADORES_POR_MODULO = {
    'comunidad/tests/test_atlas.py': 'integracion_atlas',
    'tests/test_concurrencia_inscripcion.py': 'postgres',
}


@pytest.fixture(scope='session', autouse=True)
def ajustes_lbwus(django_test_environment):
    ajustes = override_settings(
        STORAGES={
            **settings.STORAGES,
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
        DOCUMENTOS_CLAVE=settings.DOCUMENTOS_CLAVE or Fernet.generate_key().decode(),
    )
    ajustes.enable()
    yield
    ajustes.disable()


def pytest_collection_modifyitems(config, items):
    for item in items:
        ruta = item.nodeid.split('::', 1)[0]
        marcador = MARCADORES_POR_MODULO.get(ruta)
        if marcador:
            item.add_marker(getattr(pytest.mark, marcador))
