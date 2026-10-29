"""Apoderados: registro, confirmacion de correo, vinculos con estudiantes y revisiones.

Permisos con los decoradores de rol existentes. El portal del apoderado solo
muestra su cuenta y sus vinculos: no abre nada de alumnos, profesores ni admin.
Las revisiones son de soporte: solo el agente con el ticket ve documentos y decide.
"""

import time

from cryptography.fernet import InvalidToken
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from alumnos.decorators import alumno_required, alumno_sesion_required, apoderado_required, soporte_required
from alumnos.exceptions import InscripcionError
from alumnos.models import Inscripcion, PaqueteClases, SesionClase
from alumnos.roles import ALUMNO, APODERADO, abrir_sesion_rol, redirigir_a_portal, rol_en_sesion
from alumnos.services import InscripcionService
from alumnos.utils import es_menor
from alumnos.views import iniciar_compra_paquete  # unico inicio de Webpay para paquetes
from soporte.permisos import agente_en_sesion, lider_required, ticket_asignado, tickets_del_agente

from .correo import avisar_apoderados, enviar_confirmacion, enviar_confirmacion_adolescente, enviar_invitacion
from .documentos import con_marca_de_agua
from .forms import (VERSION_DECLARACION_VINCULO, AceptarInvitacionForm, ClaveEstudianteForm,
                    InvitacionForm, NuevaClaveForm, RegistroAdolescenteForm, RegistroApoderadoForm,
                    RegistroEstudianteForm, RevisionIdentidadForm, RevisionVinculoForm, RevocarVinculoForm)
from .models import (AccesoDocumento, Apoderado, CompraApoderado, Documento, RevisionIdentidad,
                     RevisionVinculo, Revocacion, SolicitudAdolescente, Vinculo)
from .permisos import debe_renovar_clave, vinculo_contratable
from .tokens import invitacion_vigente, token_correo, token_correo_adolescente, user_id_de_uid

ESPERA_REENVIO = 60  # segundos entre correos de confirmacion
CLAVE_ENVIO = 'apoderado_correo_enviado'
CLAVE_INVITACION = 'invitacion_pendiente'  # enlace guardado mientras el apoderado entra o se registra
BACKEND = 'alumnos.backends.RutOrEmailBackend'


def _apoderado_en_sesion(request):
    return get_object_or_404(Apoderado.objects.select_related('user'),
                             id_apoderado=request.session[APODERADO.clave_sesion])


def _solicitud_en_sesion(request):
    return get_object_or_404(SolicitudAdolescente.objects.select_related('alumno__user'),
                             alumno_id=request.session[ALUMNO.clave_sesion])


def _formulario(request, form, **textos):
    return render(request, 'apoderados/formulario.html', {'form': form, **textos})


def _segundos_para_reenviar(request):
    falta = ESPERA_REENVIO - (time.time() - request.session.get(CLAVE_ENVIO, 0))
    return max(0, int(falta))


def _avisar_envio(request, enviado, correo):
    if enviado:
        request.session[CLAVE_ENVIO] = time.time()
        messages.success(request, f'Te enviamos un enlace a {correo} para confirmar tu correo.')
    else:
        messages.error(request, 'No pudimos enviar el correo de confirmación. Inténtalo de nuevo en unos minutos.')


def _con_token_valido(perfiles, campo_user, uidb64, token, generador):
    """El perfil (con ``.user``) del enlace de confirmacion, o None si el enlace no sirve."""
    user_id = user_id_de_uid(uidb64)
    perfil = perfiles.filter(**{campo_user: user_id}).first() if user_id else None
    return perfil if perfil is not None and generador.check_token(perfil.user, token) else None


