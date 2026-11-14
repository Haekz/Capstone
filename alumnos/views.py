import os

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.views.decorators.debug import sensitive_post_parameters
from django.core.cache import cache
from django.db.models import F

from .models import (
    Alumno,
    Genero,
    Profesor,
    Reporte,
    Clase,
    Inscripcion,
    PaqueteClases,
    Suscripcion,
)
from . import paquetes, progreso
from mensajes import panel as mensajes_panel
from observaciones import panel as observaciones_panel
from resenas.consultas import (
    calificaciones_por_profesor, formatear_promedio, ids_recomendados, pendiente_de_calificar,
)
from apoderados.permisos import vinculo_contratable
from lbwus.puerta import destino_seguro
from .forms import AlumnoForm, FiltroClasesForm
from admin_portal.forms import MensajeContactoForm
from soporte.tickets import abrir_contacto
from .decorators import alumno_required
from .utils import es_menor
from .portales import contexto_de_marco
from .templatetags.dinero import clp as _clp  # mismo formato en vistas y plantillas
from .roles import (
    ALUMNO,
    abrir_sesion_rol,
    redirigir_a_portal,
    resolver_rol,
    rol_en_sesion,
)
from .backends import obtener_identificador_rate_limit


def _plan_para_js(alumno):
    """Plan vigente en el formato que usa el JS del portal, o None si no tiene."""
    paquete = alumno.paquetes.vigentes().order_by('-fecha_fin').first()
    if paquete:
        return {'nombre': paquete.get_plan_display(), 'premium': True}
    suscripcion = alumno.plan_vigente()
    if suscripcion is None:
        return None
    return {'nombre': suscripcion.get_plan_display(), 'premium': suscripcion.es_premium}

def _profesor_habilitado(profesor_id):
    """Profesor que puede vender clases segun el id recibido, o None."""
    profesor_id = str(profesor_id or '')
    if not profesor_id.isdecimal():
        return None
    return Profesor.objects.habilitados().select_related('user').filter(pk=profesor_id).first()


# ============================================================
# VISTAS PÚBLICAS
# ============================================================

def home(request):
    context = {}
    return render(
        request,
        'alumnos/home.html',
        context
    )


def _alumno_en_sesion_es_menor(request):
    """El alumno con sesion abierta es menor de edad: contrata su apoderado, no el."""
    alumno_id = request.session.get('alumno_id')
    alumno = Alumno.objects.select_related('user').filter(pk=alumno_id).first() if alumno_id else None
    return alumno is not None and es_menor(alumno.user)


def planes(request):
    """Paquetes con los precios del profesor elegido (?profesor=id) o de la tarifa base.
    Todo precio sale de alumnos/paquetes.py: la pantalla no calcula nada.
    """
    profesor = _profesor_habilitado(request.GET.get('profesor'))
    tarifa = profesor.tarifa if profesor else paquetes.TARIFA_BASE

    if request.GET.get('format') == 'json' or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        planes_data = [  # mismos precios que la pantalla (BUG-QA-01)
            {'nombre': f'Plan {c.plan.nombre}', 'clases': c.plan.clases, 'precio_total': c.precio, 'sin_renovacion': True}
            for c in paquetes.cotizar(tarifa)
        ]
        return JsonResponse({
            'planes': planes_data,
            'profesor': {
                'id': profesor.id_profesor,
                'nombre': profesor.nombre,
                'tarifa_base': tarifa,
            } if profesor else None,
            'status': 'ok'
        })

    return render(request, 'alumnos/planes.html', {
        # Primero el marco: las claves propias de Planes (es_menor...) mandan sobre las suyas
        **contexto_de_marco(request, seccion='paquetes'),
        'profesores': Profesor.objects.habilitados().select_related('user', 'especialidad')
                                                    .order_by('user__first_name', 'user__last_name'),
        'profesor': profesor,
        'tarifa': tarifa,
        'tarifa_base': paquetes.TARIFA_BASE,
        'cotizaciones': paquetes.cotizar(tarifa),
        'duracion_clase': paquetes.DURACION_CLASE_MIN,
        'comision_pct': int(paquetes.COMISION * 100),
        'es_alumno': bool(request.session.get('alumno_id')),
        # El menor ve que contrata su apoderado, en vez de botones que no harian nada.
        'es_menor': _alumno_en_sesion_es_menor(request),
        # Apoderado contratando para su estudiante (?estudiante=id del vinculo verificado).
        'estudiante': vinculo_contratable(request, request.GET.get('estudiante')),
    })


