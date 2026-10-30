import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.db.models import Sum, Q
from alumnos.models import (
    Alumno, Asignatura, Genero, Profesor, Tutor, Clase,
    Reporte, SolicitudRetiro, Inscripcion, DesgloseOperacion,
)
from alumnos.decorators import admin_required
from alumnos.utils import formato_clp

logger = logging.getLogger(__name__)


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
    admin = get_object_or_404(Tutor.objects.select_related('user'), id_tutor=admin_id)

    # Carga optimizada con select_related en listas en memoria para evitar N+1 y COUNTs redundantes
    alumnos = list(
        Alumno.objects.select_related('user', 'user__genero', 'tutor', 'tutor__user').order_by('-id_alumno')
    )
    profesores = list(
        Profesor.objects.select_related('user', 'user__genero', 'especialidad').order_by('-id_profesor')
    )
    admins = list(Tutor.objects.select_related('user', 'user__genero').all())
    clases = list(Clase.objects.select_related('asignatura', 'profesor', 'profesor__user').all())
    todos_reportes = list(Reporte.objects.select_related('remitente').order_by('-fecha_reporte'))

    reportes_recientes = todos_reportes[:5]
    reportes_pendientes = sum(1 for r in todos_reportes if r.estado == 'pendiente')

    ultimos_alumnos = alumnos[:3]
    ultimos_profesores = profesores[:3]

    todas_solicitudes_retiro = list(
        SolicitudRetiro.objects.select_related('profesor', 'profesor__user', 'banco').order_by('-fecha_solicitud')
    )
    total_inscripciones_global = Inscripcion.objects.count()
    ingresos_totales = max(total_inscripciones_global * 15000, 180000)

    retiros_pagados = sum(r.monto for r in todas_solicitudes_retiro if r.estado == 'aprobado')
    retiros_pendientes = sum(r.monto for r in todas_solicitudes_retiro if r.estado == 'pendiente')

    # S4-09: Auditoría consolidada de comisiones de plataforma e importes en custodia en 1 sola consulta
    agregados_desglose = DesgloseOperacion.objects.aggregate(
        comisiones=Sum('comision_lbwus', filter=~Q(estado='reembolsado')),
        custodia=Sum('monto_tutor', filter=Q(estado='pendiente')),
    )
    comisiones_lbwus_totales = agregados_desglose['comisiones'] or 0
    fondos_en_custodia = agregados_desglose['custodia'] or 0

    context = {
        'admin': admin,
        'alumnos': alumnos,
        'profesores': profesores,
        'admins': admins,
        'clases': clases,
        'total_alumnos': len(alumnos),
        'total_profesores': len(profesores),
        'total_admins': len(admins),
        'total_clases': len(clases),
        'todos_reportes': todos_reportes,
        'reportes_recientes': reportes_recientes,
        'reportes_pendientes': reportes_pendientes,
        'ultimos_alumnos': ultimos_alumnos,
        'ultimos_profesores': ultimos_profesores,
        'todas_solicitudes_retiro': todas_solicitudes_retiro,
        'ingresos_totales': formato_clp(ingresos_totales),
        'retiros_pagados': formato_clp(retiros_pagados),
        'retiros_pendientes': formato_clp(retiros_pendientes),
        'comisiones_lbwus_totales': formato_clp(comisiones_lbwus_totales),
        'fondos_en_custodia': formato_clp(fondos_en_custodia),
    }
    return render(request, 'admin_portal/dashboard_admin.html', context)


# Controlador para cambiar el estado de un reporte a 'resuelto'
@admin_required
@require_POST
def resolver_reporte(request, pk):
    reporte = get_object_or_404(Reporte, id_reporte=pk)
    reporte.estado = 'resuelto'
    reporte.save()
    return redirect('dashboard_admin')


def home_adm(request):
    context = {}
    return render(request, 'admin_portal/home_adm.html', context)


