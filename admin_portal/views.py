from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from alumnos.models import Alumno, Genero, Profesor, Tutor, Clase, Reporte

# esta parte es del menú clásico del admin (se mantiene por si se usa en otros lados)
def menu(request):
    return render(request, 'admin_portal/menu.html', {})


# esta parte es del dashboard principal del administrador con todos los datos
def dashboard_admin(request):
    # redirigir al login si no hay sesión de admin
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login')

    admin = get_object_or_404(Tutor, id_tutor=admin_id)

    # esta parte es de recoger todos los datos para las estadísticas
    alumnos = Alumno.objects.all()
    profesores = Profesor.objects.all()
    admins = Tutor.objects.all()
    clases = Clase.objects.all()
    todos_reportes = Reporte.objects.all().order_by('-fecha_reporte')
    reportes_recientes = todos_reportes[:5]
    reportes_pendientes = todos_reportes.filter(estado='pendiente').count()

    # esta parte es de los últimos registros para mostrar en el resumen
    ultimos_alumnos = alumnos.order_by('-id_alumno')[:3]
    ultimos_profesores = profesores.order_by('-id_profesor')[:3]

    context = {
        'admin': admin,
        'alumnos': alumnos,
        'profesores': profesores,
        'admins': admins,
        'total_alumnos': alumnos.count(),
        'total_profesores': profesores.count(),
        'total_admins': admins.count(),
        'total_clases': clases.count(),
        'todos_reportes': todos_reportes,
        'reportes_recientes': reportes_recientes,
        'reportes_pendientes': reportes_pendientes,
        'ultimos_alumnos': ultimos_alumnos,
        'ultimos_profesores': ultimos_profesores,
    }
    return render(request, 'admin_portal/dashboard_admin.html', context)


# esta parte es para marcar un reporte como resuelto
def resolver_reporte(request, pk):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login')

    reporte = get_object_or_404(Reporte, id_reporte=pk)
    reporte.estado = 'resuelto'
    reporte.save()
    return redirect('dashboard_admin')
    

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
