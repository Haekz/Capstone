import json
import os
import secrets

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, JsonResponse, Http404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.urls import reverse
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
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
    SesionClase,
    Inscripcion,
    PaqueteClases,
    Suscripcion,
)
from django.core.exceptions import ValidationError
from . import paquetes, progreso
from mensajes import panel as mensajes_panel
from observaciones import panel as observaciones_panel
from resenas.consultas import (
    calificaciones_por_profesor, formatear_promedio, ids_recomendados, pendiente_de_calificar,
)
from django.db import transaction
from apoderados.permisos import clase_pagada_por_apoderado, vinculo_contratable
from lbwus.puerta import destino_seguro
from .forms import AlumnoForm, FiltroClasesForm
from admin_portal.forms import MensajeContactoForm
from .decorators import alumno_required, alumno_required_json, profesor_required_json, sesion_iniciada_required
from .exceptions import InscripcionError
from .services import InscripcionService, exigir_mayor_de_edad
from .utils import es_menor
from .portales import contexto_de_marco
from .templatetags.dinero import clp as _clp  # mismo formato en vistas y plantillas
from .roles import (
    ALUMNO,
    PROFESOR,
    abrir_sesion_rol,
    redirigir_a_portal,
    resolver_rol,
    rol_en_sesion,
)
from .backends import obtener_identificador_rate_limit


# ============================================================
# TRANSBANK - WEBPAY PLUS
# Ambiente de integración
# ============================================================

from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_type import IntegrationType


