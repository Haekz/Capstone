"""Pantallas del registro con Google: 1) codigo por correo, 2) completar datos.

Se llega aqui solo desde LbwusSocialAdapter.pre_social_login, que deja en la
sesion el correo verificado por Google (ver alumnos/codigo_google.py).
"""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import codigo_google
from .google_adapter import buscar_usuario_por_correo, entrar_al_portal
from .google_forms import CompletarRegistroGoogleForm
from .roles import resolver_rol


def _sin_registro_en_curso(request):
    messages.error(request, 'Tu sesión de registro expiró. Vuelve a entrar con Google.')
    return redirect('login')


@never_cache
def google_verificar(request):
    if codigo_google.pendiente(request) is None:
        return _sin_registro_en_curso(request)
    if codigo_google.verificado(request):
        return redirect('google_completar')

    error = None
    if request.method == 'POST':
        error = codigo_google.verificar(request, request.POST.get('codigo'))
        if error is None:
            return redirect('google_completar')

    return render(request, 'registration/google_verificar.html', {
        'correo': codigo_google.correo(request),
        'error': error,
        'espera': codigo_google.segundos_para_reenviar(request),
    })


@require_POST
def google_reenviar(request):
    if codigo_google.pendiente(request) is None:
        return _sin_registro_en_curso(request)
    if codigo_google.segundos_para_reenviar(request) > 0:
        messages.warning(request, 'Espera un momento antes de pedir otro código.')
    elif codigo_google.enviar(request):
        messages.success(request, 'Te enviamos un código nuevo.')
    else:
        messages.error(request, 'No pudimos enviar el código. Intenta de nuevo en un momento.')
    return redirect('google_verificar')


def _cuenta_a_completar(sociallogin, correo):
    """Cuenta sin perfil que ya existe para esta persona, o None.

    Pasa con quienes entraron con Google antes de este arreglo: allauth les
    creo un usuario vacio. Se reutiliza en vez de duplicarlo.
    """
    if sociallogin.is_existing:
        return sociallogin.user
    user = buscar_usuario_por_correo(correo)
    if user is not None and resolver_rol(user)[0] is None:
        return user
    return None


@never_cache
def google_completar(request):
    if codigo_google.pendiente(request) is None:
        return _sin_registro_en_curso(request)
    if not codigo_google.verificado(request):
        return redirect('google_verificar')

    datos = codigo_google.pendiente(request)
    correo = datos['correo']
    sociallogin = codigo_google.sociallogin(request)
    existente = _cuenta_a_completar(sociallogin, correo)

    form = CompletarRegistroGoogleForm(
        request.POST or None,
        correo=correo,
        user_existente=existente,
        initial={'nombre': datos.get('nombre', '')},
    )
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        if not sociallogin.is_existing:
            sociallogin.connect(request, user)
        codigo_google.terminar(request)
        messages.success(request, '¡Listo! Tu cuenta quedó creada.')
        return entrar_al_portal(request, user)

    return render(request, 'registration/google_completar.html', {'form': form, 'correo': correo})
