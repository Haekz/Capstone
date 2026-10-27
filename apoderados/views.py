"""Apoderados: registro, confirmacion de correo, vinculos con estudiantes y revisiones.

Permisos con los decoradores de rol existentes. El portal del apoderado solo
muestra su cuenta y sus vinculos: no abre nada de alumnos, profesores ni admin.
"""

import time

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import DjangoUnicodeDecodeError, force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from alumnos.decorators import admin_required, apoderado_required
from alumnos.models import Tutor
from alumnos.roles import APODERADO, abrir_sesion_rol, redirigir_a_portal, rol_en_sesion

from .correo import enviar_confirmacion
from .forms import (ClaveEstudianteForm, RegistroApoderadoForm, RegistroEstudianteForm,
                    RevisionIdentidadForm, RevisionVinculoForm)
from .models import Apoderado, Revision, RevisionIdentidad, RevisionVinculo, Vinculo
from .tokens import token_correo

ESPERA_REENVIO = 60  # segundos entre correos de confirmacion
CLAVE_ENVIO = 'apoderado_correo_enviado'


def _apoderado_en_sesion(request):
    return get_object_or_404(Apoderado.objects.select_related('user'),
                             id_apoderado=request.session[APODERADO.clave_sesion])


def _formulario(request, form, **textos):
    return render(request, 'apoderados/formulario.html', {'form': form, **textos})


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
    return _formulario(
        request, form, titulo='Crea tu cuenta de apoderado', subtitulo='Tus datos', boton='Crear cuenta',
        volver_url=reverse('opcion_user'),
        intro=('Para madres, padres y adultos responsables de estudiantes menores de edad. Antes de '
               'habilitar tu cuenta confirmaremos tu correo y un administrador revisará tu identidad. '
               'No te pediremos subir documentos.'),
    )


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
        'vinculos': apoderado.vinculos.select_related('alumno__user').prefetch_related('revisiones'),
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


@sensitive_post_parameters('password', 'confirmar_password')
@never_cache
@apoderado_required
def registrar_estudiante(request):
    apoderado = _apoderado_en_sesion(request)
    if apoderado.estado != Apoderado.VERIFICADO:
        messages.error(request, 'Podrás registrar estudiantes cuando tu identidad esté verificada.')
        return redirect(APODERADO.ruta_portal)
    form = RegistroEstudianteForm(request.POST or None, apoderado=apoderado)
    if request.method == 'POST' and form.is_valid():
        vinculo = form.save()
        messages.success(request, f'Registramos a {vinculo.alumno.user.first_name}. Un administrador '
                                  'revisará su certificado de nacimiento para verificar el vínculo.')
        return redirect(APODERADO.ruta_portal)
    return _formulario(
        request, form, titulo='Registrar a un estudiante', subtitulo='Datos del estudiante',
        boton='Registrar estudiante', volver_url=reverse(APODERADO.ruta_portal),
        intro=('El estudiante entrará con su RUT y la contraseña que definas aquí. Hasta que verifiquemos '
               'el vínculo con su certificado de nacimiento, solo podrá ver el catálogo.'),
    )


@sensitive_post_parameters('new_password1', 'new_password2')
@never_cache
@apoderado_required
def clave_estudiante(request, id_vinculo):
    # Solo vinculos propios y no rechazados: un vinculo ajeno o rechazado responde 404.
    vinculo = get_object_or_404(
        Vinculo.objects.select_related('alumno__user'), pk=id_vinculo,
        apoderado_id=request.session[APODERADO.clave_sesion],
        estado__in=[Vinculo.PENDIENTE, Vinculo.VERIFICADO],
    )
    estudiante = vinculo.alumno.user
    form = ClaveEstudianteForm(estudiante, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Actualizamos la contraseña de {estudiante.first_name}.')
        return redirect(APODERADO.ruta_portal)
    return _formulario(
        request, form, titulo=f'Contraseña de {estudiante.first_name}', subtitulo='Nueva contraseña',
        boton='Guardar contraseña', volver_url=reverse(APODERADO.ruta_portal),
        intro=f'{estudiante.first_name} entra con su RUT ({estudiante.rut}) y esta contraseña.',
    )


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
        'vinculos_pendientes': (Vinculo.objects.filter(estado=Vinculo.PENDIENTE)
                                .select_related('apoderado__user', 'alumno__user')),
        'historial_vinculos': (RevisionVinculo.objects
                               .select_related('vinculo__apoderado__user', 'vinculo__alumno__user', 'administrador')[:50]),
        'documentos': RevisionIdentidad.DOCUMENTOS,
        'canales': Revision.CANALES,
    })


def _revisar(request, revisado, formulario, nombre):
    form = formulario(request.POST)
    if form.is_valid():
        revisado.aplicar_revision(form.save(commit=False), request.user)
        messages.success(request, f'{nombre}: {revisado.get_estado_display().lower()}.')
    else:
        messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('apoderados_revision')


@require_POST
@admin_required
def revisar(request, id_apoderado):
    # Solo se revisa quien confirmo su correo y aun no tiene decision.
    apoderado = get_object_or_404(Apoderado.objects.select_related('user'),
                                  pk=id_apoderado, estado=Apoderado.REVISION_PENDIENTE)
    return _revisar(request, apoderado, RevisionIdentidadForm, apoderado.nombre)


@require_POST
@admin_required
def revisar_vinculo(request, id_vinculo):
    # Solo vinculos pendientes de apoderados con identidad verificada.
    vinculo = get_object_or_404(Vinculo.objects.select_related('apoderado__user', 'alumno__user'),
                                pk=id_vinculo, estado=Vinculo.PENDIENTE,
                                apoderado__estado=Apoderado.VERIFICADO)
    return _revisar(request, vinculo, RevisionVinculoForm,
                    f'Vínculo {vinculo.apoderado.nombre} - {vinculo.alumno.user.first_name}')
