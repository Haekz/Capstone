"""Puerta con clave para todo el sitio.

Mientras el sitio esta en pruebas, se define la variable de entorno
SITIO_CLAVE y cada visitante debe ingresarla una vez en /puerta/.

Alternativa por correo: con SITIO_DOMINIOS_CORREO (ej. "duocuc.cl", varios
separados por coma) el visitante escribe su correo, recibe un codigo de 6
digitos y entra solo si el correo es de ese dominio. Tiene prioridad sobre
SITIO_CLAVE. Sin ninguna de las dos variables, la puerta no hace nada.
"""

import hmac
import secrets
import time

from django import forms
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

SESION_PUERTA = 'puerta_ok'
SESION_PENDIENTE = 'puerta_pendiente'
ESPERA_REENVIO = 60  # segundos
MINUTOS_CODIGO = 10
INTENTOS_CODIGO = 5


def puerta_activa():
    return bool(settings.SITIO_DOMINIOS_CORREO or settings.SITIO_CLAVE)


def modo_correo():
    return bool(settings.SITIO_DOMINIOS_CORREO)


def correo_permitido(correo):
    correo = (correo or '').strip().lower()
    if correo.count('@') != 1:
        return False
    local, dominio = correo.split('@')
    return bool(local) and dominio in settings.SITIO_DOMINIOS_CORREO


def _enviar_codigo(request, correo):
    """Genera un codigo nuevo, lo guarda hasheado en la sesion y lo manda."""
    codigo = f'{secrets.randbelow(10**6):06d}'
    request.session[SESION_PENDIENTE] = {
        'correo': correo,
        'codigo': make_password(codigo),
        'vence': time.time() + MINUTOS_CODIGO * 60,
        'intentos': 0,
        'enviado': time.time(),
    }
    try:
        send_mail(
            'Tu código de acceso a LBWUS',
            f'Tu código para entrar a LBWUS es: {codigo}\n\n'
            f'Vence en {MINUTOS_CODIGO} minutos. Si no fuiste tú, ignora este correo.',
            settings.DEFAULT_FROM_EMAIL,
            [correo],
        )
    except Exception:  # SMTP caido o mal configurado: se puede reenviar
        return False
    return True


def _verificar_codigo(request, codigo):
    """None si el codigo es correcto; si no, el mensaje de error."""
    datos = request.session.get(SESION_PENDIENTE)
    if not datos:
        return 'Pide un código nuevo.'
    if time.time() > datos['vence']:
        return 'El código venció. Pide uno nuevo.'
    if datos['intentos'] >= INTENTOS_CODIGO:
        return 'Demasiados intentos. Pide un código nuevo.'
    if not check_password((codigo or '').strip(), datos['codigo']):
        datos['intentos'] += 1
        request.session[SESION_PENDIENTE] = datos
        return 'El código no es correcto.'
    return None


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
        if not puerta_activa():
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


def _puerta_correo(request, destino):
    ctx = {'next': destino, 'modo_correo': True}
    pendiente = request.session.get(SESION_PENDIENTE)
    accion = request.POST.get('accion') if request.method == 'POST' else None

    if accion == 'cambiar':
        request.session.pop(SESION_PENDIENTE, None)
        pendiente = None
    elif accion == 'correo':
        correo = (request.POST.get('correo') or '').strip().lower()
        if not correo_permitido(correo):
            dominios = ', '.join('@' + d for d in settings.SITIO_DOMINIOS_CORREO)
            ctx['error'] = f'Solo pueden entrar correos {dominios}.'
            ctx['correo_valor'] = correo
        else:
            enviado = _enviar_codigo(request, correo)
            pendiente = request.session.get(SESION_PENDIENTE)
            if not enviado:
                ctx['error'] = 'No pudimos enviar el código. Intenta reenviarlo en un momento.'
    elif accion == 'reenviar' and pendiente:
        falta = ESPERA_REENVIO - (time.time() - pendiente.get('enviado', 0))
        if falta > 0:
            ctx['error'] = f'Espera {int(falta) + 1} segundos para pedir otro código.'
        elif not _enviar_codigo(request, pendiente['correo']):
            ctx['error'] = 'No pudimos enviar el código. Intenta de nuevo.'
        pendiente = request.session.get(SESION_PENDIENTE)
    elif accion == 'codigo' and pendiente:
        error = _verificar_codigo(request, request.POST.get('codigo'))
        if error is None:
            request.session.pop(SESION_PENDIENTE, None)
            request.session[SESION_PUERTA] = True
            return HttpResponseRedirect(destino)
        ctx['error'] = error
        pendiente = request.session.get(SESION_PENDIENTE)

    ctx['pendiente_correo'] = pendiente['correo'] if pendiente else None
    return render(request, 'puerta.html', ctx)


@never_cache
@sensitive_post_parameters('clave', 'codigo')
def puerta(request):
    destino = destino_seguro(request.POST.get('next') or request.GET.get('next'))

    if not puerta_activa() or request.session.get(SESION_PUERTA):
        return HttpResponseRedirect(destino)

    if modo_correo():
        return _puerta_correo(request, destino)

    form = PuertaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        request.session[SESION_PUERTA] = True
        return HttpResponseRedirect(destino)

    return render(request, 'puerta.html', {'form': form, 'next': destino})
