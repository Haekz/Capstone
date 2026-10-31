"""Que pasa cuando alguien vuelve de Google.

Con el correo VERIFICADO que entrega Google:

1. Si el correo es de una cuenta LBWUS con perfil -> entra a su portal
   (y la cuenta Google queda vinculada para la proxima vez).
2. Si no hay cuenta (o es una cuenta huerfana sin perfil) -> NO se crea nada:
   se envia un codigo al correo y se piden los datos que faltan
   (ver alumnos/google_views.py). Sin esos datos no hay cuenta funcional.
3. Si la cuenta existe pero esta desactivada (is_active = False) -> se rechaza
   el acceso de inmediato.
"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.shortcuts import redirect

from . import codigo_google
from .roles import abrir_sesion_rol, redirigir_a_portal, resolver_rol

BACKEND_SESION = 'django.contrib.auth.backends.ModelBackend'


def correo_verificado(sociallogin):
    """Primer correo que Google marca como verificado, o None."""
    for direccion in sociallogin.email_addresses:
        if direccion.verified and direccion.email:
            return direccion.email.strip().lower()
    return None


def buscar_usuario_por_correo(correo):
    """Usuario dueno de ``correo``, o None.

    El correo vive solo en CustomUser.email: los perfiles ya no lo guardan.
    """
    return get_user_model().objects.filter(email__iexact=correo).first()


def entrar_al_portal(request, user):
    """Abre la sesion del rol del usuario y devuelve el redirect a su portal."""
    if not getattr(user, 'is_active', True):
        messages.error(
            request,
            'Tu cuenta se encuentra desactivada por la administración. '
            'Comunícate con soporte si consideras que es un error.'
        )
        return redirect('login')

    rol, perfil = resolver_rol(user)
    auth_login(request, user, backend=BACKEND_SESION)
    abrir_sesion_rol(request, rol, perfil)
    return redirigir_a_portal(rol)


class LbwusAccountAdapter(DefaultAccountAdapter):
    """
    Adaptador de cuentas locales para allauth.
    Deshabilita el endpoint público de registro directo (/accounts/signup/)
    para que nadie pueda registrar cuentas huérfanas sin perfil ni validación de RUT.
    """

    def is_open_for_signup(self, request):
        return False


class LbwusSocialAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        correo = correo_verificado(sociallogin)
        if correo is None:
            messages.error(request, 'Google no confirmó tu correo. Usa otra cuenta o entra con tu RUT.')
            raise ImmediateHttpResponse(redirect('login'))

        # sociallogin.user ya viene cargado si esta cuenta Google estaba vinculada.
        user = sociallogin.user if sociallogin.is_existing else buscar_usuario_por_correo(correo)

        # Las cuentas desactivadas no entran
        if user is not None and not user.is_active:
            messages.error(
                request,
                'Tu cuenta ha sido desactivada por la administración. '
                'Comunícate con soporte si crees que esto es un error.'
            )
            raise ImmediateHttpResponse(redirect('login'))

        rol, _ = resolver_rol(user) if user is not None else (None, None)

        if rol is not None:
            if not sociallogin.is_existing:
                sociallogin.connect(request, user)
            raise ImmediateHttpResponse(entrar_al_portal(request, user))

        # Cuenta nueva (o huerfana): primero confirmar el correo con un codigo.
        codigo_google.iniciar(request, correo=correo, sociallogin=sociallogin)
        enviado = codigo_google.enviar(request)
        if not enviado:
            messages.error(request, 'No pudimos enviar el código a tu correo. Intenta reenviarlo en un momento.')
        raise ImmediateHttpResponse(redirect('google_verificar'))

    def is_open_for_signup(self, request, sociallogin):
        # Nunca dejar que allauth cree cuentas por su cuenta (pre_social_login
        # ya corto el flujo antes; esto es el cinturon de seguridad).
        return False