def servicios(request):
    context = {}
    return render(
        request,
        'alumnos/servicios.html',
        context
    )


def nosotros(request):
    context = {}
    return render(
        request,
        'alumnos/nosotros.html',
        context
    )


# Formulario publico: tope de mensajes por IP en una hora, como el limite de intentos del login.
LIMITE_CONTACTO = 5


def contactos(request):
    if request.method == 'POST':
        return _recibir_contacto(request)
    context = {}
    return render(
        request,
        'alumnos/contactos.html',
        context
    )


def _recibir_contacto(request):
    clave = f'contacto_ip_{_obtener_ip(request)}'
    enviados = cache.get(clave, 0)
    if enviados >= LIMITE_CONTACTO:
        return JsonResponse({'success': False, 'message': 'Ya enviaste varios mensajes. Intenta de nuevo en una hora.'},
                            status=429)
    form = MensajeContactoForm(request.POST)
    if not form.is_valid():
        primer_error = next(iter(form.errors.values()))[0]
        return JsonResponse({'success': False, 'message': primer_error}, status=400)
    # Lo atiende soporte, como cualquier caso (H14, D5): el admin solo ve metricas.
    abrir_contacto(form.save(commit=False))
    cache.set(clave, enviados + 1, 3600)
    return JsonResponse({'success': True})


def opcion_user(request):
    context = {}
    return render(
        request,
        'alumnos/opcion_user.html',
        context
    )


# ============================================================
# REGISTRO DE ALUMNOS
# ============================================================

def regis_alum(request):

    if request.method == 'POST':

        form = AlumnoForm(request.POST)

        if form.is_valid():

            alumno = form.save()

            auth_login(
                request,
                alumno.user,
                backend='alumnos.backends.RutOrEmailBackend'
            )

            abrir_sesion_rol(request, ALUMNO, alumno)

            return JsonResponse({
                "success": True,
                "message": "Alumno registrado exitosamente."
            })

        else:

            errors = []

            for field, errs in form.errors.items():

                if field in form.fields:
                    label = form.fields[field].label
                else:
                    label = field

                errors.append(
                    f"{label}: {errs[0]}"
                )

            return JsonResponse({
                "success": False,
                "message": " | ".join(errors)
            })

    form = AlumnoForm()
    generos = Genero.objects.all()

    context = {
        'form': form,
        'generos': generos
    }

    return render(
        request,
        'alumnos/regis_alum.html',
        context
    )


def alumnos_reg(request):
    """Alias de compatibilidad hacia regis_alum para mantener DRY y contexto completo."""
    return regis_alum(request)


# ============================================================
# PORTAL DEL ALUMNO
# ============================================================

def _rating_para_tarjeta(calificacion):
    """Lo que muestra la tarjeta del profesor: promedio con coma y total; None si aun no tiene resenas."""
    if not calificacion:
        return None
    return {'promedio': formatear_promedio(calificacion['promedio']), 'total': calificacion['total']}


