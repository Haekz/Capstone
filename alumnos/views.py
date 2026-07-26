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
    context = {'alumno': alumno}
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


