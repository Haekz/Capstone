import os
import uuid
from django.utils import timezone
from django.conf import settings
import json
import random

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.debug import sensitive_post_parameters
from django.core.cache import cache

from .models import (
    Alumno,
    Genero,
    Tutor,
    Profesor,
    Reporte,
    Clase,
    SesionClase,
    Inscripcion,
    Pago,
)
from django.core.exceptions import ValidationError
from .forms import AlumnoForm
from .decorators import alumno_required
from .exceptions import InscripcionError
from .services import InscripcionService, PlanesService
from .backends import obtener_identificador_rate_limit
from .roles import (
    ALUMNO,
    abrir_sesion_rol,
    redirigir_a_portal,
    resolver_rol,
    rol_en_sesion,
)


# ============================================================
# TRANSBANK - WEBPAY PLUS
# Ambiente de integración
# ============================================================

from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_type import IntegrationType


PERIODOS = {
    'mensual': 1,
    '3semanas': 0.75,
    '2semanas': 0.50,
    '1semana': 0.25,
}


def _tx():
    return Transaction(
        WebpayOptions(
            IntegrationCommerceCodes.WEBPAY_PLUS,
            IntegrationApiKeys.WEBPAY,
            IntegrationType.TEST,
        )
    )


def _clp(n):
    return '$' + f'{int(n):,}'.replace(',', '.')


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

    factor = PERIODOS.get(
        item.get('periodo', 'mensual'),
        1
    )

    try:
        cantidad = max(1, min(int(item.get('cantidad', 1)), 20))
    except (ValueError, TypeError):
        cantidad = 1

    return round(base * factor) * cantidad


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
    profesor_id = request.GET.get('profesor_id')
    profesor = None
    if profesor_id:
        try:
            profesor = Profesor.objects.select_related('user', 'especialidad').get(pk=profesor_id)
        except (Profesor.DoesNotExist, ValueError):
            profesor = None

    planes_data = PlanesService.calcular_planes(profesor=profesor)
    tarifa_base_ref = PlanesService.obtener_tarifa_base_profesor(profesor)

    if request.GET.get('format') == 'json' or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'planes': planes_data,
            'profesor': {
                'id': profesor.id_profesor,
                'nombre': profesor.nombre,
                'tarifa_base': tarifa_base_ref,
            } if profesor else None,
            'status': 'ok'
        })

    context = {
        'planes': planes_data,
        'profesor_seleccionado': profesor,
        'tarifa_base_referencia': tarifa_base_ref,
    }
    return render(
        request,
        'alumnos/planes.html',
        context
    )


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

    generos = Genero.objects.all()

    return render(
        request,
        'alumnos/regis_alum.html',
        {
            'generos': generos
        }
    )


# ============================================================
# PORTAL DEL ALUMNO
# ============================================================