@never_cache
@alumno_required
def alumno_pag1(request):

    alumno_id = request.session['alumno_id']

    alumno = get_object_or_404(
        Alumno.objects.select_related('user', 'user__genero'),
        id_alumno=alumno_id
    )

    mis_reportes = list(
        Reporte.objects.filter(
            remitente=alumno.user
        ).order_by(
            '-fecha_reporte'
        )
    )

    # Solo profesores con titulo aprobado pueden hacer clases.
    profesores_list = Profesor.objects.habilitados().select_related(
        'user',
        'especialidad'
    ).order_by('user__first_name', 'user__last_name')

    filtros = FiltroClasesForm(request.GET)
    filtros.is_valid()
    criterios = filtros.cleaned_data
    clases_disponibles = Clase.objects.habilitadas().filtrar(
        especialidad=criterios.get('especialidad'),
        solo_disponibles=criterios.get('disponible', False),
    ).select_related('asignatura', 'profesor__user', 'profesor__especialidad')

    relacionadas = ('clase__asignatura', 'clase__profesor__user', 'clase__profesor__especialidad', 'sesion')
    mis_inscripciones = (
        Inscripcion.objects.filter(alumno=alumno).proximas()
        .select_related(*relacionadas)
        .order_by(F('sesion__fecha_hora_inicio').asc(nulls_last=True), '-fecha_inscripcion')
    )
    historial_clases = (
        Inscripcion.objects.filter(alumno=alumno).completadas()
        .select_related(*relacionadas)
        .order_by('-sesion__fecha_hora_inicio')
    )

    mis_paquetes = list(
        alumno.paquetes.vigentes().select_related('profesor__user').order_by('fecha_fin')
    )
    pagos = sorted(
        [*alumno.suscripciones.exclude(estado=Suscripcion.ESTADO_PENDIENTE),
         *alumno.paquetes.exclude(estado=PaqueteClases.ESTADO_PENDIENTE)],
        key=lambda pago: pago.creada, reverse=True,
    )
    for pago in pagos:
        pago.monto_clp = _clp(pago.total if isinstance(pago, PaqueteClases) else pago.monto)  # lo cobrado en Webpay

    calificaciones = calificaciones_por_profesor()
    profesor_por_id = {p.id_profesor: p for p in profesores_list}
    recomendados = [
        {'profesor': profesor_por_id[id_profesor], 'rating': _rating_para_tarjeta(calificaciones[id_profesor])}
        for id_profesor in ids_recomendados(calificaciones, entre=profesor_por_id)
    ]

    context = {
        'alumno': alumno,
        'mis_reportes': mis_reportes,
        'profesores_list': profesores_list,
        'recomendados': recomendados,
        # Solo datos reales. Distancia y precio no se registran todavia en la plataforma, asi que no se
        # inventan; la calificacion sale de las resenas visibles (None = profesor nuevo, sin resenas).
        'profesores_js': [
            {
                'id': p.id_profesor,
                'name': p.nombre,
                'specialties': [p.especialidad.nombre] if p.especialidad else [],
                'initial': p.nombre[:1].upper(),
                'rating': _rating_para_tarjeta(calificaciones.get(p.id_profesor)),
            }
            for p in profesores_list
        ],
        'clases_disponibles': clases_disponibles,
        'filtros': filtros,
        'hay_filtros': any(criterios.values()),
        'especialidades': filtros.fields['especialidad'].queryset,
        'mis_inscripciones': mis_inscripciones,
        'historial_clases': historial_clases,
        'progreso': alumno.resumen_progreso(),
        'progreso_ramos': progreso.por_ramo(alumno),
        'grafico_semanal': progreso.horas_por_semana(alumno),
        # Lo que el profesor comenta de las clases: lo lee el alumno (menor o no) aqui, y el apoderado del menor en su portal.
        'observaciones': observaciones_panel.del_alumno(alumno),
        'plan_activo': _plan_para_js(alumno),
        'mis_paquetes': mis_paquetes,
        'pagos': pagos,
        'es_menor': es_menor(alumno.user),
        'tiene_solicitud': hasattr(alumno, 'solicitud_apoderado'),  # adolescente de 14 a 17 (apoderados)
        'por_calificar': pendiente_de_calificar(alumno),  # cuadro de estrellas al entrar
        # Buzon de Dudas (mensajes/panel.py); el error de un envio rechazado se muestra una sola vez.
        **mensajes_panel.contexto_alumno(alumno, request.GET.get('c'), request.session.pop('mensajes_error', None)),
    }

    return render(
        request,
        'alumnos/Alumno_pag1.html',
        context
    )


# ============================================================
# LOGIN CENTRALIZADO
# ============================================================

