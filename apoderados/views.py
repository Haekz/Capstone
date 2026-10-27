"""Fase 1a: registro del apoderado, confirmacion de correo y revision de identidad.

Permisos con los decoradores de rol existentes. El portal del apoderado solo
muestra el estado de su cuenta: no abre nada de alumnos, profesores ni admin.
"""

import time

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.encoding import DjangoUnicodeDecodeError, force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from alumnos.decorators import admin_required, apoderado_required
from alumnos.models import Tutor
from alumnos.roles import APODERADO, abrir_sesion_rol, redirigir_a_portal, rol_en_sesion

from .correo import enviar_confirmacion
from .forms import RegistroApoderadoForm, RevisionIdentidadForm
from .models import Apoderado, RevisionIdentidad
from .tokens import token_correo

ESPERA_REENVIO = 60  # segundos entre correos de confirmacion
CLAVE_ENVIO = 'apoderado_correo_enviado'


def _apoderado_en_sesion(request):
    return get_object_or_404(Apoderado.objects.select_related('user'),
                             id_apoderado=request.session[APODERADO.clave_sesion])


def _segundos_para_reenviar(request):
    falta = ESPERA_REENVIO - (time.time() - request.session.get(CLAVE_ENVIO, 0))
    return max(0, int(falta))


def _enviar(request, apoderado):
    if enviar_confirmacion(request, apoderado):
        request.session[CLAVE_ENVIO] = time.time()
        messages.success(request, f'Te enviamos un enlace a {apoderado.user.email} para confirmar tu correo.')
    else:
        messages.error(request, 'No pudimos enviar el correo de confirmación. Inténtalo de nuevo en unos minutos.')


@sensitive_post_parameters('password', 'confirmar_password')
@never_cache
def registro(request):
    rol = rol_en_sesion(request)
    if rol is not None:
        return redirigir_a_portal(rol)
    form = RegistroApoderadoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        apoderado = form.save()
        auth_login(request, apoderado.user, backend='alumnos.backends.RutOrEmailBackend')
        abrir_sesion_rol(request, APODERADO, apoderado)
        _enviar(request, apoderado)
        return redirect(APODERADO.ruta_portal)
    return render(request, 'apoderados/registro.html', {'form': form})


@never_cache
def confirmar_correo(request, uidb64, token):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
    except (ValueError, TypeError, OverflowError, DjangoUnicodeDecodeError):
        user_id = None
    apoderado = (Apoderado.objects.select_related('user').filter(user_id=user_id).first()
                 if user_id and user_id.isdigit() else None)
    if apoderado is None or not token_correo.check_token(apoderado.user, token):
        return render(request, 'apoderados/enlace_invalido.html', status=400)
    apoderado.confirmar_correo()
    messages.success(request, 'Correo confirmado. Ahora un administrador revisará tu identidad.')
    return redirect(APODERADO.ruta_portal if request.session.get(APODERADO.clave_sesion) else 'login')


@never_cache
@apoderado_required
def portal(request):
    apoderado = _apoderado_en_sesion(request)
    return render(request, 'apoderados/portal.html', {
        'apoderado': apoderado,
        'revision': apoderado.ultima_revision,
        'espera': _segundos_para_reenviar(request),
    })


@require_POST
@apoderado_required
def reenviar(request):
    apoderado = _apoderado_en_sesion(request)
    if apoderado.estado != Apoderado.CORREO_PENDIENTE:
        messages.info(request, 'Tu correo ya está confirmado.')
    elif _segundos_para_reenviar(request):
        messages.error(request, 'Espera un minuto antes de pedir otro enlace.')
    else:
        _enviar(request, apoderado)
    return redirect(APODERADO.ruta_portal)


def logout_apoderado(request):
    auth_logout(request)
    return redirect('home')


@never_cache
@admin_required
def revision(request):
    return render(request, 'apoderados/revision.html', {
        'admin': get_object_or_404(Tutor, id_tutor=request.session['admin_id']),
        'pendientes': Apoderado.objects.filter(estado=Apoderado.REVISION_PENDIENTE).select_related('user'),
        'historial': RevisionIdentidad.objects.select_related('apoderado__user', 'administrador')[:50],
        'documentos': RevisionIdentidad.DOCUMENTOS,
        'canales': RevisionIdentidad.CANALES,
    })


@require_POST
@admin_required
def revisar(request, id_apoderado):
    # Solo se revisa quien confirmo su correo y aun no tiene decision.
    apoderado = get_object_or_404(Apoderado.objects.select_related('user'),
                                  pk=id_apoderado, estado=Apoderado.REVISION_PENDIENTE)
    form = RevisionIdentidadForm(request.POST)
    if form.is_valid():
        revision = form.save(commit=False)
        apoderado.aplicar_revision(revision, request.user)
        messages.success(request, f'{apoderado.nombre}: {apoderado.get_estado_display().lower()}.')
    else:
        messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('apoderados_revision')
