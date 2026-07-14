import json
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from .models import Alumno, Genero, Tutor
from .forms import AlumnoForm

# ===== Transbank (Webpay Plus - ambiente de integración) =====
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_type import IntegrationType

PERIODOS = {'mensual': 1, '3semanas': 0.75, '2semanas': 0.50, '1semana': 0.25}


def _tx():
    return Transaction(WebpayOptions(
        IntegrationCommerceCodes.WEBPAY_PLUS,
        IntegrationApiKeys.WEBPAY,
        IntegrationType.TEST,
    ))


def _clp(n):
    return '$' + f'{int(n):,}'.replace(',', '.')


def _precio_item(item):
    base = int(''.join(c for c in str(item.get('precio', '0')) if c.isdigit()) or 0)
    factor = PERIODOS.get(item.get('periodo', 'mensual'), 1)
    return round(base * factor) * int(item.get('cantidad', 1))


# Create your views here.

def home(request):
    context = {}
    return render(request, 'alumnos/home.html', context)

def planes(request):
    context = {}
    return render(request, 'alumnos/planes.html', context)

def servicios(request):
    context = {}
    return render(request, 'alumnos/servicios.html', context)

def nosotros(request):
    context = {}
    return render(request, 'alumnos/nosotros.html', context)

def contactos(request):
    context = {}
    return render(request, 'alumnos/contactos.html', context)

def simulador(request):
    context = {}
    return render(request, 'alumnos/simulador.html', context)

def opcion_user(request):
    context = {}
    return render(request, 'alumnos/opcion_user.html', context)

def regis_alum(request):
    if request.method == 'POST':
        form = AlumnoForm(request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({"success": True, "message": "Alumno registrado exitosamente."})
        else:
            errors = form.errors.as_json()
            return JsonResponse({"success": False, "message": "Error en los datos.", "errors": errors})

    form = AlumnoForm()
    context = {'form': form}
    return render(request, 'alumnos/regis_alum.html', context)

def alumnos_reg(request):
    if request.method == 'POST':
        try:
            nombre = request.POST['nombre']
            rut = request.POST['rut']
            nivel_educacion = request.POST['nivel_educacion']
            direccion = request.POST['direccion']
            fecha_nacimiento = request.POST['fecha_nacimiento']
            correo_electronico = request.POST['correo_electronico']
            telefono = request.POST['telefono']
            genero_id = request.POST['genero']

            genero = Genero.objects.get(id_genero=genero_id)

            Alumno.objects.create(
                nombre=nombre,
                rut=rut,
                nivel_educacion=nivel_educacion,
                direccion=direccion,
                fecha_nacimiento=fecha_nacimiento,
                correo_electronico=correo_electronico,
                telefono=telefono,
                genero=genero
            )
            return JsonResponse({"success": True, "message": "Alumno registrado exitosamente."})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})

    generos = Genero.objects.all()
    return render(request, 'alumnos/regis_alum.html', {'generos': generos})

def alumno_pag1(request):
    context = {}
    return render(request, 'alumnos/Alumno_pag1.html', context)


# --- Vistas CRUD reubicadas desde admin_portal ---
def crud(request):
    alumnos = Alumno.objects.all()
    context = {'alumnos': alumnos}
    return render(request, 'admin_portal/alumnos_list.html', context)

def alumnos_Add(request):
    if request.method == 'POST':
        try:
            nombre = request.POST['nombre']
            rut = request.POST['rut']
            nivel_educacion = request.POST['nivel_educacion']
            direccion = request.POST['direccion']
            fecha_nacimiento = request.POST['fecha_nacimiento']
            correo_electronico = request.POST['correo_electronico']
            telefono = request.POST['telefono']
            genero_id = request.POST['genero']

            genero = Genero.objects.get(id_genero=genero_id)

            Alumno.objects.create(
                nombre=nombre,
                rut=rut,
                nivel_educacion=nivel_educacion,
                direccion=direccion,
                fecha_nacimiento=fecha_nacimiento,
                correo_electronico=correo_electronico,
                telefono=telefono,
                genero=genero
            )
            return JsonResponse({"success": True, "message": "Alumno registrado exitosamente."})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})

    generos = Genero.objects.all()
    return render(request, 'admin_portal/alumnos_add.html', {'generos': generos})