def reporte_alumnos(request):
    """Ruta antigua del listado de alumnos; redirige a crud()."""
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
    alumnos = Alumno.objects.select_related('user', 'user__genero').all()
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
            except Exception:
                logger.exception("Error interno al registrar alumno desde admin_portal")
                return JsonResponse(
                    {"success": False, "message": "Error interno al guardar los datos del alumno."},
                    status=500,
                )
        else:
            errores = dict(form.errors.items())
            mensaje_error = "\n".join([f"{k}: {v[0]}" for k, v in errores.items()])
            return JsonResponse({"success": False, "message": mensaje_error})
    else:
        form = AdminAlumnoForm()

    return render(request, 'admin_portal/alumnos_add.html', {'form': form})


@never_cache
@admin_required
def alumnos_findEdit(request, pk):
    alumno = get_object_or_404(Alumno.objects.select_related('user', 'user__genero'), id_alumno=pk)
    from .forms import AdminAlumnoForm
    form = AdminAlumnoForm(instance=alumno)
    context = {'alumno': alumno, 'form': form}
    return render(request, 'admin_portal/alumnos_edit.html', context)


@admin_required
@require_POST
def alumnos_del(request, pk):
    alumno = get_object_or_404(Alumno.objects.select_related('user'), id_alumno=pk)

    if alumno.user:
        alumno.user.delete()
    if Alumno.objects.filter(id_alumno=pk).exists():
        alumno.delete()

    alumnos = Alumno.objects.select_related('user', 'user__genero').all()
    context = {'alumnos': alumnos, 'mensaje': "Bien, datos eliminados..."}
    return render(request, 'admin_portal/alumnos_list.html', context)


@admin_required
def alumnos_Update(request):
    if request.method == 'POST':
        id_alumno = request.POST.get('id_alumno')
        alumno = get_object_or_404(Alumno.objects.select_related('user'), id_alumno=id_alumno)

        from .forms import AdminAlumnoForm
        form = AdminAlumnoForm(request.POST, instance=alumno)

        if form.is_valid():
            try:
                form.save()
                return HttpResponse("OK, datos actualizados.")
            except Exception:
                logger.exception("Error interno al actualizar alumno id=%s", id_alumno)
                return HttpResponse("Error interno al actualizar los datos del alumno.", status=400)
        else:
            errores = dict(form.errors.items())
            mensaje_error = "\n".join([f"{k}: {v[0]}" for k, v in errores.items()])
            return HttpResponse(f"Error de validación: {mensaje_error}", status=400)
    else:
        return HttpResponse("Solicitud inválida.", status=400)


@never_cache
@require_POST
def logout_admin(request):
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    request.session.flush()
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

        profesor = get_object_or_404(Profesor.objects.select_related('user'), id_profesor=id_profesor)
        if not profesor.puede_hacer_clases:
            return JsonResponse({'success': False, 'message': f'{profesor.nombre} aún no tiene su título profesional aprobado.'})
        clase = Clase.objects.create(
            asignatura=Asignatura.objects.get_or_create(nombre=nombre_curso)[0],
            modalidad=modalidad,
            horario=horario,
            profesor=profesor
        )
        return JsonResponse({'success': True, 'message': f'Clase "{clase.asignatura.nombre}" creada exitosamente.'})
    return JsonResponse({'success': False, 'message': 'Método no permitido.'})


@admin_required
@require_POST
def eliminar_clase(request, pk):
    clase = get_object_or_404(Clase, id_clase=pk)
    clase.delete()
    return redirect('dashboard_admin')


@admin_required
@require_POST
def aprobar_retiro(request, pk):
    from django.utils import timezone
    retiro = get_object_or_404(SolicitudRetiro, id_solicitud=pk)
    retiro.estado = 'aprobado'
    retiro.fecha_resolucion = timezone.now()
    retiro.save()
    return redirect('dashboard_admin')


@admin_required
@require_POST
def rechazar_retiro(request, pk):
    from django.utils import timezone
    retiro = get_object_or_404(SolicitudRetiro, id_solicitud=pk)
    retiro.estado = 'rechazado'
    retiro.fecha_resolucion = timezone.now()
    retiro.save()
    return redirect('dashboard_admin')