@never_cache
@alumno_required
def alumno_pag1(request):

    alumno_id = request.session['alumno_id']

    alumno = get_object_or_404(
        Alumno,
        id_alumno=alumno_id
    )

    mis_reportes = Reporte.objects.filter(
        remitente=alumno.user
    ).order_by(
        '-fecha_reporte'
    )

    # Solo profesores con titulo aprobado pueden hacer clases.
    profesores_list = Profesor.objects.habilitados().select_related(
        'user',
        'especialidad'
    )

    clases_disponibles = Clase.objects.all().select_related(
        'profesor'
    )

    mis_inscripciones = (
        Inscripcion.objects
        .filter(
            alumno=alumno,
            estado__in=['confirmada', 'pendiente']
        )
        .select_related(
            'clase',
            'clase__profesor'
        )
        .order_by(
            '-fecha_inscripcion'
        )
    )

    inscritas_ids = list(
        mis_inscripciones.values_list(
            'clase_id',
            flat=True
        )
    )

    sesiones_disponibles = (
        SesionClase.objects.disponibles()
        .select_related('clase', 'clase__asignatura', 'clase__profesor', 'clase__profesor__user')
        .order_by('fecha_hora_inicio')
    )

    context = {
        'alumno': alumno,
        'mis_reportes': mis_reportes,
        'profesores_list': profesores_list,
        'profesores_js': [
            {
                'id': p.id_profesor,
                'name': p.nombre,
                'specialties': [p.especialidad.nombre] if p.especialidad else [],
                'distance': 1.2,
                'rating': '5.0 ⭐',
                'price': '$15.000',
                'initial': p.nombre[:1].upper(),
            }
            for p in profesores_list
        ],
        'clases_disponibles': clases_disponibles,
        'sesiones_disponibles': sesiones_disponibles,
        'mis_inscripciones': mis_inscripciones,
        'inscritas_ids': inscritas_ids,
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
    """
    Obtiene una dirección IP confiable del cliente (S4-02 / S-07).
    Prioriza REMOTE_ADDR salvo en entornos con proxy inverso de confianza (ej. Railway).
    Previene evasión de límites de intentos mediante cabeceras X-Forwarded-For manipuladas.
    """
    remote_addr = request.META.get('REMOTE_ADDR', '').strip() or '127.0.0.1'
    confiar_proxy = (
        getattr(settings, 'CONFIAR_X_FORWARDED_FOR', False)
        or bool(os.environ.get('RAILWAY_ENVIRONMENT'))
    )
    if confiar_proxy:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ips = [ip.strip() for ip in x_forwarded_for.split(',') if ip.strip()]
            if ips:
                return ips[0]
    return remote_addr


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
        canon_user = obtener_identificador_rate_limit(username)
        clave_cache_ip = f'intentos_login_ip_{ip}'
        clave_cache_user = f'intentos_login_user_{canon_user}' if canon_user else 'intentos_login_user_anon'

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
                # Sin perfil no se abre sesion: antes se guardaba user.id
                # como si fuera id de alumno/tutor y se mezclaban portales.
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
                    return redirigir_a_portal(rol)

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
            'error': error
        }
    )


# ============================================================
# LOGOUT ALUMNO
# ============================================================

def logout_alumno(request):
    auth_logout(request)
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
            'fecha_formateada': s.fecha_hora_inicio.strftime('%d/%m/%Y'),
            'hora_formateada': f"{s.fecha_hora_inicio.strftime('%H:%M')} - {s.fecha_hora_fin.strftime('%H:%M')} hrs",
            'inicio_formateado': s.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M'),
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
                f'el {sesion.fecha_hora_inicio.strftime("%d/%m/%Y a las %H:%M")}!'
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
    except Exception:
        inscripcion.delete()

    return redirect('alumno_pag1')


# ============================================================
# PAGO CON WEBPAY PLUS - TRANSBANK
# ============================================================

def pago(request):

    return render(
        request,
        'alumnos/pago.html',
        {}
    )



def _simulacion_permitida(user):
    """Verifica si la simulación de Webpay está habilitada para el entorno o usuario."""
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