def alumnos_findEdit(request, pk):
    try:
        alumno = Alumno.objects.get(id_alumno=pk)  # Usamos id_alumno en lugar de rut
        generos = Genero.objects.all()
        context = {'alumno': alumno, 'generos': generos}
        return render(request, 'admin_portal/alumnos_edit.html', context)
    except Alumno.DoesNotExist:
        context = {'mensaje': "Error, ID no existe..."}
        return render(request, 'admin_portal/alumnos_list.html', context)


def alumnos_del(request, pk):
    try:
        alumno = Alumno.objects.get(id_alumno=pk)  # Usamos id_alumno en lugar de rut
        alumno.delete()
        mensaje = "Bien, datos eliminados..."
    except Alumno.DoesNotExist:
        mensaje = "Error, ID no existe..."
    alumnos = Alumno.objects.all()
    context = {'alumnos': alumnos, 'mensaje': mensaje}
    return render(request, 'admin_portal/alumnos_list.html', context)


def alumnos_Update(request):
    if request.method == 'POST':
        id_alumno = request.POST.get('id_alumno')
        alumno = get_object_or_404(Alumno, id_alumno=id_alumno)

        alumno.nombre = request.POST.get('nombre')
        alumno.rut = request.POST.get('rut')
        alumno.nivel_educacion = request.POST.get('nivel_educacion')
        alumno.direccion = request.POST.get('direccion')
        alumno.fecha_nacimiento = request.POST.get('fecha_nacimiento')
        alumno.correo_electronico = request.POST.get('correo_electronico')
        alumno.telefono = request.POST.get('telefono')
        genero_id = request.POST.get('genero')
        alumno.genero = Genero.objects.get(id_genero=genero_id)

        alumno.save()
        return HttpResponse("OK, datos actualizados.")  # Confirmación simple en lugar de redirección
    else:
        return HttpResponse("Solicitud inválida.", status=400)


# ============================================================
#  PAGO CON WEBPAY PLUS (Transbank)
# ============================================================

def pago(request):
    return render(request, 'alumnos/pago.html', {})


def iniciar_webpay(request):
    if request.method != 'POST':
        return redirect('planes')

    try:
        amount = int(request.POST.get('amount', '0'))
    except ValueError:
        amount = 0

    carrito_json = request.POST.get('carrito', '[]')
    if amount < 350:
        return redirect('planes')

    buy_order = 'LB' + str(random.randrange(1000000, 9999999))
    session_id = 'S' + str(random.randrange(1000000, 9999999))
    return_url = request.build_absolute_uri(reverse('confirmacion'))

    response = _tx().create(buy_order, session_id, amount, return_url)

    request.session['orden_pendiente'] = {
        'buy_order': buy_order,
        'carrito': carrito_json,
    }

    return render(request, 'alumnos/redirect_webpay.html', {
        'url': response['url'],
        'token': response['token'],
    })


@csrf_exempt
def confirmacion(request):
    token = request.GET.get('token_ws') or request.POST.get('token_ws')
    tbk_token = request.GET.get('TBK_TOKEN') or request.POST.get('TBK_TOKEN')

    orden = request.session.pop('orden_pendiente', {})
    try:
        carrito = json.loads(orden.get('carrito', '[]'))
    except (ValueError, TypeError):
        carrito = []

    items = [{
        'titulo': it.get('titulo', ''),
        'cantidad': it.get('cantidad', 1),
        'precio': _clp(_precio_item(it)),
    } for it in carrito]

    ctx = {'items': items}

    if token:
        resp = _tx().commit(token)
        aprobado = resp.get('response_code') == 0 and resp.get('status') == 'AUTHORIZED'
        card = resp.get('card_detail') or {}
        ctx.update({
            'aprobado': aprobado,
            'orden': resp.get('buy_order', orden.get('buy_order', '')),
            'monto': _clp(resp.get('amount', 0)),
            'codigo_autorizacion': resp.get('authorization_code', ''),
            'tarjeta': card.get('card_number', ''),
            'fecha': resp.get('transaction_date', ''),
        })
    elif tbk_token:
        ctx.update({'aprobado': False, 'anulado': True})
    else:
        return redirect('planes')

    return render(request, 'alumnos/confirmacion.html', ctx)
