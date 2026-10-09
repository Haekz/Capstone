import json
import random

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from .models import (
    Alumno,
    Genero,
    Tutor,
    Profesor,
    Reporte,
    Clase,
    Inscripcion,
)
from .forms import AlumnoForm


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


def _precio_item(item):
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

    cantidad = int(
        item.get('cantidad', 1)
    )

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
    context = {}
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

            request.session['alumno_id'] = alumno.id_alumno

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

            request.session['alumno_id'] = alumno.id_alumno

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
def alumno_pag1(request):

    alumno_id = request.session.get(
        'alumno_id'
    )

    if not alumno_id:
        return redirect('login')

    alumno = get_object_or_404(
        Alumno,
        id_alumno=alumno_id
    )

    mis_reportes = Reporte.objects.filter(
        remitente=alumno.user
    ).order_by(
        '-fecha_reporte'
    )

    profesores_list = Profesor.objects.all()

    clases_disponibles = Clase.objects.all().select_related(
        'profesor'
    )

    mis_inscripciones = (
        Inscripcion.objects
        .filter(
            alumno=alumno
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

    context = {
        'alumno': alumno,
        'mis_reportes': mis_reportes,
        'profesores_list': profesores_list,
        'clases_disponibles': clases_disponibles,
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

# never_cache: si el navegador guarda el login, al volver "atras" desde el
# portal muestra esa copia (con los datos escritos) en vez de preguntarle al
# servidor, que habria redirigido al portal porque la sesion sigue activa.
@never_cache
def custom_login(request):

    # Si ya existe una sesión activa,
    # redirigir al portal correspondiente.

    if request.session.get('alumno_id'):
        return redirect(
            'alumno_pag1'
        )

    if request.session.get('profesor_id'):
        return redirect(
            'panel_profesor'
        )

    if request.session.get('admin_id'):
        return redirect(
            'dashboard_admin'
        )

    error = None

    if request.method == 'POST':

        username = request.POST.get(
            'username',
            ''
        ).strip()

        password = request.POST.get(
            'password',
            ''
        ).strip()

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

                auth_login(request, user)

                # 1. ¿Es Alumno?
                if getattr(user, 'rol', None) == 'alumno' or hasattr(user, 'perfil_alumno'):
                    alumno_id = user.perfil_alumno.id_alumno if hasattr(user, 'perfil_alumno') else user.id
                    request.session['alumno_id'] = alumno_id
                    return redirect('alumno_pag1')

                # 2. ¿Es Profesor?
                elif getattr(user, 'rol', None) == 'profesor' or hasattr(user, 'perfil_profesor'):
                    prof_id = user.perfil_profesor.id_profesor if hasattr(user, 'perfil_profesor') else user.id
                    request.session['profesor_id'] = prof_id
                    return redirect('panel_profesor')

                # 3. ¿Es Administrador / Tutor?
                elif getattr(user, 'rol', None) == 'admin' or hasattr(user, 'perfil_tutor') or user.is_staff or user.is_superuser:
                    tutor = getattr(user, 'perfil_tutor', None) or Tutor.objects.filter(user=user).first()
                    
                    if tutor:
                        request.session['admin_id'] = tutor.id_tutor
                        return redirect('dashboard_admin')
                    
                    if getattr(user, 'rol', None) == 'admin' or user.is_staff or user.is_superuser:
                        request.session['admin_id'] = user.id
                        return redirect('dashboard_admin')

                    error = "Tu cuenta no tiene un perfil de administrador asociado."

                else:

                    error = (
                        "Tu cuenta no tiene "
                        "un perfil asignado "
                        "en el sistema."
                    )

            else:

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

@csrf_exempt
def enviar_reporte(request):

    if request.method == 'POST':

        try:

            data = json.loads(
                request.body
            )

            descripcion = data.get(
                'descripcion'
            )

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

        except Exception as e:

            return JsonResponse({
                "success": False,
                "message": str(e)
            })

    return JsonResponse({
        "success": False,
        "message": "Método no permitido."
    })


# ============================================================
# INSCRIPCIÓN DE CLASES
# ============================================================

@csrf_exempt
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

            clase = get_object_or_404(
                Clase,
                clase_id=id_clase
            )

            # Evitar inscripciones duplicadas

            if Inscripcion.objects.filter(
                alumno=alumno,
                clase=clase
            ).exists():

                return JsonResponse({
                    'success': False,
                    'message': (
                        f'Ya estás inscrito en '
                        f'la clase '
                        f'"{clase.asignatura.nombre}".'
                    )
                })

            Inscripcion.objects.create(
                alumno=alumno,
                clase=clase
            )

            return JsonResponse({
                'success': True,
                'message': (
                    f'¡Te has inscrito '
                    f'exitosamente a '
                    f'"{clase.asignatura.nombre}" '
                    f'con el profesor '
                    f'{clase.profesor.user.first_name}!'
                )
            })

        except Exception as e:

            return JsonResponse({
                'success': False,
                'message': str(e)
            })

    return JsonResponse({
        'success': False,
        'message': 'Método no permitido.'
    })


def cancelar_inscripcion(request, pk):

    alumno_id = request.session.get(
        'alumno_id'
    )

    if not alumno_id:
        return redirect('login')

    inscripcion = get_object_or_404(
        Inscripcion,
        id_inscripcion=pk,
        alumno_id=alumno_id
    )

    inscripcion.delete()

    return redirect(
        'alumno_pag1'
    )


# ============================================================
# PAGO CON WEBPAY PLUS - TRANSBANK
# ============================================================

def pago(request):

    return render(
        request,
        'alumnos/pago.html',
        {}
    )


def iniciar_webpay(request):

    if request.method != 'POST':
        return redirect('planes')

    try:

        amount = int(
            request.POST.get(
                'amount',
                '0'
            )
        )

    except ValueError:

        amount = 0

    carrito_json = request.POST.get(
        'carrito',
        '[]'
    )

    # Webpay requiere un monto válido

    if amount < 350:
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

    return_url = (
        request.build_absolute_uri(
            reverse('confirmacion')
        )
    )

    response = _tx().create(
        buy_order,
        session_id,
        amount,
        return_url
    )

    request.session[
        'orden_pendiente'
    ] = {
        'buy_order': buy_order,
        'carrito': carrito_json,
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

    # Pago recibido desde Webpay

    if token:

        resp = _tx().commit(
            token
        )

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
    # Validar que el usuario esta autenticado
    # Esta vista es mixta: puede entrar un profesor o un alumno
    
    # Obtener la clase
    clase = get_object_or_404(Clase, id_clase=clase_id)
    
    # En un sistema real, aca validamos que si es alumno, este inscrito en esta clase
    # Y si es profesor, que sea el profesor de esta clase
    
    context = {
        'clase': clase
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
