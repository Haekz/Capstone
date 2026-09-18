from alumnos.models import Profesor
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.hashers import check_password
from .models import Alumno, Genero, Tutor
from .forms import AlumnoForm
from django.http import HttpResponse, JsonResponse

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
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    field_label = form.fields[field].label if field != '__all__' else "Error"
                    error_messages.append(f"{field_label}: {error}")
            message = " | ".join(error_messages)
            return JsonResponse({"success": False, "message": message})
    
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
    alumno_id = request.session.get('alumno_id')
    if not alumno_id:
        return redirect('login')
    alumno = get_object_or_404(Alumno, id_alumno=alumno_id)
    from alumnos.models import Reporte, Profesor, Clase, Inscripcion
    mis_reportes = Reporte.objects.filter(remitente_tipo='alumno', remitente_nombre=alumno.nombre).order_by('-fecha_reporte')
    profesores_list = Profesor.objects.all()
    clases_disponibles = Clase.objects.all().select_related('id_profesor')
    mis_inscripciones = Inscripcion.objects.filter(id_alumno=alumno).select_related('id_clase', 'id_clase__id_profesor').order_by('-fecha_inscripcion')
    inscritas_ids = list(mis_inscripciones.values_list('id_clase_id', flat=True))

    context = {
        'alumno': alumno,
        'mis_reportes': mis_reportes,
        'profesores_list': profesores_list,
        'clases_disponibles': clases_disponibles,
        'mis_inscripciones': mis_inscripciones,
        'inscritas_ids': inscritas_ids,
    }
    return render(request, 'alumnos/Alumno_pag1.html', context)


def custom_login(request):
    if request.session.get('alumno_id'):
        return redirect('alumno_pag1')
    if request.session.get('profesor_id'):
        return redirect('panel_profesor')
    if request.session.get('admin_id'):
        return redirect('dashboard_admin')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        # 1. Intentar autenticar contra Django User (Superusuario/Admin)
        django_user = authenticate(request, username=username, password=password)
        if django_user is not None:
            auth_login(request, django_user)
            tutor = Tutor.objects.filter(correo_electronico=django_user.email).first()
            if tutor:
                request.session['admin_id'] = tutor.id_tutor
            elif django_user.is_superuser:
                primer_tutor = Tutor.objects.first()
                if primer_tutor:
                    request.session['admin_id'] = primer_tutor.id_tutor
            return redirect('dashboard_admin')

        # 1.5 Intentar autenticar contra Tutor/Administrador registrado en la base de datos
        tutores = Tutor.objects.filter(correo_electronico__iexact=username)
        if not tutores.exists():
            tutores = Tutor.objects.filter(rut__iexact=username)

        for tutor in tutores:
            if tutor.password and check_password(password, tutor.password):
                request.session['admin_id'] = tutor.id_tutor
                return redirect('dashboard_admin')

        # 1.8 Intentar autenticar contra Profesor registrado en la base de datos
        profesores = Profesor.objects.filter(correo_electronico__iexact=username)
        if not profesores.exists():
            profesores = Profesor.objects.filter(rut__iexact=username)

        for profesor in profesores:
            if profesor.password and check_password(password, profesor.password):
                request.session['profesor_id'] = profesor.id_profesor
                return redirect('panel_profesor')

        # 2. Intentar autenticar contra Alumno (insensible a mayúsculas/minúsculas y tolerando duplicados)
        alumnos = Alumno.objects.filter(correo_electronico__iexact=username)
        if not alumnos.exists():
            alumnos = Alumno.objects.filter(rut__iexact=username)

        for alumno in alumnos:
            if alumno.password and check_password(password, alumno.password):
                request.session['alumno_id'] = alumno.id_alumno
                return redirect('alumno_pag1')

        error = "Usuario o contraseña incorrectos. Inténtalo de nuevo."

    return render(request, 'registration/login.html', {'error': error})


def logout_alumno(request):
    if 'alumno_id' in request.session:
        del request.session['alumno_id']
    return redirect('home')

import json
from .models import Reporte, Clase, Inscripcion
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def enviar_reporte(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            descripcion = data.get('descripcion')
            
            alumno_id = request.session.get('alumno_id')
            profesor_id = request.session.get('profesor_id')
            
            if not descripcion:
                return JsonResponse({"success": False, "message": "La descripción no puede estar vacía."})
                
            if alumno_id:
                alumno = Alumno.objects.get(id_alumno=alumno_id)
                Reporte.objects.create(
                    remitente_tipo='alumno',
                    remitente_nombre=alumno.nombre,
                    descripcion=descripcion
                )
                return JsonResponse({"success": True})
            elif profesor_id:
                profesor = Profesor.objects.get(id_profesor=profesor_id)
                Reporte.objects.create(
                    remitente_tipo='profesor',
                    remitente_nombre=profesor.nombre,
                    descripcion=descripcion
                )
                return JsonResponse({"success": True})
            else:
                return JsonResponse({"success": False, "message": "No hay sesión activa."})
                
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
            
    return JsonResponse({"success": False, "message": "Método no permitido."})


@csrf_exempt
def inscribir_clase(request):
    alumno_id = request.session.get('alumno_id')
    if not alumno_id:
        return JsonResponse({'success': False, 'message': 'Debes iniciar sesión como alumno para inscribirte.'})
    
    if request.method == 'POST':
        try:
            alumno = get_object_or_404(Alumno, id_alumno=alumno_id)
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                id_clase = data.get('id_clase')
            else:
                id_clase = request.POST.get('id_clase')
            
            if not id_clase:
                return JsonResponse({'success': False, 'message': 'ID de clase no proporcionado.'})
                
            clase = get_object_or_404(Clase, id_clase=id_clase)
            
            # Validar si ya está inscrito
            if Inscripcion.objects.filter(id_alumno=alumno, id_clase=clase).exists():
                return JsonResponse({'success': False, 'message': f'Ya estás inscrito en la clase "{clase.nombre_curso}".'})
                
            Inscripcion.objects.create(
                id_alumno=alumno,
                id_clase=clase
            )
            return JsonResponse({'success': True, 'message': f'¡Te has inscrito exitosamente a "{clase.nombre_curso}" con el profesor {clase.id_profesor.nombre}!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
            
    return JsonResponse({'success': False, 'message': 'Método no permitido.'})


def cancelar_inscripcion(request, pk):
    alumno_id = request.session.get('alumno_id')
    if not alumno_id:
        return redirect('login')
    inscripcion = get_object_or_404(Inscripcion, id_inscripcion=pk, id_alumno_id=alumno_id)
    inscripcion.delete()
    return redirect('alumno_pag1')


