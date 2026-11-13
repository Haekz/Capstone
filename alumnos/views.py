from django.utils import timezone
import random
import uuid
import json
import os
import secrets

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.debug import sensitive_post_parameters
from django.core.cache import cache
from django.db.models import F, Q

from .models import (
    Alumno,
    Genero,
    Profesor,
    Reporte,
    Clase,
    SesionClase,
    Inscripcion,
    Pago,
    PaqueteClases,
    Suscripcion,
)
from django.core.exceptions import ValidationError
from .forms import AlumnoForm, FiltroClasesForm
from .decorators import alumno_required, profesor_required_json
from .exceptions import InscripcionError
from .services import InscripcionService, PlanesService
from .utils import formato_clp, es_menor
from .templatetags.dinero import clp as _clp
from . import paquetes
from django.db import transaction
from apoderados.permisos import clase_pagada_por_apoderado, vinculo_contratable
from .roles import (
    ALUMNO,
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


PERIODOS = {
    'mensual': 1,
    '3semanas': 0.75,
    '2semanas': 0.50,
    '1semana': 0.25,
}

PRECIOS_PLANES_OFICIALES = {
    # Planes vigentes (S4-03): Tarifa base $15.000 / $59.000 / $116.000
    'plan_flexible': 15000,
    'plan_progreso': 59000,
    'plan_intensivo': 116000,
    'flexible': 15000,
    'progreso': 59000,
    'intensivo': 116000,
    # Retrocompatibilidad con planes heredados (Sprint 3 / Tests)
    '1': 89990,
    '2': 139990,
    '3': 189990,
}

def _precio_item(item):
    item_id = str(item.get('id', ''))
    if item_id in PRECIOS_PLANES_OFICIALES:
        base = PRECIOS_PLANES_OFICIALES[item_id]
    else:
        base = int(
            ''.join(
                c for c in str(item.get('precio', '0'))
                if c.isdigit()
            ) or 0
        )
    factor = PERIODOS.get(item.get('periodo', 'mensual'), 1)
    try:
        cantidad = max(1, min(int(item.get('cantidad', 1)), 20))
    except (ValueError, TypeError):
        cantidad = 1
    return round(base * factor) * cantidad

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
        'profesores': Profesor.objects.habilitados().select_related('user', 'especialidad')
                                                    .order_by('user__first_name', 'user__last_name'),
        'profesor': profesor,
        'tarifa': tarifa,
        'tarifa_base': paquetes.TARIFA_BASE,
        'cotizaciones': paquetes.cotizar(tarifa),
        'duracion_clase': paquetes.DURACION_CLASE_MIN,
        'comision_pct': int(paquetes.COMISION * 100),
        'es_alumno': bool(request.session.get('alumno_id')),
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


def contactos(request):
    context = {}
    return render(
        request,
        'alumnos/contactos.html',
        context
    )


def simulador(request):
    context = {}
    return render(
        request,
        'alumnos/simulador.html',
        context
    )


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

    context = {
        'alumno': alumno,
        'mis_reportes': mis_reportes,
        'profesores_list': profesores_list,
        # Solo datos reales. Distancia, calificacion y precio no se
        # registran todavia en la plataforma, asi que no se inventan.
        'profesores_js': [
            {
                'id': p.id_profesor,
                'name': p.nombre,
                'specialties': [p.especialidad.nombre] if p.especialidad else [],
                'initial': p.nombre[:1].upper(),
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
        'plan_activo': _plan_para_js(alumno),
        'mis_paquetes': mis_paquetes,
        'pagos': pagos,
        'es_menor': es_menor(alumno.user),
        'tiene_solicitud': hasattr(alumno, 'solicitud_apoderado'),  # adolescente de 14 a 17 (apoderados)
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


def _estado_rate_limit_login(request, username):
    """Obtiene claves de caché y conteos de intentos fallidos para IP y usuario."""
    ip = _obtener_ip(request)
    # Mismo contador para todas las formas de escribir el RUT.
    canon_user = obtener_identificador_rate_limit(username)
    clave_ip = f'intentos_login_ip_{ip}'
    clave_user = f'intentos_login_user_{canon_user}'
    intentos_ip = cache.get(clave_ip, 0)
    intentos_user = cache.get(clave_user, 0)
    return {
        'clave_ip': clave_ip,
        'clave_user': clave_user,
        'canon_user': canon_user,
        'intentos_ip': intentos_ip,
        'intentos_user': intentos_user,
        'bloqueado': intentos_ip >= 15 or intentos_user >= 5,
    }


def _registrar_fallo_login(rate_limit):
    """Incrementa contadores de intentos fallidos en caché por 5 minutos."""
    cache.set(rate_limit['clave_ip'], rate_limit['intentos_ip'] + 1, 300)
    if rate_limit['canon_user']:
        cache.set(rate_limit['clave_user'], rate_limit['intentos_user'] + 1, 300)


def _autenticar_y_abrir_sesion(request, username, password, rate_limit):
    """Autentica credenciales, resuelve el rol y abre sesión o retorna mensaje de error."""
    user = authenticate(request, username=username, password=password)
    if user is None:
        _registrar_fallo_login(rate_limit)
        return None, "RUT/Correo o contraseña incorrectos. Inténtalo de nuevo."

    cache.delete(rate_limit['clave_ip'])
    cache.delete(rate_limit['clave_user'])

    # El rol lo define el perfil asociado (ver alumnos/roles.py). Sin perfil no se abre sesion.
    rol, perfil = resolver_rol(user)
    if rol is None:
        return None, "Tu cuenta no tiene un perfil asignado en el sistema."

    auth_login(request, user)
    abrir_sesion_rol(request, rol, perfil)
    return redirigir_a_portal(rol), None


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

    if request.method != 'POST':
        return render(request, 'registration/login.html', {'error': None})

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    rate_limit = _estado_rate_limit_login(request, username)

    if rate_limit['bloqueado']:
        return render(
            request,
            'registration/login.html',
            {
                'error': (
                    "Demasiados intentos fallidos. "
                    "Por seguridad, el acceso ha sido bloqueado "
                    "temporalmente por 5 minutos."
                )
            },
        )

    if not username or not password:
        return render(request, 'registration/login.html', {'error': "Por favor ingrese todos los campos."})

    respuesta_portal, error = _autenticar_y_abrir_sesion(request, username, password, rate_limit)
    if respuesta_portal is not None:
        return respuesta_portal

    return render(request, 'registration/login.html', {'error': error})


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
# REPORTES
# ============================================================

def enviar_reporte(request):

    if request.method == 'POST':

        try:

            data = json.loads(
                request.body
            )

            descripcion = str(data.get('descripcion', '')).strip()[:2000]

            alumno_id = request.session.get(
                'alumno_id'
            )

            profesor_id = request.session.get(
                'profesor_id'
            )

            if not descripcion:

                return JsonResponse({
                    "success": False,
                    "message": (
                        "La descripción no "
                        "puede estar vacía."
                    )
                })

            # Reporte desde alumno

            if alumno_id:

                alumno = Alumno.objects.get(
                    id_alumno=alumno_id
                )

                Reporte.objects.create(
                    remitente=alumno.user,
                    descripcion=descripcion
                )

                return JsonResponse({
                    "success": True
                })

            # Reporte desde profesor

            elif profesor_id:

                profesor = Profesor.objects.get(
                    id_profesor=profesor_id
                )

                Reporte.objects.create(
                    remitente=profesor.user,
                    descripcion=descripcion
                )

                return JsonResponse({
                    "success": True
                })

            else:

                return JsonResponse({
                    "success": False,
                    "message": (
                        "No hay sesión activa."
                    )
                })

        except Exception:

            return JsonResponse({
                "success": False,
                "message": "Ocurrió un error inesperado al registrar el reporte."
            })

    return JsonResponse({
        "success": False,
        "message": "Método no permitido."
    })


# ============================================================
# INSCRIPCIÓN DE CLASES
# ============================================================

def inscribir_clase(request):

    alumno_id = request.session.get(
        'alumno_id'
    )

    if not alumno_id:

        return JsonResponse({
            'success': False,
            'message': (
                'Debes iniciar sesión como '
                'alumno para inscribirte.'
            )
        })

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

    alumno_id = request.session.get('alumno_id') if hasattr(request, 'session') else None
    inscritas_sesion_ids = set()
    if alumno_id:
        inscritas_sesion_ids = set(
            Inscripcion.objects.filter(
                alumno_id=alumno_id,
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


def reservar_sesion(request):
    """Endpoint para que un alumno autenticado reserve un cupo en una SesionClase puntual."""
    alumno_id = request.session.get('alumno_id')
    if not alumno_id:
        return JsonResponse({
            'success': False,
            'message': 'Debes iniciar sesión como alumno para reservar una sesión.'
        }, status=401)

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
    # Menores: contrata su apoderado. Unico inicio de Webpay.
    if es_menor(get_object_or_404(Alumno, id_alumno=request.session['alumno_id']).user):
        return redirect('alumno_pag1')
    return iniciar_compra_paquete(request, request.session['alumno_id'])


def iniciar_compra_paquete(request, alumno_id, al_crear=None):
    """Unico inicio de Webpay para paquetes: lo usan el alumno y el apoderado.

    Plan y profesor vienen del POST; el monto lo calcula el servidor. ``al_crear``
    recibe el paquete dentro de la misma transaccion (la compra del apoderado).
    """
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


def _simulacion_permitida(user):
    if not getattr(settings, 'WEBPAY_SIMULACION_ACTIVADA', True):
        return False
    usuarios_permitidos = getattr(settings, 'USUARIOS_SIMULACION_WEBPAY', ['*'])
    if '*' in usuarios_permitidos:
        return True
    if user and user.is_authenticated:
        return (
            user.is_staff
            or user.is_superuser
            or user.username in usuarios_permitidos
            or user.email in usuarios_permitidos
        )
    return False


def _parsear_carrito_y_monto_webpay(request):
    """Extrae el carrito desde POST y calcula el monto total validando mínimo Webpay."""
    carrito_json = request.POST.get('carrito', '[]')
    try:
        carrito = json.loads(carrito_json)
    except (ValueError, TypeError):
        return None
    if not isinstance(carrito, list) or not carrito:
        return None
    monto = sum(_precio_item(item) for item in carrito)
    if monto < 350:
        return None
    return carrito, carrito_json, monto


def _resolver_alumno_webpay(request):
    """Obtiene el Alumno asociado al usuario autenticado o a la sesión actual."""
    alumno_obj = None
    if request.user.is_authenticated:
        alumno_obj = Alumno.objects.filter(user=request.user).first()
    if not alumno_obj and request.session.get('alumno_id'):
        alumno_obj = Alumno.objects.filter(pk=request.session.get('alumno_id')).first()
    return alumno_obj


def _guardar_orden_pendiente_sesion(request, buy_order, carrito_json, pago, token, amount):
    """Persiste en sesión el resumen de la orden en curso para la vista de confirmación."""
    request.session['orden_pendiente'] = {
        'buy_order': buy_order,
        'carrito': carrito_json,
        'pago_id': pago.id_pago,
        'token': token,
        'amount': amount,
    }


def _procesar_webpay_simulado(request, alumno_obj, carrito, carrito_json, amount, session_id):
    """Crea un pago aprobado en modo simulación y redirige directamente a confirmación."""
    token_sim = f'sim_{uuid.uuid4().hex[:20]}'
    buy_order_sim = f'LB-SIM-{random.randrange(100000, 999999)}'
    pago = Pago.objects.create(
        buy_order=buy_order_sim,
        session_id=session_id,
        token_ws=token_sim,
        monto=amount,
        estado=Pago.ESTADO_PAGADA,
        es_simulacion=True,
        usuario=request.user if request.user.is_authenticated else None,
        alumno=alumno_obj,
        detalle_carrito=carrito,
        authorization_code=str(random.randint(100000, 999999)),
        ultimos_digitos_tarjeta='6623',
        fecha_transaccion=timezone.now(),
    )
    _guardar_orden_pendiente_sesion(request, buy_order_sim, carrito_json, pago, token_sim, amount)
    return redirect(f"{reverse('confirmacion')}?token_ws={token_sim}")


def _procesar_webpay_real(request, alumno_obj, carrito, carrito_json, amount, buy_order, session_id):
    """Registra el Pago inicial, crea la transacción en Transbank y renderiza el redirect."""
    pago = Pago.objects.create(
        buy_order=buy_order,
        session_id=session_id,
        monto=amount,
        estado=Pago.ESTADO_INICIADA,
        es_simulacion=False,
        usuario=request.user if request.user.is_authenticated else None,
        alumno=alumno_obj,
        detalle_carrito=carrito,
    )
    return_url = request.build_absolute_uri(reverse('confirmacion'))
    try:
        response = _tx().create(buy_order, session_id, amount, return_url)
        pago.token_ws = response['token']
        pago.save(update_fields=['token_ws'])
    except Exception:
        pago.estado = Pago.ESTADO_RECHAZADA
        pago.save(update_fields=['estado'])
        return redirect('planes')

    _guardar_orden_pendiente_sesion(request, buy_order, carrito_json, pago, response['token'], amount)
    return render(
        request,
        'alumnos/redirect_webpay.html',
        {'url': response['url'], 'token': response['token']},
    )


def iniciar_webpay(request):
    if request.method != 'POST':
        return redirect('planes')

    parsed = _parsear_carrito_y_monto_webpay(request)
    if parsed is None:
        return redirect('planes')
    carrito, carrito_json, amount = parsed

    buy_order = 'LB' + str(random.randrange(1000000, 9999999))
    session_id = 'S' + str(random.randrange(1000000, 9999999))
    alumno_obj = _resolver_alumno_webpay(request)

    es_simulacion = request.POST.get('simular') == '1' or request.GET.get('simular') == '1'
    if es_simulacion and _simulacion_permitida(request.user):
        return _procesar_webpay_simulado(request, alumno_obj, carrito, carrito_json, amount, session_id)

    return _procesar_webpay_real(request, alumno_obj, carrito, carrito_json, amount, buy_order, session_id)


def _buscar_pago_confirmacion(token, tbk_token, orden):
    """Localiza el registro Pago usando token_ws, TBK_TOKEN o los datos en sesión."""
    pago = None
    if token:
        pago = Pago.objects.filter(token_ws=token).first()
    elif tbk_token:
        pago = Pago.objects.filter(token_ws=tbk_token).first()

    if not pago and orden.get('pago_id'):
        pago = Pago.objects.filter(pk=orden.get('pago_id')).first()
    if not pago and orden.get('buy_order'):
        pago = Pago.objects.filter(buy_order=orden.get('buy_order')).first()
    return pago


def _cargar_carrito_e_items(orden, pago):
    """Reconstruye el carrito desde sesión o desde Pago y formatea sus ítems para plantilla."""
    try:
        carrito = json.loads(orden.get('carrito', '[]'))
    except (ValueError, TypeError):
        carrito = []

    if not carrito and pago and pago.detalle_carrito:
        carrito = pago.detalle_carrito

    items = [
        {
            'titulo': item.get('titulo', ''),
            'cantidad': item.get('cantidad', 1),
            'precio': _clp(_precio_item(item)),
        }
        for item in carrito
    ]
    return carrito, items


def _respuesta_estado_previo(request, pago, token, tbk_token, orden, ctx):
    """Resuelve anulación en pasarela, falta de token o pagos ya procesados (idempotencia)."""
    if tbk_token:
        if pago:
            pago.estado = Pago.ESTADO_ANULADA
            pago.save(update_fields=['estado', 'updated_at'])
        ctx.update({
            'aprobado': False,
            'anulado': True,
            'orden': pago.buy_order if pago else orden.get('buy_order', ''),
        })
        return render(request, 'alumnos/confirmacion.html', ctx)

    if not token:
        return redirect('planes')

    if pago and pago.estado == Pago.ESTADO_PAGADA:
        ctx.update({
            'aprobado': True,
            'orden': pago.buy_order,
            'monto': _clp(pago.monto),
            'codigo_autorizacion': pago.authorization_code,
            'tarjeta': pago.ultimos_digitos_tarjeta or '6623',
            'fecha': str(pago.fecha_transaccion or pago.created_at),
        })
        return render(request, 'alumnos/confirmacion.html', ctx)

    if pago and pago.estado in (Pago.ESTADO_RECHAZADA, Pago.ESTADO_ANULADA):
        ctx.update({
            'aprobado': False,
            'anulado': (pago.estado == Pago.ESTADO_ANULADA),
            'orden': pago.buy_order,
            'monto': _clp(pago.monto),
        })
        return render(request, 'alumnos/confirmacion.html', ctx)

    return None


def _actualizar_pago_confirmado(pago, buy_order, aprobado, resp):
    """Actualiza el estado del Pago según la respuesta final validada de Transbank."""
    if not pago and buy_order:
        pago = Pago.objects.filter(buy_order=buy_order).first()
    if not pago:
        return

    card = resp.get('card_detail') or {}
    if aprobado:
        pago.estado = Pago.ESTADO_PAGADA
        pago.authorization_code = resp.get('authorization_code', '')
        pago.ultimos_digitos_tarjeta = card.get('card_number', '')
        pago.fecha_transaccion = timezone.now()
        pago.save()
    else:
        pago.estado = Pago.ESTADO_RECHAZADA
        pago.save(update_fields=['estado', 'updated_at'])


def _evaluar_aprobacion_transbank(resp, expected_order, expected_amount):
    """Valida respuesta AUTHORIZED de Transbank contra orden, monto y paquete asociado."""
    resp_order = resp.get('buy_order', '')
    resp_amount = int(resp.get('amount', 0))
    aprobado_tbk = (resp.get('response_code') == 0 and resp.get('status') == 'AUTHORIZED')
    orden_valida = (not expected_order or resp_order == expected_order)
    monto_valido = (not expected_amount or resp_amount == int(expected_amount))
    aprobado = bool(aprobado_tbk and orden_valida and monto_valido)

    buy_order = resp_order or expected_order
    paquete = PaqueteClases.objects.filter(buy_order=buy_order).first() if buy_order else None
    if paquete and int(resp.get('amount') or 0) != paquete.monto:
        aprobado = False
    return buy_order, aprobado


def _items_paquetes_por_orden(buy_order):
    """Construye el listado visual de paquetes asociados a un buy_order."""
    return [
        {
            'titulo': f'{p.get_plan_display()}: {p.clases} clase(s) con {p.profesor.nombre if p.profesor else "—"}',
            'cantidad': 1,
            'precio': _clp(p.monto),
        }
        for p in PaqueteClases.objects.filter(buy_order=buy_order).select_related('profesor__user')
    ]


def _confirmar_con_transbank(token, pago, orden, carrito, ctx):
    """Ejecuta commit en Transbank, valida orden/monto y aplica efectos en modelos."""
    expected_order = pago.buy_order if pago else orden.get('buy_order', '')
    expected_amount = pago.monto if pago else orden.get('amount')
    if expected_amount is None and carrito:
        expected_amount = sum(_precio_item(it) for it in carrito)

    try:
        resp = _tx().commit(token)
    except Exception:
        if pago:
            pago.estado = Pago.ESTADO_RECHAZADA
            pago.save(update_fields=['estado', 'updated_at'])
        ctx.update({
            'aprobado': False,
            'orden': expected_order,
            'monto': _clp(expected_amount or 0),
        })
        return ctx

    buy_order, aprobado = _evaluar_aprobacion_transbank(resp, expected_order, expected_amount)
    Suscripcion.confirmar_pago(buy_order, aprobado)
    PaqueteClases.confirmar_pago(buy_order, aprobado)

    if not ctx['items'] and buy_order:
        ctx['items'] = _items_paquetes_por_orden(buy_order)

    _actualizar_pago_confirmado(pago, buy_order, aprobado, resp)
    card = resp.get('card_detail') or {}
    ctx.update({
        'aprobado': aprobado,
        'orden': buy_order,
        'monto': _clp(resp.get('amount', expected_amount or 0)),
        'codigo_autorizacion': resp.get('authorization_code', ''),
        'tarjeta': card.get('card_number', ''),
        'fecha': resp.get('transaction_date', ''),
    })
    return ctx


@csrf_exempt
def confirmacion(request):
    token = request.GET.get('token_ws') or request.POST.get('token_ws')
    tbk_token = request.GET.get('TBK_TOKEN') or request.POST.get('TBK_TOKEN')
    orden = request.session.pop('orden_pendiente', {})

    pago = _buscar_pago_confirmacion(token, tbk_token, orden)
    carrito, items = _cargar_carrito_e_items(orden, pago)
    ctx = {'items': items}

    respuesta_previa = _respuesta_estado_previo(request, pago, token, tbk_token, orden, ctx)
    if respuesta_previa is not None:
        return respuesta_previa

    ctx = _confirmar_con_transbank(token, pago, orden, carrito, ctx)
    return render(request, 'alumnos/confirmacion.html', ctx)




@never_cache
def sala_virtual(request, clase_id):
    if not request.user.is_authenticated:
        return redirect('custom_login_alumno')

    clase = get_object_or_404(
        Clase.objects.select_related('asignatura', 'profesor', 'profesor__user', 'profesor__especialidad'),
        id_clase=clase_id
    )

    # Validar autorización:
    # 1. Profesor de la clase
    es_profesor = (
        hasattr(clase, 'profesor')
        and (clase.profesor.user_id == request.user.id
             or request.session.get('profesor_id') == getattr(clase.profesor, 'id_profesor', None))
    )
# 2. Alumno con una inscripcion que permita entrar (Inscripcion.puede_unirse).
    #    Menores: solo clases pagadas por su apoderado con vinculo vigente.
    propias = Q(alumno__user=request.user)
    if request.session.get('alumno_id'):
        propias |= Q(alumno_id=request.session['alumno_id'])
    menor = es_menor(request.user)
    es_alumno = any(
        insc.puede_unirse and (not menor or clase_pagada_por_apoderado(insc))
        for insc in Inscripcion.objects.filter(propias, clase=clase).select_related('sesion', 'alumno')
    )
    if not (es_profesor or es_alumno):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Acceso denegado: debes estar inscrito activamente en la clase o ser el profesor asignado.")

    context = {
        'clase': clase,
        'es_profesor': es_profesor,
    }
    return render(request, 'alumnos/sala_virtual.html', context)


@profesor_required_json
@require_POST
def iniciar_directo(request, clase_id):
    clase = get_object_or_404(Clase.objects.select_related('profesor'), id_clase=clase_id)

    # Solo el profesor titular de la clase puede iniciar
    profesor_id = request.session.get('profesor_id')
    if not profesor_id or str(clase.profesor.id_profesor) != str(profesor_id):
        return JsonResponse({'success': False, 'message': 'No tienes permiso.'}, status=403)

    descripcion = request.POST.get('descripcion_vivo', '').strip()[:2000]
    temas = request.POST.get('temas_vivo', '').strip()[:255]

    clase.descripcion_vivo = descripcion
    clase.temas_vivo = temas
    clase.en_vivo = True
    clase.save(update_fields=['descripcion_vivo', 'temas_vivo', 'en_vivo'])

    return JsonResponse({'success': True})