def iniciar_webpay(request):

    if request.method != 'POST':
        return redirect('planes')

    carrito_json = request.POST.get(
        'carrito',
        '[]'
    )

    try:
        carrito = json.loads(carrito_json)
        if not isinstance(carrito, list) or not carrito:
            return redirect('planes')
    except (ValueError, TypeError):
        return redirect('planes')

    # Validar y calcular el monto esperado desde el carrito en el servidor (Zero Trust)
    monto_calculado = sum(_precio_item(item) for item in carrito)
    if monto_calculado >= 350:
        amount = monto_calculado
    else:
        return redirect('planes')

    buy_order = (
        'LB'
        + str(
            random.randrange(
                1000000,
                9999999
            )
        )
    )

    session_id = (
        'S'
        + str(
            random.randrange(
                1000000,
                9999999
            )
        )
    )

    alumno_obj = None
    if request.user.is_authenticated:
        alumno_obj = Alumno.objects.filter(user=request.user).first()
    if not alumno_obj and request.session.get('alumno_id'):
        alumno_obj = Alumno.objects.filter(pk=request.session.get('alumno_id')).first()

    # Modo simulación de pago para pruebas/testers (sin cobro real)
    es_simulacion = request.POST.get('simular') == '1' or request.GET.get('simular') == '1'
    if es_simulacion and _simulacion_permitida(request.user):
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

        request.session['orden_pendiente'] = {
            'buy_order': buy_order_sim,
            'carrito': carrito_json,
            'pago_id': pago.id_pago,
            'token': token_sim,
            'amount': amount,
        }

        return redirect(f"{reverse('confirmacion')}?token_ws={token_sim}")

    # Registro en base de datos antes de interactuar con la pasarela Webpay
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

    return_url = (
        request.build_absolute_uri(
            reverse('confirmacion')
        )
    )

    try:
        response = _tx().create(
            buy_order,
            session_id,
            amount,
            return_url
        )
        pago.token_ws = response['token']
        pago.save(update_fields=['token_ws'])
    except Exception:
        pago.estado = Pago.ESTADO_RECHAZADA
        pago.save(update_fields=['estado'])
        return redirect('planes')

    request.session[
        'orden_pendiente'
    ] = {
        'buy_order': buy_order,
        'carrito': carrito_json,
        'pago_id': pago.id_pago,
        'token': response['token'],
        'amount': amount,
    }

    return render(
        request,
        'alumnos/redirect_webpay.html',
        {
            'url': response['url'],
            'token': response['token'],
        }
    )


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

    orden = request.session.pop(
        'orden_pendiente',
        {}
    )

    try:
        carrito = json.loads(
            orden.get(
                'carrito',
                '[]'
            )
        )
    except (ValueError, TypeError):
        carrito = []

    # Recuperar pago desde BD si existe
    pago = None
    if token:
        pago = Pago.objects.filter(token_ws=token).first()
    elif tbk_token:
        pago = Pago.objects.filter(token_ws=tbk_token).first()

    if not pago and orden.get('pago_id'):
        pago = Pago.objects.filter(pk=orden.get('pago_id')).first()
    if not pago and orden.get('buy_order'):
        pago = Pago.objects.filter(buy_order=orden.get('buy_order')).first()

    if not carrito and pago and pago.detalle_carrito:
        carrito = pago.detalle_carrito

    items = [
        {
            'titulo': item.get(
                'titulo',
                ''
            ),
            'cantidad': item.get(
                'cantidad',
                1
            ),
            'precio': _clp(
                _precio_item(item)
            ),
        }
        for item in carrito
    ]

    ctx = {
        'items': items
    }

    # 1. Pago cancelado/anulado por el usuario en pasarela
    if tbk_token:
        if pago:
            pago.estado = Pago.ESTADO_ANULADA
            pago.save(update_fields=['estado', 'updated_at'])

        ctx.update({
            'aprobado': False,
            'anulado': True,
            'orden': pago.buy_order if pago else orden.get('buy_order', ''),
        })
        return render(
            request,
            'alumnos/confirmacion.html',
            ctx
        )

    # 2. Sin tokens ni orden: redirigir a planes
    if not token:
        return redirect('planes')

    # 3. Control de Idempotencia / Prevención de doble aplicación
    if pago and pago.estado == Pago.ESTADO_PAGADA:
        ctx.update({
            'aprobado': True,
            'orden': pago.buy_order,
            'monto': _clp(pago.monto),
            'codigo_autorizacion': pago.authorization_code,
            'tarjeta': pago.ultimos_digitos_tarjeta or '6623',
            'fecha': str(pago.fecha_transaccion or pago.created_at),
        })
        return render(
            request,
            'alumnos/confirmacion.html',
            ctx
        )

    if pago and pago.estado in (Pago.ESTADO_RECHAZADA, Pago.ESTADO_ANULADA):
        ctx.update({
            'aprobado': False,
            'anulado': (pago.estado == Pago.ESTADO_ANULADA),
            'orden': pago.buy_order,
            'monto': _clp(pago.monto),
        })
        return render(
            request,
            'alumnos/confirmacion.html',
            ctx
        )

    # 4. Procesar confirmación con Transbank Webpay
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
        return render(
            request,
            'alumnos/confirmacion.html',
            ctx
        )

    card = resp.get('card_detail') or {}
    resp_order = resp.get('buy_order', '')
    resp_amount = int(resp.get('amount', 0))
    resp_code = resp.get('response_code')
    resp_status = resp.get('status')

    # Validación cruzada: estado pasarela, orden y monto coincidente
    aprobado_tbk = (resp_code == 0 and resp_status == 'AUTHORIZED')
    orden_valida = (not expected_order or resp_order == expected_order)
    monto_valido = (not expected_amount or resp_amount == int(expected_amount))

    aprobado = bool(aprobado_tbk and orden_valida and monto_valido)

    if pago:
        if aprobado:
            pago.estado = Pago.ESTADO_PAGADA
            pago.authorization_code = resp.get('authorization_code', '')
            pago.ultimos_digitos_tarjeta = card.get('card_number', '')
            pago.fecha_transaccion = timezone.now()
            pago.save()

            # S4-03 / S4-09: Activación, desglose y acreditación contable para el alumno
            if pago.alumno:
                from .models import PlanAlumno, DesgloseOperacion
                from .services import LiquidacionService
                tiene_planes = False
                for item in pago.detalle_carrito:
                    item_id = str(item.get('id', ''))
                    if item_id in PRECIOS_PLANES_OFICIALES:
                        tiene_planes = True
                        # Evitar duplicados por idempotencia de webhook/callback
                        if not PlanAlumno.objects.filter(pago=pago, tipo_plan=item_id).exists():
                            PlanesService.crear_plan_desde_pago(
                                alumno=pago.alumno,
                                tipo_plan_str=item_id,
                                pago=pago
                            )
                # Si la compra fue puntual (no paquete), registrar desglose individual
                if not tiene_planes and not DesgloseOperacion.objects.filter(pago=pago).exists():
                    LiquidacionService.registrar_compra(
                        pago=pago,
                        alumno=pago.alumno,
                        tipo_operacion=DesgloseOperacion.TIPO_CLASE_INDIVIDUAL
                    )
        else:
            pago.estado = Pago.ESTADO_RECHAZADA
            pago.save(update_fields=['estado', 'updated_at'])

    ctx.update({
        'aprobado': aprobado,

        'orden': resp.get(
            'buy_order',
            orden.get(
                'buy_order',
                ''
            )
        ),

        'monto': _clp(
            resp.get(
                'amount',
                0
            )
        ),

        'codigo_autorizacion': (
            resp.get(
                'authorization_code',
                ''
            )
        ),

        'tarjeta': card.get(
            'card_number',
            ''
        ),

        'fecha': resp.get(
            'transaction_date',
            ''
        ),
    })

    return render(
        request,
        'alumnos/confirmacion.html',
        ctx
    )



