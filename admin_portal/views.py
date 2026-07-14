from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from alumnos.models import Alumno, Genero, Profesor, Tutor, Clase, Reporte

# Vista del menú antiguo (ahora redirige automáticamente al nuevo panel de control)
def menu(request):
    admin_id = request.session.get('admin_id')
    if admin_id:
        return redirect('dashboard_admin')
    return redirect('login')



# Controlador principal del Dashboard de administración
def dashboard_admin(request):
    # redirigir al login si no hay sesión de admin
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('login')

    admin = get_object_or_404(Tutor, id_tutor=admin_id)

    # Consulta a la base de datos de los contadores y reportes del sistema
    alumnos = Alumno.objects.all()
    profesores = Profesor.objects.all()
    admins = Tutor.objects.all()
    clases = Clase.objects.all()
    todos_reportes = Reporte.objects.all().order_by('-fecha_reporte')
    reportes_recientes = todos_reportes[:5]
    reportes_pendientes = todos_reportes.filter(estado='pendiente').count()

    # Trae los 3 registros más recientes de alumnos y profesores para la vista previa
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


# Controlador para cambiar el estado de un reporte a 'resuelto'
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


