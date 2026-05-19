from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from alumnos.models import Alumno, Genero
from django.contrib.auth.decorators import login_required

@login_required
def menu(request):
    request.session["usuario"] = "fcisterna"
    usuario = request.session["usuario"]
    context = {'usuario': usuario}
    return render(request, 'admin_portal/menu.html', context)
    
@login_required
def home_adm(request):
    context = {}
    return render(request, 'admin_portal/home_adm.html', context)

def reporte_alumnos(request):
    alumnos = Alumno.objects.all()  
    return render(request, 'alumnos/reporte_alumnos.html', {'alumnos': alumnos})

def planes_adm(request):
    context = {}
    return render(request, 'admin_portal/planes_adm.html', context)

def nosotros_adm(request):
    context = {}
    return render(request, 'admin_portal/nosotros_adm.html', context)

def contactos_adm(request):
    context = {}
    return render(request, 'admin_portal/contactos_adm.html', context)

# --- Vistas CRUD movidas desde alumnos ---
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
