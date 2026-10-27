import json
import secrets

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
    Tutor,
    Profesor,
    Reporte,
    Clase,
    SesionClase,
    Inscripcion,
    PaqueteClases,
    Suscripcion,
)
from django.core.exceptions import ValidationError
from . import paquetes
from .forms import AlumnoForm, FiltroClasesForm
from .decorators import alumno_required
from .exceptions import InscripcionError
from .services import InscripcionService
from .utils import es_menor
from .templatetags.dinero import clp as _clp  # mismo formato en vistas y plantillas
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


def _tx():
    return Transaction(
        WebpayOptions(
            IntegrationCommerceCodes.WEBPAY_PLUS,
            IntegrationApiKeys.WEBPAY,
            IntegrationType.TEST,
        )
    )


def _plan_para_js(alumno):
    """Plan vigente en el formato que usa el JS del portal, o None si no tiene.

    Un paquete vigente es el plan activo. Las suscripciones de antes de los
    paquetes siguen valiendo hasta que venzan.
    """
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
    ).order_by('user__first_name', 'user__last_name')

    # Catalogo: solo clases de profesores habilitados, con los filtros del GET.
    filtros = FiltroClasesForm(request.GET)
    filtros.is_valid()  # un campo invalido queda fuera de cleaned_data y no filtra
    criterios = filtros.cleaned_data
    clases_disponibles = Clase.objects.habilitadas().filtrar(
        especialidad=criterios.get('especialidad'),
        modalidad=criterios.get('modalidad'),
        solo_disponibles=criterios.get('disponible', False),
    ).select_related('asignatura', 'profesor__user', 'profesor__especialidad')

    # Mis clases: proximas primero por fecha de sesion; las ya realizadas van al historial.
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
    # Historial: paquetes y suscripciones antiguas, del mas nuevo al mas viejo.
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
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


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
        clave_cache_ip = f'intentos_login_ip_{ip}'
        clave_cache_user = f'intentos_login_user_{username.lower()}'

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
                if username:
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
        # Ya empezo o no esta activa. Antes se borraba la inscripcion: con
        # paquetes eso devolveria una clase ya tomada.
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
    # Menores: la contratacion sera del apoderado (fase 1c). Unico inicio de Webpay.
    if es_menor(get_object_or_404(Alumno, id_alumno=request.session['alumno_id']).user):
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

    PaqueteClases.objects.create(
        alumno_id=request.session['alumno_id'], profesor=profesor, plan=plan.codigo,
        clases=plan.clases, tarifa=profesor.tarifa, monto=monto, dias=plan.vigencia_dias,
        buy_order=buy_order,
    )
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
            resp = _tx().commit(
                token
            )
        except Exception:  # token invalido/expirado o Transbank caido: no se activa nada
            resp = {}

        aprobado = (
            resp.get(
                'response_code'
            ) == 0
            and
            resp.get(
                'status'
            ) == 'AUTHORIZED'
        )

        card = (
            resp.get(
                'card_detail'
            )
            or {}
        )

        # El buy_order viene de Transbank (commit), no del navegador.
        # confirmar_pago es idempotente: repetir el token no activa dos veces.
        buy_order = resp.get('buy_order', '')
        # El monto autorizado por Transbank debe ser el del paquete pedido (idea de la rama Franco).
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

    # Pago cancelado/anulado

    elif tbk_token:

        ctx.update({
            'aprobado': False,
            'anulado': True
        })

    else:

        return redirect(
            'planes'
        )

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
    # 2. Alumno con una inscripcion que permita entrar (Inscripcion.puede_unirse)
    propias = Q(alumno__user=request.user)
    if request.session.get('alumno_id'):
        propias |= Q(alumno_id=request.session['alumno_id'])
    es_alumno = any(
        insc.puede_unirse
        for insc in Inscripcion.objects.filter(propias, clase=clase).select_related('sesion')
    )
    # Nadie mas entra: ni administradores, ni staff, ni el campo ``rol``. Antes
    # bastaba rol 'admin'/'tutor' para abrir cualquier clase (decision 10, menores).
    # Menores: sin clases virtuales hasta la fase 1c, aunque tengan inscripcion.
    if not (es_profesor or (es_alumno and not es_menor(request.user))):
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