def _obtener_ip(request):
    """IP del cliente para el limite de intentos.

    X-Forwarded-For lo escribe el propio cliente, salvo la ultima IP, que la agrega
    el proxy de confianza (Railway). Por eso solo se usa esa: con la primera bastaba
    cambiar la cabecera para reiniciar el contador.
    """
    if getattr(settings, 'CONFIAR_X_FORWARDED_FOR', False) or os.environ.get('RAILWAY_ENVIRONMENT'):
        ips = [ip.strip() for ip in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if ip.strip()]
        if ips:
            return ips[-1]
    return request.META.get('REMOTE_ADDR', '').strip() or '127.0.0.1'


LIMITE_INTENTOS_IP = 15
LIMITE_INTENTOS_USUARIO = 5
BLOQUEO_LOGIN_SEGUNDOS = 300
MENSAJE_LOGIN_BLOQUEADO = (
    "Demasiados intentos fallidos. Por seguridad, el acceso ha sido bloqueado temporalmente por 5 minutos."
)


def _abrir_sesion(request, user, siguiente):
    """(respuesta, error): abre la sesion del rol del usuario y lo manda a su portal (o a ``siguiente``).

    El rol lo define el perfil asociado (ver alumnos/roles.py). Sin perfil no se abre sesion.
    """
    rol, perfil = resolver_rol(user)
    if rol is None:
        return None, "Tu cuenta no tiene un perfil asignado en el sistema."
    auth_login(request, user)
    abrir_sesion_rol(request, rol, perfil)
    return (redirect(siguiente) if siguiente else redirigir_a_portal(rol)), None


# never_cache: si el navegador guarda el login, al volver "atras" desde el
# portal muestra esa copia (con los datos escritos) en vez de preguntarle al
# servidor, que habria redirigido al portal porque la sesion sigue activa.
@sensitive_post_parameters('password')
@never_cache
def custom_login(request):

    # Si ya existe una sesión activa, redirigir al portal de ese rol.
    rol_activo = rol_en_sesion(request)
    if rol_activo is not None:
        return redirigir_a_portal(rol_activo)

    error = None
    # A donde volver tras entrar (p. ej. el boton de un pago rechazado). Solo rutas
    # internas: destino_seguro rechaza otros dominios; '/' significa "ninguno".
    siguiente = destino_seguro(request.POST.get('next') or request.GET.get('next'))
    siguiente = '' if siguiente == '/' else siguiente

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        ip = _obtener_ip(request)
        # Mismo contador para todas las formas de escribir el RUT.
        canon_user = obtener_identificador_rate_limit(username)
        clave_cache_ip = f'intentos_login_ip_{ip}'
        clave_cache_user = f'intentos_login_user_{canon_user}'

        intentos_ip = cache.get(clave_cache_ip, 0)
        intentos_user = cache.get(clave_cache_user, 0)

        if intentos_ip >= LIMITE_INTENTOS_IP or intentos_user >= LIMITE_INTENTOS_USUARIO:
            return render(request, 'registration/login.html', {'error': MENSAJE_LOGIN_BLOQUEADO})

        if not username or not password:
            error = "Por favor ingrese todos los campos."
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                cache.delete(clave_cache_ip)
                cache.delete(clave_cache_user)
                respuesta, error = _abrir_sesion(request, user, siguiente)
                if respuesta is not None:
                    return respuesta
            else:
                cache.set(clave_cache_ip, intentos_ip + 1, BLOQUEO_LOGIN_SEGUNDOS)
                if canon_user:
                    cache.set(clave_cache_user, intentos_user + 1, BLOQUEO_LOGIN_SEGUNDOS)
                error = "RUT/Correo o contraseña incorrectos. Inténtalo de nuevo."

    return render(request, 'registration/login.html', {'error': error, 'siguiente': siguiente})


# ============================================================
# LOGOUT ALUMNO
# ============================================================

@never_cache
@require_POST
def logout_alumno(request):
    auth_logout(request)
    request.session.flush()
    return redirect('home')