def sala_virtual(request, clase_id):
    if not request.user.is_authenticated:
        return redirect('custom_login_alumno')

    clase = get_object_or_404(Clase, id_clase=clase_id)

    # Validar autorización:
    # 1. Profesor de la clase
    es_profesor = (
        hasattr(clase, 'profesor')
        and (clase.profesor.user_id == request.user.id
             or request.session.get('profesor_id') == getattr(clase.profesor, 'id_profesor', None))
    )
    # 2. Alumno inscrito en la clase
    es_alumno = Inscripcion.objects.filter(
        clase=clase,
        alumno__user=request.user
    ).exists() or bool(
        request.session.get('alumno_id')
        and Inscripcion.objects.filter(clase=clase, alumno_id=request.session['alumno_id']).exists()
    )
    # 3. Administrador o Tutor
    es_admin = bool(
        request.user.is_superuser
        or request.user.is_staff
        or request.session.get('tutor_id')
        or getattr(request.user, 'rol', None) in ('admin', 'tutor')
    )

    if not (es_profesor or es_alumno or es_admin):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Acceso denegado: debes estar inscrito en la clase o ser el profesor asignado.")

    context = {
        'clase': clase,
        'es_profesor': es_profesor,
    }
    return render(request, 'alumnos/sala_virtual.html', context)


from django.views.decorators.http import require_POST

@require_POST
def iniciar_directo(request, clase_id):
    clase = get_object_or_404(Clase, id_clase=clase_id)
    
    # Solo el profesor de la clase puede iniciar
    profesor_id = request.session.get('profesor_id')
    if not profesor_id or str(clase.profesor.id_profesor) != str(profesor_id):
        return JsonResponse({'success': False, 'message': 'No tienes permiso.'})
        
    descripcion = request.POST.get('descripcion_vivo', '')
    temas = request.POST.get('temas_vivo', '')
    
    clase.descripcion_vivo = descripcion
    clase.temas_vivo = temas
    clase.en_vivo = True
    clase.save()
    
    return JsonResponse({'success': True})