@sensitive_post_parameters('password', 'confirmar_password')
@never_cache
def registro(request):
    rol = rol_en_sesion(request)
    if rol is not None:
        return redirigir_a_portal(rol)
    form = RegistroApoderadoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        apoderado = form.save()
        auth_login(request, apoderado.user, backend=BACKEND)
        abrir_sesion_rol(request, APODERADO, apoderado)
        _avisar_envio(request, enviar_confirmacion(request, apoderado), apoderado.user.email)
        return redirect(APODERADO.ruta_portal)
    return _formulario(
        request, form, titulo='Crea tu cuenta de apoderado', subtitulo='Tus datos', boton='Crear cuenta',
        volver_url=reverse('opcion_user'),
        intro=('Para madres, padres y tutores legales de estudiantes menores de edad. Antes de habilitar tu '
               'cuenta confirmaremos tu correo y nuestro equipo de soporte revisará tu identidad con una foto de tu '
               'carnet por ambos lados.'),
    )


@never_cache
def confirmar_correo(request, uidb64, token):
    apoderado = _con_token_valido(Apoderado.objects.select_related('user'), 'user_id',
                                  uidb64, token, token_correo)
    if apoderado is None:
        return render(request, 'apoderados/enlace_invalido.html', status=400)
    apoderado.confirmar_correo()
    messages.success(request, 'Correo confirmado. Ahora nuestro equipo de soporte revisará tu identidad.')
    return redirect(APODERADO.ruta_portal if request.session.get(APODERADO.clave_sesion) else 'login')


