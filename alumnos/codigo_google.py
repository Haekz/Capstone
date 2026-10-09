"""Codigo de seguridad para registrarse con Google.

Todo vive en la sesion (nada en la base hasta que la cuenta esta completa):
el correo verificado, el codigo hasheado, su vencimiento, los intentos y el
SocialLogin serializado para vincular la cuenta Google al final.
"""

import secrets
import time

from allauth.socialaccount.models import SocialLogin
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail

CLAVE = 'registro_google'
ESPERA_REENVIO = 60  # segundos


def _datos(request):
    return request.session.get(CLAVE)


def _guardar(request, datos):
    request.session[CLAVE] = datos
    request.session.modified = True


def iniciar(request, correo, sociallogin):
    _guardar(request, {
        'correo': correo,
        'nombre': (sociallogin.account.extra_data or {}).get('name', ''),
        'sociallogin': sociallogin.serialize(),
        'verificado': False,
    })


def pendiente(request):
    """Datos del registro en curso, o None si no hay ninguno."""
    return _datos(request)


def correo(request):
    datos = _datos(request)
    return datos['correo'] if datos else None


def enviar(request):
    """Genera un codigo nuevo y lo manda por correo. True si salio."""
    datos = _datos(request)
    if not datos:
        return False
    codigo = f'{secrets.randbelow(10**6):06d}'
    minutos = settings.CODIGO_GOOGLE_MINUTOS
    datos.update({
        'codigo': make_password(codigo),
        'vence': time.time() + minutos * 60,
        'intentos': 0,
        'enviado': time.time(),
    })
    _guardar(request, datos)
    try:
        send_mail(
            'Tu código de seguridad LBWUS',
            f'Tu código para terminar el registro en LBWUS es: {codigo}\n\n'
            f'Vence en {minutos} minutos. Si no fuiste tú, ignora este correo.',
            settings.DEFAULT_FROM_EMAIL,
            [datos['correo']],
        )
    except Exception:  # SMTP caido, timeout, credenciales: el usuario puede reenviar
        return False
    return True


def segundos_para_reenviar(request):
    datos = _datos(request) or {}
    falta = ESPERA_REENVIO - (time.time() - datos.get('enviado', 0))
    return max(0, int(falta))


def verificar(request, codigo):
    """Devuelve None si el codigo es correcto, o el mensaje de error."""
    datos = _datos(request)
    if not datos or 'codigo' not in datos:
        return 'Pide un código nuevo.'
    if time.time() > datos['vence']:
        return 'El código venció. Pide uno nuevo.'
    if datos['intentos'] >= settings.CODIGO_GOOGLE_INTENTOS:
        return 'Demasiados intentos. Pide un código nuevo.'
    if not check_password((codigo or '').strip(), datos['codigo']):
        datos['intentos'] += 1
        _guardar(request, datos)
        return 'El código no es correcto.'
    datos['verificado'] = True
    datos.pop('codigo')  # un codigo sirve una sola vez
    _guardar(request, datos)
    return None


def verificado(request):
    datos = _datos(request)
    return bool(datos and datos.get('verificado'))


def sociallogin(request):
    return SocialLogin.deserialize(_datos(request)['sociallogin'])


def terminar(request):
    request.session.pop(CLAVE, None)
