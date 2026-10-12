"""Puerta con clave para todo el sitio.

Mientras el sitio esta en pruebas, se define la variable de entorno
SITIO_CLAVE y cada visitante debe ingresarla una vez en /puerta/. Sin la
variable (o vacia), la puerta no hace nada.
"""

import hmac

from django import forms
from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

SESION_PUERTA = 'puerta_ok'


def destino_seguro(destino):
    """Devuelve `destino` solo si es una ruta interna; si no, '/'.

    Evita que /puerta/?next=https://otro-sitio.cl mande al visitante fuera.
    allowed_hosts=None solo acepta rutas sin dominio (rechaza tambien //otro).
    """
    if (destino and destino.startswith('/')
            and url_has_allowed_host_and_scheme(destino, allowed_hosts=None)):
        return destino
    return '/'


def _rutas_exentas():
    # Se calculan en cada peticion: reverse() no se puede usar al importar.
    return {
        'exactas': {reverse('puerta'), reverse('confirmacion')},
        # Webpay vuelve a confirmacion desde su dominio, sin pasar por la puerta.
        'prefijos': (settings.STATIC_URL,),
    }


class PuertaSitioMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.SITIO_CLAVE:
            return self.get_response(request)

        exentas = _rutas_exentas()
        ruta = request.path_info
        if ruta in exentas['exactas'] or ruta.startswith(exentas['prefijos']):
            return self.get_response(request)

        if not request.session.get(SESION_PUERTA):
            url = reverse('puerta') + '?' + urlencode({'next': request.get_full_path()})
            return HttpResponseRedirect(url)

        response = self.get_response(request)
        # auth_logout() hace session.flush() y borraria la marca: sin esto,
        # cada cierre de sesion volveria a pedir la clave del sitio.
        if not request.session.get(SESION_PUERTA):
            request.session[SESION_PUERTA] = True
        return response


class PuertaForm(forms.Form):
    # strip=False: la clave se compara tal cual, con espacios incluidos.
    clave = forms.CharField(
        label='Clave del sitio', strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'puerta-input', 'autocomplete': 'current-password',
            'autofocus': True, 'placeholder': 'Clave del sitio',
        }),
    )

    @sensitive_variables('clave')
    def clean_clave(self):
        clave = self.cleaned_data['clave']
        if not hmac.compare_digest(clave.encode('utf-8'),
                                   settings.SITIO_CLAVE.encode('utf-8')):
            raise forms.ValidationError('Clave incorrecta')
        return clave


@never_cache
@sensitive_post_parameters('clave')
def puerta(request):
    destino = destino_seguro(request.POST.get('next') or request.GET.get('next'))

    if not settings.SITIO_CLAVE or request.session.get(SESION_PUERTA):
        return HttpResponseRedirect(destino)

    form = PuertaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        request.session[SESION_PUERTA] = True
        return HttpResponseRedirect(destino)

    return render(request, 'puerta.html', {'form': form, 'next': destino})
