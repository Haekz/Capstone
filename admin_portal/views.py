from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from alumnos.models import Alumno, Genero, Profesor, Tutor, Clase, Reporte
from alumnos.decorators import admin_required

# Ruta antigua del menú: ya no tiene template, solo redirige al panel.
# Se mantiene porque regis_tutor.html envía aquí tras registrarse.
def menu(request):
    admin_id = request.session.get('admin_id')
    if admin_id:
        return redirect('dashboard_admin')
    return redirect('login')



# Controlador principal del Dashboard de administración
@never_cache
@admin_required
def dashboard_admin(request):
    admin_id = request.session.get('admin_id')

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

    from alumnos.models import SolicitudRetiro, Inscripcion
    from django.db.models import Sum

    todas_solicitudes_retiro = SolicitudRetiro.objects.all().order_by('-fecha_solicitud')
    total_inscripciones_global = Inscripcion.objects.count()
    ingresos_totales = max(total_inscripciones_global * 15000, 180000)
    retiros_pagados = SolicitudRetiro.objects.filter(estado='aprobado').aggregate(Sum('monto'))['monto__sum'] or 0
    retiros_pendientes = SolicitudRetiro.objects.filter(estado='pendiente').aggregate(Sum('monto'))['monto__sum'] or 0

    ingresos_totales_fmt = f"${ingresos_totales:,}".replace(",", ".")
    retiros_pagados_fmt = f"${retiros_pagados:,}".replace(",", ".")
    retiros_pendientes_fmt = f"${retiros_pendientes:,}".replace(",", ".")

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
        'todas_solicitudes_retiro': todas_solicitudes_retiro,
        'ingresos_totales': ingresos_totales_fmt,
        'retiros_pagados': retiros_pagados_fmt,
        'retiros_pendientes': retiros_pendientes_fmt,
    }
    return render(request, 'admin_portal/dashboard_admin.html', context)


# Controlador para cambiar el estado de un reporte a 'resuelto'
@admin_required
def resolver_reporte(request, pk):

    reporte = get_object_or_404(Reporte, id_reporte=pk)
    reporte.estado = 'resuelto'
    reporte.save()
    return redirect('dashboard_admin')
    

def home_adm(request):
    context = {}
    return render(request, 'admin_portal/home_adm.html', context)

def reporte_alumnos(request):
    """Ruta antigua del listado de alumnos.

    Apuntaba a 'alumnos/reporte_alumnos.html', un template que no existe:
    la vista reventaba con TemplateDoesNotExist (HTTP 500) y ademas no
    exigia sesion de administrador. El listado vive en crud(), que usa
    'admin_portal/alumnos_list.html' y si valida el acceso; se redirige
    ahi para no mantener dos vistas que hacen lo mismo.
    """
    return redirect('crud')

@never_cache
@admin_required
def planes_adm(request):
    context = {}
    return render(request, 'admin_portal/planes_adm.html', context)

@never_cache
@admin_required
def nosotros_adm(request):
    context = {}
    return render(request, 'admin_portal/nosotros_adm.html', context)

@never_cache
@admin_required
def contactos_adm(request):
    context = {}
    return render(request, 'admin_portal/contactos_adm.html', context)

# --- Vistas CRUD movidas desde alumnos ---
@never_cache
@admin_required
def crud(request):
    alumnos = Alumno.objects.all()
    context = {'alumnos': alumnos}
    return render(request, 'admin_portal/alumnos_list.html', context)

@never_cache
@admin_required
def alumnos_Add(request):
    from .forms import AdminAlumnoForm
    if request.method == 'POST':
        form = AdminAlumnoForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                return JsonResponse({"success": True, "message": "Alumno registrado exitosamente."})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Error al guardar: {str(e)}"})
        else:
            # Obtener el primer error del formulario
            errores = dict(form.errors.items())
            mensaje_error = "\n".join([f"{k}: {v[0]}" for k, v in errores.items()])
            return JsonResponse({"success": False, "message": mensaje_error})
    else:
        form = AdminAlumnoForm()

    return render(request, 'admin_portal/alumnos_add.html', {'form': form})

