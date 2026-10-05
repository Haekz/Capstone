"""Que pasa cuando alguien vuelve de Google.

Antes allauth creaba un CustomUser vacio (sin RUT ni perfil) y lo dejaba
logueado, pero los portales piden un perfil Alumno/Profesor/Tutor
(alumnos/roles.py), asi que la persona quedaba afuera sin explicacion.

Ahora, con el correo VERIFICADO que entrega Google:

1. Si el correo es de una cuenta LBWUS con perfil -> entra a su portal
   (y la cuenta Google queda vinculada para la proxima vez).
2. Si no hay cuenta (o es una cuenta huerfana sin perfil) -> NO se crea nada:
   se envia un codigo al correo y se piden los datos que faltan
   (ver alumnos/google_views.py). Sin esos datos no hay cuenta funcional.
"""

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.shortcuts import redirect

from . import codigo_google
from .models import Alumno, Profesor, Tutor
from .roles import abrir_sesion_rol, redirigir_a_portal, resolver_rol

BACKEND_SESION = 'django.contrib.auth.backends.ModelBackend'


def correo_verificado(sociallogin):
    """Primer correo que Google marca como verificado, o None."""
    for direccion in sociallogin.email_addresses:
        if direccion.verified and direccion.email:
            return direccion.email.strip().lower()
    return None


def buscar_usuario_por_correo(correo):
    """Usuario dueno de ``correo`` (en CustomUser o en algun perfil), o None."""
    User = get_user_model()
    user = User.objects.filter(email__iexact=correo).first()
    if user is not None:
        return user
    for modelo in (Alumno, Profesor, Tutor):
        perfil = modelo.objects.filter(correo_electronico__iexact=correo).select_related('user').first()
        if perfil is not None and perfil.user is not None:
            return perfil.user
    return None


def entrar_al_portal(request, user):
    """Abre la sesion del rol del usuario y devuelve el redirect a su portal."""
    rol, perfil = resolver_rol(user)
    auth_login(request, user, backend=BACKEND_SESION)
    abrir_sesion_rol(request, rol, perfil)
    return redirigir_a_portal(rol)


class LbwusSocialAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        correo = correo_verificado(sociallogin)
        if correo is None:
            messages.error(request, 'Google no confirmó tu correo. Usa otra cuenta o entra con tu RUT.')
            raise ImmediateHttpResponse(redirect('login'))

        # sociallogin.user ya viene cargado si esta cuenta Google estaba vinculada.
        user = sociallogin.user if sociallogin.is_existing else buscar_usuario_por_correo(correo)
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