def _tx():
    """Construye la instancia de Transaction de Webpay Plus según la estrategia de credenciales (S-08 / 7.6).

    Salvaguarda estricta:
    - Salvo que TRANSBANK_PRODUCCION_HABILITADA sea True Y se provean credenciales válidas en LIVE,
      el sistema opera forzosamente en IntegrationType.TEST (Sandbox oficial Transbank).
    - Evita cualquier cobro real o uso no autorizado en ambientes de prueba o desarrollo.
    """
    produccion_habilitada = getattr(settings, 'TRANSBANK_PRODUCCION_HABILITADA', False)
    cc = getattr(settings, 'TRANSBANK_COMMERCE_CODE', '')
    api_key = getattr(settings, 'TRANSBANK_API_KEY', '')
    env_str = getattr(settings, 'TRANSBANK_ENVIRONMENT', 'TEST')

    if produccion_habilitada and env_str == 'LIVE' and cc and api_key:
        return Transaction(
            WebpayOptions(
                cc,
                api_key,
                IntegrationType.LIVE,
            )
        )

    # Por defecto / Salvaguarda de no cobro real (Modo Integración / Sandbox oficial):
    return Transaction(
        WebpayOptions(
            IntegrationCommerceCodes.WEBPAY_PLUS,
            IntegrationApiKeys.WEBPAY,
            IntegrationType.TEST,
        )
    )


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
        planes_data = [
            {'nombre': 'Plan Flexible', 'clases': 1, 'precio_total': 15000, 'sin_renovacion': True},
            {'nombre': 'Plan Progreso', 'clases': 4, 'precio_total': 59000, 'sin_renovacion': True},
            {'nombre': 'Plan Intensivo', 'clases': 8, 'precio_total': 116000, 'sin_renovacion': True},
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
    form.save()
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
        modalidad=criterios.get('modalidad'),
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
        pago.monto_clp = _clp(pago.monto)  # mismo formato que la confirmacion de Webpay

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

        username = request.POST.get(
            'username',
            ''
        ).strip()

        password = request.POST.get(
            'password',
            ''
        )

        ip = _obtener_ip(request)
        # Mismo contador para todas las formas de escribir el RUT.
        canon_user = obtener_identificador_rate_limit(username)
        clave_cache_ip = f'intentos_login_ip_{ip}'
        clave_cache_user = f'intentos_login_user_{canon_user}'

        intentos_ip = cache.get(clave_cache_ip, 0)
        intentos_user = cache.get(clave_cache_user, 0)

        if intentos_ip >= 15 or intentos_user >= 5:
            return render(
                request,
                'registration/login.html',
                {
                    'error': (
                        "Demasiados intentos fallidos. "
                        "Por seguridad, el acceso ha sido bloqueado "
                        "temporalmente por 5 minutos."
                    )
                }
            )

        if not username or not password:

            error = (
                "Por favor ingrese todos "
                "los campos."
            )

        else:

            user = authenticate(
                request,
                username=username,
                password=password
            )

            if user is not None:

                cache.delete(clave_cache_ip)
                cache.delete(clave_cache_user)

                # El rol lo define el perfil asociado (ver alumnos/roles.py).
                # Sin perfil no se abre sesion.
                rol, perfil = resolver_rol(user)

                if rol is None:
                    error = (
                        "Tu cuenta no tiene "
                        "un perfil asignado "
                        "en el sistema."
                    )
                else:
                    auth_login(request, user)
                    abrir_sesion_rol(request, rol, perfil)
                    return redirect(siguiente) if siguiente else redirigir_a_portal(rol)

            else:
                cache.set(clave_cache_ip, intentos_ip + 1, 300)
                if canon_user:
                    cache.set(clave_cache_user, intentos_user + 1, 300)

                error = (
                    "RUT/Correo o contraseña "
                    "incorrectos. "
                    "Inténtalo de nuevo."
                )

    return render(
        request,
        'registration/login.html',
        {
            'error': error,
            'siguiente': siguiente,
        }
    )


# ============================================================
# LOGOUT ALUMNO
# ============================================================

@never_cache
@require_POST
def logout_alumno(request):
    auth_logout(request)
    request.session.flush()
    return redirect('home')


# ============================================================
# INSCRIPCIÓN DE CLASES
# ============================================================

@alumno_required_json
def inscribir_clase(request):

    alumno_id = request.session['alumno_id']

    if request.method == 'POST':

        try:

            alumno = get_object_or_404(
                Alumno,
                id_alumno=alumno_id
            )

            if request.content_type == 'application/json':

                data = json.loads(
                    request.body
                )

                id_clase = data.get(
                    'id_clase'
                )

            else:

                id_clase = request.POST.get(
                    'id_clase'
                )

            if not id_clase:

                return JsonResponse({
                    'success': False,
                    'message': (
                        'ID de clase no '
                        'proporcionado.'
                    )
                })

            from .services import InscripcionService
            from .exceptions import InscripcionError
            from django.core.exceptions import ValidationError

            inscripcion = InscripcionService.inscribir_alumno_en_clase(alumno, id_clase)

            return JsonResponse({
                'success': True,
                'message': (
                    f'¡Te has inscrito exitosamente a "{inscripcion.clase.asignatura.nombre}" '
                    f'con el profesor {inscripcion.clase.profesor.user.first_name}!'
                )
            })

        except (InscripcionError, ValidationError) as e:
            msg = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
            return JsonResponse({
                'success': False,
                'message': msg
            })
        except Exception:
            return JsonResponse({
                'success': False,
                'message': 'Ocurrió un error inesperado al procesar la inscripción.'
            })

    return JsonResponse({
        'success': False,
        'message': 'Método no permitido.'
    })


@alumno_required_json
def listar_sesiones_disponibles(request):
    """Retorna las sesiones programadas a futuro con cupos libres en formato JSON."""
    clase_id = request.GET.get('clase_id')
    qs = SesionClase.objects.disponibles()
    if clase_id:
        qs = qs.filter(clase_id=clase_id)

    sesiones = (
        qs.select_related('clase', 'clase__asignatura', 'clase__profesor', 'clase__profesor__user')
        .order_by('fecha_hora_inicio')
    )

    inscritas_sesion_ids = set(
        Inscripcion.objects.filter(
            alumno_id=request.session['alumno_id'],
            sesion__isnull=False,
            estado__in=['confirmada', 'pendiente']
        )
        .values_list('sesion_id', flat=True)
    )

    data = [
        {
            'id_sesion': s.id_sesion,
            'id_clase': s.clase.id_clase,
            'asignatura': s.clase.asignatura.nombre,
            'profesor': s.clase.profesor.nombre,
            'modalidad': s.clase.modalidad,
            'fecha_hora_inicio': s.fecha_hora_inicio.isoformat(),
            'fecha_hora_fin': s.fecha_hora_fin.isoformat(),
            'fecha_formateada': s.inicio_local.strftime('%d/%m/%Y'),
            'hora_formateada': f"{s.inicio_local.strftime('%H:%M')} - {s.fin_local.strftime('%H:%M')} hrs",
            'inicio_formateado': s.inicio_local.strftime('%d/%m/%Y %H:%M'),
            'duracion_minutos': s.duracion_minutos,
            'cupo_maximo': s.cupo_maximo,
            'cupos_disponibles': s.cupos_disponibles,
            'precio': str(s.precio),
            'precio_formateado': f"${int(s.precio):,}".replace(',', '.') if s.precio > 0 else 'Gratis',
            'ya_inscrito': s.id_sesion in inscritas_sesion_ids,
        }
        for s in sesiones
    ]
    return JsonResponse({'success': True, 'sesiones': data})


@alumno_required_json
def reservar_sesion(request):
    """Endpoint para que un alumno autenticado reserve un cupo en una SesionClase puntual."""
    alumno_id = request.session['alumno_id']

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido.'}, status=405)

    try:
        alumno = get_object_or_404(Alumno, id_alumno=alumno_id)

        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8') or '{}')
            id_sesion = data.get('id_sesion')
        else:
            id_sesion = request.POST.get('id_sesion')

        if not id_sesion:
            return JsonResponse({'success': False, 'message': 'ID de sesión no proporcionado.'}, status=400)

        sesion = get_object_or_404(SesionClase, id_sesion=id_sesion)
        inscripcion = InscripcionService.inscribir_alumno_en_sesion(alumno, sesion.pk)

        return JsonResponse({
            'success': True,
            'message': (
                f'¡Reserva confirmada con éxito para la sesión de "{sesion.clase.asignatura.nombre}" '
                f'el {sesion.inicio_local.strftime("%d/%m/%Y a las %H:%M")}!'
            ),
            'id_inscripcion': inscripcion.pk
        })

    except Http404:
        return JsonResponse({'success': False, 'message': 'Sesión no encontrada.'}, status=404)
    except (InscripcionError, ValidationError) as e:
        msg = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
        return JsonResponse({'success': False, 'message': msg})
    except Exception:
        return JsonResponse({'success': False, 'message': 'Error inesperado al procesar la reserva. Intenta nuevamente.'})


@alumno_required
def cancelar_inscripcion(request, pk):
    alumno_id = request.session['alumno_id']
    alumno = get_object_or_404(Alumno, id_alumno=alumno_id)
    inscripcion = get_object_or_404(Inscripcion, id_inscripcion=pk, alumno_id=alumno_id)

    # Protección contra CSRF: solo procesar cancelaciones reales por POST
    if request.method != 'POST':
        return redirect('alumno_pag1')

    from .services import InscripcionService
    try:
        InscripcionService.cancelar_inscripcion(alumno, inscripcion.pk)
    except InscripcionError:
        # Ya empezo o no esta activa: no se cancela, porque devolveria una clase ya tomada.
        pass

    return redirect('alumno_pag1')


@alumno_required
@require_POST
def reprogramar_inscripcion(request, pk):
    """Mueve una reserva propia a otra sesion del mismo profesor (POST id_sesion)."""
    alumno = get_object_or_404(Alumno, id_alumno=request.session['alumno_id'])
    id_sesion = request.POST.get('id_sesion', '')
    if not id_sesion.isdecimal():
        return JsonResponse({'success': False, 'message': 'ID de sesión no proporcionado.'}, status=400)
    try:
        inscripcion = InscripcionService.reprogramar_inscripcion(alumno, pk, int(id_sesion))
    except (InscripcionError, ValidationError) as e:
        return JsonResponse({'success': False, 'message': e.messages[0] if e.messages else str(e)})
    return JsonResponse({
        'success': True,
        'message': f'Reserva movida al {inscripcion.sesion.inicio_local.strftime("%d/%m/%Y a las %H:%M")}.',
    })


# ============================================================
# PAGO CON WEBPAY PLUS - TRANSBANK
# ============================================================

@alumno_required  # el paquete necesita un dueño: sin alumna logueada no se cobra
@require_POST
def comprar_paquete(request):
    """Inicia Webpay por un paquete. El monto lo calcula el servidor con la tarifa del profesor."""
    return iniciar_compra_paquete(request, request.session['alumno_id'])  # el menor no pasa: ahi se bloquea


def iniciar_compra_paquete(request, alumno_id, al_crear=None, vinculo=None):
    """Unico inicio de Webpay para paquetes: lo usan el alumno y el apoderado.

    Plan y profesor vienen del POST; el monto lo calcula el servidor. ``al_crear``
    recibe el paquete dentro de la misma transaccion (la compra del apoderado).

    Menores: solo contrata su apoderado, con el ``vinculo`` que lo autoriza. El bloqueo vive aqui y no en las
    vistas, porque aqui se crea el paquete: cualquier vista nueva que llegue hasta este punto queda cubierta.
    """
    try:
        exigir_mayor_de_edad(get_object_or_404(Alumno, pk=alumno_id), vinculo)
    except InscripcionError:
        return redirect('alumno_pag1')
    plan = paquetes.POR_CODIGO.get(request.POST.get('plan', ''))
    profesor = _profesor_habilitado(request.POST.get('profesor'))
    if not (plan and profesor):
        return redirect('planes')

    monto = paquetes.precio(plan, profesor.tarifa)
    # Unico (26 caracteres, el maximo de Transbank): con un numero corto al azar, un
    # pedido abandonado podia compartir orden con una compra nueva y activarse gratis.
    buy_order = f'PQ{secrets.token_hex(12)}'
    session_id = f'S{secrets.token_hex(8)}'
    try:
        response = _tx().create(buy_order, session_id, monto, request.build_absolute_uri(reverse('confirmacion')))
    except Exception:  # Transbank caido o rechazo la orden: no se cobra ni se crea el paquete
        return render(request, 'alumnos/confirmacion.html', {'aprobado': False, 'items': []})

    with transaction.atomic():  # paquete y registro del apoderado: ambos o ninguno
        paquete = PaqueteClases.objects.create(
            alumno_id=alumno_id, profesor=profesor, plan=plan.codigo,
            clases=plan.clases, tarifa=profesor.tarifa, monto=monto, dias=plan.vigencia_dias,
            buy_order=buy_order,
        )
        if al_crear:
            al_crear(paquete)
    return render(request, 'alumnos/redirect_webpay.html', {'url': response['url'], 'token': response['token']})


@csrf_exempt
def confirmacion(request):

    token = (
        request.GET.get('token_ws')
        or request.POST.get('token_ws')
    )

    tbk_token = (
        request.GET.get('TBK_TOKEN')
        or request.POST.get('TBK_TOKEN')
    )

    ctx = {
        'items': []
    }

    # Pago recibido desde Webpay

    if token:

        try:
            resp = _tx().commit(token)
        except Exception:
            resp = {}

        aprobado = (
            resp.get('response_code') == 0
            and resp.get('status') == 'AUTHORIZED'
        )
        card = resp.get('card_detail') or {}
        buy_order = resp.get('buy_order', '')
        paquete = PaqueteClases.objects.filter(buy_order=buy_order).first() if buy_order else None
        if paquete and int(resp.get('amount') or 0) != paquete.monto:
            aprobado = False
        Suscripcion.confirmar_pago(buy_order, aprobado)
        PaqueteClases.confirmar_pago(buy_order, aprobado)
        ctx['items'] = [
            {'titulo': f'{p.get_plan_display()}: {p.clases} clase(s) con {p.profesor.nombre if p.profesor else "—"}',
             'cantidad': 1, 'precio': _clp(p.monto)}
            for p in PaqueteClases.objects.filter(buy_order=buy_order).select_related('profesor__user')
        ] if buy_order else []

        ctx.update({
            'aprobado': aprobado,
            'orden': buy_order,
            'monto': _clp(resp.get('amount', 0)),
            'codigo_autorizacion': resp.get('authorization_code', ''),
            'tarjeta': card.get('card_number', ''),
            'fecha': resp.get('transaction_date', ''),
        })
    elif tbk_token:
        ctx.update({
            'aprobado': False,
            'anulado': True
        })
    else:
        return redirect('planes')
    return render(
        request,
        'alumnos/confirmacion.html',
        ctx
    )



def es_profesor_habilitado_de(clase, user):
    """El titular de la clase, con su titulo aprobado (SCRUM-87)."""
    return clase.profesor.user_id == user.id and clase.profesor.puede_hacer_clases


def nombre_sala_jitsi(clase):
    """Nombre de la sala en meet.jit.si, imposible de adivinar sin SECRET_KEY.

    meet.jit.si es publico: con un nombre predecible ('lbwus-clase-privada-5')
    cualquiera entraba directo, sin pasar por ``sala_virtual``.
    """
    return 'lbwus-' + salted_hmac('lbwus.sala_virtual', str(clase.id_clase)).hexdigest()[:32]


@never_cache
@sesion_iniciada_required
def sala_virtual(request, clase_id):
    clase = get_object_or_404(
        Clase.objects.select_related('asignatura', 'profesor', 'profesor__user', 'profesor__especialidad'),
        id_clase=clase_id
    )

    # Se decide por la cuenta (request.user), no por las claves de sesion:
    # 1. Profesor titular de la clase, con titulo aprobado.
    es_profesor = es_profesor_habilitado_de(clase, request.user)
    # 2. Alumno con una inscripcion que permita entrar (Inscripcion.puede_unirse).
    #    Menores: solo clases pagadas por su apoderado con vinculo vigente.
    menor = es_menor(request.user)
    es_alumno = not es_profesor and any(
        insc.puede_unirse and (not menor or clase_pagada_por_apoderado(insc))
        for insc in Inscripcion.objects.filter(alumno__user=request.user, clase=clase).select_related('sesion', 'alumno')
    )
    # Nadie mas entra: ni administradores, ni staff, ni el campo ``rol`` (SCRUM-87).
    if not (es_profesor or es_alumno):
        return HttpResponseForbidden("Acceso denegado: debes estar inscrito activamente en la clase o ser el profesor asignado.")

    context = {
        'clase': clase,
        'es_profesor': es_profesor,
        # Iniciar el directo es un POST con @profesor_required_json: el boton
        # solo aparece con el rol profesor activo (los demas esperan el directo).
        'puede_iniciar': es_profesor and rol_en_sesion(request) is PROFESOR,
        'sala_jitsi': nombre_sala_jitsi(clase),
    }
    return render(request, 'alumnos/sala_virtual.html', context)


@profesor_required_json
@require_POST
def iniciar_directo(request, clase_id):
    clase = get_object_or_404(Clase.objects.select_related('profesor'), id_clase=clase_id)

    # Solo el profesor titular de la clase, con titulo aprobado, puede iniciar
    if not es_profesor_habilitado_de(clase, request.user):
        return JsonResponse({'success': False, 'message': 'No tienes permiso.'}, status=403)

    descripcion = request.POST.get('descripcion_vivo', '').strip()[:2000]
    temas = request.POST.get('temas_vivo', '').strip()[:255]

    clase.descripcion_vivo = descripcion
    clase.temas_vivo = temas
    clase.en_vivo = True
    clase.save(update_fields=['descripcion_vivo', 'temas_vivo', 'en_vivo'])

    return JsonResponse({'success': True})