@never_cache
@admin_required
def alumnos_findEdit(request, pk):
    alumno = get_object_or_404(Alumno, id_alumno=pk)
    from .forms import AdminAlumnoForm
    form = AdminAlumnoForm(instance=alumno)
    context = {'alumno': alumno, 'form': form}
    return render(request, 'admin_portal/alumnos_edit.html', context)


@admin_required
def alumnos_del(request, pk):
    
    alumno = get_object_or_404(Alumno, id_alumno=pk)
    
    # IMPORTANTE: al borrar el Alumno, quizás también queramos borrar el CustomUser asociado
    # Si queremos que se mantenga el usuario pero pierda el rol de alumno, no lo borramos.
    # En este caso, borramos ambos para mantener la base de datos limpia.
    if alumno.user:
        alumno.user.delete() 
    # El perfil de alumno se borrará en cascada por el OneToOneField de CustomUser, 
    # o si no, lo borramos manualmente (dependiendo de on_delete).
    if Alumno.objects.filter(id_alumno=pk).exists():
        alumno.delete()

    alumnos = Alumno.objects.all()
    context = {'alumnos': alumnos, 'mensaje': "Bien, datos eliminados..."}
    return render(request, 'admin_portal/alumnos_list.html', context)


@admin_required
def alumnos_Update(request):
        
    if request.method == 'POST':
        id_alumno = request.POST.get('id_alumno')
        alumno = get_object_or_404(Alumno, id_alumno=id_alumno)
        
        from .forms import AdminAlumnoForm
        form = AdminAlumnoForm(request.POST, instance=alumno)
        
        if form.is_valid():
            try:
                form.save()
                return HttpResponse("OK, datos actualizados.")
            except Exception as e:
                return HttpResponse(f"Error al actualizar: {str(e)}", status=400)
        else:
            errores = dict(form.errors.items())
            mensaje_error = "\n".join([f"{k}: {v[0]}" for k, v in errores.items()])
            return HttpResponse(f"Error de validación: {mensaje_error}", status=400)
    else:
        return HttpResponse("Solicitud inválida.", status=400)


def logout_admin(request):
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    if 'admin_id' in request.session:
        del request.session['admin_id']
    return redirect('home')


@admin_required
def crear_clase(request):
    if request.method == 'POST':
        nombre_curso = request.POST.get('nombre_curso', '').strip()
        modalidad = request.POST.get('modalidad', 'online')
        horario = request.POST.get('horario', '').strip()
        id_profesor = request.POST.get('id_profesor')

        if not (nombre_curso and horario and id_profesor):
            return JsonResponse({'success': False, 'message': 'Todos los campos son requeridos.'})

        profesor = get_object_or_404(Profesor, id_profesor=id_profesor)
        clase = Clase.objects.create(
            asignatura=Asignatura.objects.get_or_create(nombre=nombre_curso)[0],
            modalidad=modalidad,
            horario=horario,
            profesor=profesor
        )
        return JsonResponse({'success': True, 'message': f'Clase "{clase.asignatura.nombre}" creada exitosamente.'})
    return JsonResponse({'success': False, 'message': 'Método no permitido.'})


@admin_required
def eliminar_clase(request, pk):
    clase = get_object_or_404(Clase, id_clase=pk)
    clase.delete()
    return redirect('dashboard_admin')


@admin_required
def aprobar_retiro(request, pk):
    from alumnos.models import SolicitudRetiro
    from django.utils import timezone
    retiro = get_object_or_404(SolicitudRetiro, id_solicitud=pk)
    retiro.estado = 'aprobado'
    retiro.fecha_resolucion = timezone.now()
    retiro.save()
    return redirect('dashboard_admin')


@admin_required
def rechazar_retiro(request, pk):
    from alumnos.models import SolicitudRetiro
    from django.utils import timezone
    retiro = get_object_or_404(SolicitudRetiro, id_solicitud=pk)
    retiro.estado = 'rechazado'
    retiro.fecha_resolucion = timezone.now()
    retiro.save()
    return redirect('dashboard_admin')



