"""Filtro de la pagina de error de Django (DEBUG=True) y de los correos de error.

SafeExceptionReporterFilter ya oculta los settings cuyo nombre contiene API,
AUTH, TOKEN, KEY, SECRET, PASS, SIGNATURE o HTTP_COOKIE. Se agregan URI
(MONGODB_URI trae usuario y clave de Atlas) y CLAVE (SITIO_CLAVE).

Ademas, el filtro original no oculta los datos marcados con
@sensitive_post_parameters ni @sensitive_variables cuando DEBUG=True, y la
pagina de error mostraria la clave enviada en /puerta/. Aqui se ocultan
siempre.
"""

import re

from django.views.debug import SafeExceptionReporterFilter


class FiltroReporteErrores(SafeExceptionReporterFilter):
    hidden_settings = re.compile(
        'API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE|URI|CLAVE',
        flags=re.I,
    )

    def is_active(self, request):
        return True
