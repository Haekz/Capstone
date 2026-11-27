"""Filtro de la pagina de error de Django (DEBUG=True) y de los correos de error.

SafeExceptionReporterFilter ya oculta los settings cuyo nombre contiene API,
AUTH, TOKEN, KEY, SECRET, PASS, SIGNATURE o HTTP_COOKIE. Se agregan URI y
DATABASE_URL (cadenas de conexion que traen usuario y clave: DATABASE_URL se
mostraba entera, con la clave de PostgreSQL) y CLAVE (SITIO_CLAVE).

Ademas, el filtro original no oculta los datos marcados con
@sensitive_post_parameters ni @sensitive_variables cuando DEBUG=True, y la
pagina de error mostraria la clave enviada en /puerta/. Aqui se ocultan
siempre.
"""

import re

from django.views.debug import SafeExceptionReporterFilter


class FiltroReporteErrores(SafeExceptionReporterFilter):
    hidden_settings = re.compile(
        'API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE|URI|URL|CLAVE',
        flags=re.I,
    )

    def is_active(self, request):
        return True