@never_cache
@apoderado_required
def portal(request):
    apoderado = _apoderado_en_sesion(request)
    token = request.session.get(CLAVE_INVITACION)
    return render(request, 'apoderados/portal.html', {
        'apoderado': apoderado,
        'revision': apoderado.ultima_revision,
        'espera': _segundos_para_reenviar(request),
        'vinculos': apoderado.vinculos.select_related('alumno__user')
                    .prefetch_related('revisiones', 'compras__paquete__profesor__user'),
        'invitacion': invitacion_vigente(token) if token else None,
        'token_invitacion': token,
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
        _avisar_envio(request, enviar_confirmacion(request, apoderado), apoderado.user.email)
    return redirect(APODERADO.ruta_portal)


@sensitive_post_parameters('password', 'confirmar_password')
@never_cache
@apoderado_required
def registrar_estudiante(request):
    apoderado = _apoderado_en_sesion(request)
    if apoderado.estado != Apoderado.VERIFICADO:
        messages.error(request, 'Podrás registrar estudiantes cuando tu identidad esté verificada.')
        return redirect(APODERADO.ruta_portal)
    form = RegistroEstudianteForm(request.POST or None, request.FILES or None, apoderado=apoderado)
    if request.method == 'POST' and form.is_valid():
        vinculo = form.save()
        messages.success(request, f'Registramos a {vinculo.alumno.user.first_name}. Nuestro equipo de soporte '
                                  'revisará el documento que adjuntaste para verificar el vínculo.')
        return redirect(APODERADO.ruta_portal)
    return _formulario(
        request, form, titulo='Registrar a un estudiante', subtitulo='Datos del estudiante',
        boton='Registrar estudiante', volver_url=reverse(APODERADO.ruta_portal),
        intro=('El estudiante entrará con su RUT y la contraseña que definas aquí. Hasta que verifiquemos '
               'el vínculo con el documento que adjuntes, solo podrá ver el catálogo.'),
    )


@sensitive_post_parameters('new_password1', 'new_password2')
@never_cache
@apoderado_required
def clave_estudiante(request, id_vinculo):
    # Solo vinculos propios, no rechazados y de cuentas que creo el apoderado
    # (Vinculo.apoderado_define_clave): lo demas responde 404.
    vinculo = get_object_or_404(
        Vinculo.objects.select_related('alumno__user'), pk=id_vinculo,
        apoderado_id=request.session[APODERADO.clave_sesion],
        estado__in=[Vinculo.PENDIENTE, Vinculo.VERIFICADO],
        alumno__solicitud_apoderado__isnull=True,
    )
    estudiante = vinculo.alumno.user
    if not es_menor(estudiante):  # a los 18 la contrasena es solo suya
        raise Http404
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


# --- El apoderado contrata y reserva por su estudiante ---

def _vinculo_o_404(request, id_vinculo):
    vinculo = vinculo_contratable(request, id_vinculo)
    if vinculo is None:
        raise Http404
    return vinculo


@require_POST
@apoderado_required
def comprar_paquete(request, id_vinculo):
    """Mismo Webpay que el alumno; el paquete queda a nombre del estudiante."""
    vinculo = _vinculo_o_404(request, id_vinculo)
    return iniciar_compra_paquete(request, vinculo.alumno_id, al_crear=lambda paquete: (
        CompraApoderado.objects.create(paquete=paquete, apoderado=vinculo.apoderado, vinculo=vinculo)))


@never_cache
@apoderado_required
def clases_estudiante(request, id_vinculo):
    vinculo = _vinculo_o_404(request, id_vinculo)
    alumno = vinculo.alumno
    paquetes = list(PaqueteClases.objects.vigentes().filter(alumno=alumno).select_related('profesor__user'))
    reservas = list(Inscripcion.objects.proximas().filter(alumno=alumno)
                    .select_related('clase__asignatura', 'clase__profesor__user', 'sesion'))
    con_clases = [p for p in paquetes if p.clases_disponibles]
    # Sesiones que el servicio aceptaria: de profesores con clases libres y dentro de la vigencia.
    sesiones = (SesionClase.objects.disponibles()
                .filter(clase__profesor_id__in={p.profesor_id for p in con_clases},
                        fecha_hora_inicio__lte=max(p.fecha_fin for p in con_clases))
                .exclude(pk__in=[r.sesion_id for r in reservas if r.sesion_id])
                .select_related('clase__asignatura', 'clase__profesor__user')
                .order_by('fecha_hora_inicio')[:30]) if con_clases else []
    return render(request, 'apoderados/clases.html', {
        'vinculo': vinculo, 'paquetes': paquetes, 'reservas': reservas, 'sesiones': sesiones,
    })


def _operar(request, id_vinculo, accion, operacion):
    """Reserva, cancela o reprograma por el estudiante y avisa a sus apoderados."""
    vinculo = _vinculo_o_404(request, id_vinculo)
    try:
        inscripcion = operacion(vinculo)
    except ValueError:
        messages.error(request, 'Elige una sesión válida.')
    except InscripcionError as error:
        messages.error(request, str(error))
    else:
        avisar_apoderados(inscripcion, accion, vinculo.apoderado.nombre)
        messages.success(request, 'Cambio guardado. Avisamos por correo a los apoderados del estudiante.')
    return redirect('apoderado_clases_estudiante', vinculo.pk)


def _sesion_del_post(request):
    return int(request.POST.get('id_sesion', ''))


@require_POST
@apoderado_required
def reservar_clase(request, id_vinculo):
    return _operar(request, id_vinculo, 'reservó', lambda v: InscripcionService.inscribir_alumno_en_sesion(
        v.alumno, _sesion_del_post(request), vinculo=v))


@require_POST
@apoderado_required
def cancelar_clase(request, id_vinculo, id_inscripcion):
    return _operar(request, id_vinculo, 'canceló', lambda v: InscripcionService.cancelar_inscripcion(
        v.alumno, id_inscripcion, vinculo=v))


@require_POST
@apoderado_required
def reprogramar_clase(request, id_vinculo, id_inscripcion):
    return _operar(request, id_vinculo, 'reprogramó', lambda v: InscripcionService.reprogramar_inscripcion(
        v.alumno, id_inscripcion, _sesion_del_post(request), vinculo=v))


# --- Revocar el vinculo y contrasena propia al cumplir 18 ---

def _revocar(request, vinculo, volver, motivo_obligatorio):
    form = RevocarVinculoForm(request.POST or None, motivo_obligatorio=motivo_obligatorio)
    estudiante = vinculo.alumno.user.first_name
    if request.method == 'POST' and form.is_valid():
        canceladas = vinculo.revocar(request.user, form.cleaned_data['motivo'])
        messages.success(request, f'Revocamos el vínculo de {vinculo.apoderado.nombre} con {estudiante}. '
                                  f'Clases futuras canceladas: {canceladas}.')
        return redirect(volver)
    return _formulario(
        request, form, titulo=f'Revocar el vínculo con {estudiante}', subtitulo='Confirma la revocación',
        boton='Revocar vínculo', volver_url=reverse(volver),
        intro=(f'{vinculo.apoderado.nombre} dejará de poder reservar, contratar o cambiar la contraseña de '
               f'{estudiante}. Las clases futuras pagadas con este vínculo se cancelan y vuelven al paquete.'),
    )


@never_cache
@apoderado_required
def revocar_vinculo(request, id_vinculo):
    vinculo = get_object_or_404(Vinculo.objects.select_related('apoderado', 'alumno__user'), pk=id_vinculo,
                                apoderado_id=request.session[APODERADO.clave_sesion],
                                estado__in=Vinculo.REVOCABLES)
    return _revocar(request, vinculo, APODERADO.ruta_portal, motivo_obligatorio=False)


@never_cache
@lider_required
def revocar_vinculo_admin(request, id_vinculo):
    vinculo = get_object_or_404(Vinculo.objects.select_related('apoderado', 'alumno__user'), pk=id_vinculo,
                                estado__in=Vinculo.REVOCABLES)
    return _revocar(request, vinculo, 'apoderados_revision', motivo_obligatorio=True)


@sensitive_post_parameters('new_password1', 'new_password2')
@never_cache
@alumno_sesion_required
def nueva_clave_estudiante(request):
    if not debe_renovar_clave(request.user):
        return redirect(ALUMNO.ruta_portal)
    form = NuevaClaveForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        update_session_auth_hash(request, form.save())  # sigue con la sesion abierta
        messages.success(request, 'Listo: tu cuenta ahora tiene una contraseña que solo tú conoces.')
        return redirect(ALUMNO.ruta_portal)
    return _formulario(
        request, form, titulo='Define tu nueva contraseña', subtitulo='Ya cumpliste 18 años',
        boton='Guardar contraseña', volver_url=reverse('logout_apoderado'),
        intro=('Tu apoderado definió tu contraseña actual. Desde ahora tu cuenta es solo tuya: '
               'elige una nueva que solo tú conozcas para seguir.'),
    )


# --- El adolescente de 14 a 17 invita a su madre o padre ---

@sensitive_post_parameters('password', 'confirmar_password')
@never_cache
def registro_adolescente(request):
    rol = rol_en_sesion(request)
    if rol is not None:
        return redirigir_a_portal(rol)
    form = RegistroAdolescenteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        alumno = form.save()
        auth_login(request, alumno.user, backend=BACKEND)
        abrir_sesion_rol(request, ALUMNO, alumno)
        _avisar_envio(request, enviar_confirmacion_adolescente(request, alumno.user), alumno.user.email)
        return redirect('adolescente_solicitud')
    return _formulario(
        request, form, titulo='Crea tu cuenta de estudiante', subtitulo='Tus datos', boton='Crear cuenta',
        volver_url=reverse('opcion_user'),
        intro=('Para estudiantes de 14 a 17 años. Cuando confirmes tu correo, invitaremos a tu madre o a tu '
               'padre a ser tu apoderado. Hasta que verifiquemos el vínculo, solo podrás ver el catálogo.'),
    )


@never_cache
def confirmar_correo_adolescente(request, uidb64, token):
    solicitud = _con_token_valido(SolicitudAdolescente.objects.select_related('alumno__user'),
                                  'alumno__user_id', uidb64, token, token_correo_adolescente)
    if solicitud is None:
        return render(request, 'apoderados/enlace_invalido.html', status=400)
    if solicitud.confirmar_correo():
        _enviar_invitacion(request, solicitud, solicitud.correo_apoderado)
    return redirect('adolescente_solicitud' if request.session.get(ALUMNO.clave_sesion) else 'login')


def _enviar_invitacion(request, solicitud, correo):
    if enviar_invitacion(request, solicitud.invitar(correo)):
        messages.success(request, f'Enviamos la invitación a {correo}.')
    else:
        messages.error(request, 'No pudimos enviar la invitación. Inténtalo de nuevo en unos minutos.')


@never_cache
@alumno_required
def solicitud_adolescente(request):
    solicitud = _solicitud_en_sesion(request)
    return render(request, 'apoderados/solicitud.html', {
        'solicitud': solicitud,
        'invitacion': solicitud.ultima_invitacion,
        'vinculos': solicitud.alumno.vinculos_apoderado.select_related('apoderado__user'),
        'form': InvitacionForm(solicitud=solicitud),
        'espera': _segundos_para_reenviar(request),
    })


@require_POST
@alumno_required
def reenviar_correo_adolescente(request):
    solicitud = _solicitud_en_sesion(request)
    if solicitud.correo_confirmado:
        messages.info(request, 'Tu correo ya está confirmado.')
    elif _segundos_para_reenviar(request):
        messages.error(request, 'Espera un minuto antes de pedir otro enlace.')
    else:
        user = solicitud.alumno.user
        _avisar_envio(request, enviar_confirmacion_adolescente(request, user), user.email)
    return redirect('adolescente_solicitud')


@require_POST
@alumno_required
def invitar(request):
    solicitud = _solicitud_en_sesion(request)
    form = InvitacionForm(request.POST, solicitud=solicitud)
    if solicitud.correo_confirmado is None:
        messages.error(request, 'Primero confirma tu correo.')
    elif form.is_valid():
        _enviar_invitacion(request, solicitud, form.cleaned_data['correo_apoderado'])
    else:
        messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('adolescente_solicitud')


@never_cache
def invitacion(request, token):
    pendiente = invitacion_vigente(token)
    if pendiente is None:
        return render(request, 'apoderados/enlace_invalido.html', status=400, context={
            'detalle': 'Pídele al estudiante que te envíe una invitación nueva desde su cuenta.'})
    estudiante = pendiente.solicitud.alumno
    rol = rol_en_sesion(request)
    if rol is not APODERADO:
        # Se guarda el enlace: al entrar o registrarse, el portal ofrece aceptarlo.
        request.session[CLAVE_INVITACION] = token
        return render(request, 'apoderados/invitacion.html', {
            'nombre': estudiante.user.first_name, 'otra_sesion': rol is not None})

    apoderado = _apoderado_en_sesion(request)
    if apoderado.estado == Apoderado.RECHAZADO:
        messages.error(request, 'No puedes aceptar invitaciones porque tu verificación fue rechazada.')
        return redirect(APODERADO.ruta_portal)
    if apoderado.vinculos.filter(alumno=estudiante).exists():
        request.session.pop(CLAVE_INVITACION, None)
        messages.info(request, f'Ya tienes un vínculo con {estudiante.user.first_name}.')
        return redirect(APODERADO.ruta_portal)
    form = AceptarInvitacionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            vinculo = pendiente.aceptar(apoderado, form.cleaned_data['parentesco'], VERSION_DECLARACION_VINCULO)
            form.guardar_documento(vinculo)
        request.session.pop(CLAVE_INVITACION, None)
        messages.success(request, f'Aceptaste la invitación de {estudiante.user.first_name}. Nuestro equipo de soporte '
                                  'revisará el documento que adjuntaste para verificar el vínculo.')
        return redirect(APODERADO.ruta_portal)
    return _formulario(
        request, form, titulo=f'Invitación de {estudiante.user.first_name}', subtitulo='Confirma el vínculo',
        boton='Aceptar invitación', volver_url=reverse(APODERADO.ruta_portal),
        intro=('Si eres su madre o su padre, acepta la invitación y adjunta su certificado de nacimiento. Nuestro '
               'equipo de soporte revisará tu identidad y ese documento antes de verificar el vínculo.'),
    )


def logout_apoderado(request):
    auth_logout(request)
    return redirect('home')


@never_cache
@soporte_required
def revision(request):
    """Lo que el agente tiene asignado. El lider ademas ve registros, vinculos y accesos."""
    agente = agente_en_sesion(request)
    mios = tickets_del_agente(request)
    contexto = {
        'agente': agente,
        'pendientes': (Apoderado.objects.filter(estado=Apoderado.REVISION_PENDIENTE, tickets__in=mios)
                       .select_related('user').prefetch_related('documentos')),
        # Solo los que se pueden revisar: el apoderado ya tiene su identidad verificada.
        'vinculos_pendientes': (Vinculo.objects.filter(estado=Vinculo.PENDIENTE, apoderado__estado=Apoderado.VERIFICADO,
                                                       tickets__in=mios)
                                .select_related('apoderado__user', 'alumno__user')
                                .prefetch_related('invitaciones', 'documentos')),
    }
    if agente.es_lider:
        contexto.update({
            'historial': RevisionIdentidad.objects.select_related('apoderado__user', 'administrador')[:50],
            'historial_vinculos': (RevisionVinculo.objects
                                   .select_related('vinculo__apoderado__user', 'vinculo__alumno__user',
                                                   'administrador')[:50]),
            'vinculos_vigentes': (Vinculo.objects.filter(estado=Vinculo.VERIFICADO)
                                  .select_related('apoderado__user', 'alumno__user')),
            'revocaciones': Revocacion.objects.select_related('vinculo__apoderado__user', 'vinculo__alumno__user',
                                                              'autor').order_by('-fecha')[:50],
            'accesos': AccesoDocumento.objects.select_related('administrador', 'apoderado__user')[:50],
        })
    return render(request, 'apoderados/revision.html', contexto)


@never_cache
@soporte_required
def ver_documento(request, id_documento):
    """Documento por revisar, con marca de agua de quien lo abre. Cada apertura queda registrada.
    Solo para el agente con el ticket de ese apoderado o vinculo."""
    documento = get_object_or_404(Documento.objects.select_related('apoderado', 'vinculo__apoderado'),
                                  pk=id_documento)
    if ticket_asignado(request, apoderado_id=documento.apoderado_id, vinculo_id=documento.vinculo_id) is None:
        raise Http404('Documento no encontrado.')
    texto = f'LBWUS - solo revision - {request.user.first_name or request.user.username} - ' \
            f'{timezone.localtime():%d-%m-%Y %H:%M}'
    try:
        imagen = con_marca_de_agua(documento.contenido, texto)
    except InvalidToken:  # cambio la clave de cifrado: hay que pedir el documento de nuevo
        raise Http404('El documento ya no se puede leer.')
    AccesoDocumento.objects.create(administrador=request.user, apoderado=documento.titular,
                                   vinculo=documento.vinculo, tipo=documento.tipo)
    respuesta = HttpResponse(imagen, content_type='image/jpeg')
    respuesta['Content-Disposition'] = 'inline'  # se ve en el navegador, sin descarga directa
    return respuesta


def _revisar(request, revisado, formulario, nombre):
    form = formulario(request.POST, revisado=revisado)
    if form.is_valid():
        revisado.aplicar_revision(form.save(commit=False), request.user)
        messages.success(request, f'{nombre}: {revisado.get_estado_display().lower()}.')
    else:
        messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('apoderados_revision')


@require_POST
@soporte_required
def revisar(request, id_apoderado):
    # Solo se revisa quien confirmo su correo y aun no tiene decision, con ticket propio.
    apoderado = get_object_or_404(Apoderado.objects.select_related('user'),
                                  pk=id_apoderado, estado=Apoderado.REVISION_PENDIENTE)
    if ticket_asignado(request, apoderado=apoderado) is None:
        raise Http404('Apoderado no encontrado.')
    return _revisar(request, apoderado, RevisionIdentidadForm, apoderado.nombre)


@require_POST
@soporte_required
def revisar_vinculo(request, id_vinculo):
    # Solo vinculos pendientes de apoderados con identidad verificada, con ticket propio.
    vinculo = get_object_or_404(Vinculo.objects.select_related('apoderado__user', 'alumno__user'),
                                pk=id_vinculo, estado=Vinculo.PENDIENTE,
                                apoderado__estado=Apoderado.VERIFICADO)
    if ticket_asignado(request, vinculo=vinculo) is None:
        raise Http404('Vínculo no encontrado.')
    return _revisar(request, vinculo, RevisionVinculoForm,
                    f'Vínculo {vinculo.apoderado.nombre} - {vinculo.alumno.user.first_name}')
