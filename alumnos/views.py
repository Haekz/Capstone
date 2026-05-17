from django.shortcuts import render, redirect
from django.http import JsonResponse
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
            errors = form.errors.as_json()
            return JsonResponse({"success": False, "message": "Error en los datos.", "errors": errors})
    
    form = AlumnoForm()
    context = {'form': form}
    return render(request, 'alumnos/regis_alum.html', context)

def regis_prof(request):
    context = {}
    return render(request, 'alumnos/regis_prof.html', context)

def regis_tutor(request):
    context = {}
    return render(request, 'alumnos/regis_tutor.html', context)


def crud(request):
    alumnos = Alumno.objects.all()
    context = {'alumnos': alumnos}
    return render(request, 'alumnos/alumnos_list.html', context)

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
    return render(request, 'alumnos/alumnos_add.html', {'generos': generos})

def alumnos_findEdit(request, pk):
    try:
        alumno = Alumno.objects.get(id_alumno=pk)  # Usamos id_alumno en lugar de rut
        generos = Genero.objects.all()
        context = {'alumno': alumno, 'generos': generos}
        return render(request, 'alumnos/alumnos_edit.html', context)
    except Alumno.DoesNotExist:
        context = {'mensaje': "Error, ID no existe..."}
        return render(request, 'alumnos/alumnos_list.html', context)


def alumnos_del(request, pk):
    try:
        alumno = Alumno.objects.get(id_alumno=pk)  # Usamos id_alumno en lugar de rut
        alumno.delete()
        mensaje = "Bien, datos eliminados..."
    except Alumno.DoesNotExist:
        mensaje = "Error, ID no existe..."
    alumnos = Alumno.objects.all()
    context = {'alumnos': alumnos, 'mensaje': mensaje}
    return render(request, 'alumnos/alumnos_list.html', context)


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




