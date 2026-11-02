from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from alumnos import paquetes
from alumnos.models import Alumno, Asignatura, Profesor, Tutor, Clase
from alumnos.decorators import admin_required

from . import ingresos, metricas

# Solo redirige al panel: regis_tutor.html envía aquí tras registrarse.
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

    # Consulta a la base de datos de los contadores del sistema. Los reportes de
    # usuarios los atiende soporte (paso 6e): el admin no ve su contenido.
    alumnos = Alumno.objects.all()
    profesores = Profesor.objects.all()
    admins = Tutor.objects.all()
    clases = Clase.objects.all()

    # Trae los 3 registros más recientes de alumnos y profesores para la vista previa
    ultimos_alumnos = alumnos.order_by('-id_alumno')[:3]
    ultimos_profesores = profesores.order_by('-id_profesor')[:3]

    from alumnos.models import SolicitudRetiro

    todas_solicitudes_retiro = SolicitudRetiro.objects.select_related(
        'banco', 'profesor__user', 'profesor__cuenta_bancaria').order_by('-fecha_solicitud')

    context = {
        'admin': admin,
        'alumnos': alumnos,
        'profesores': profesores,
        'admins': admins,
        'total_alumnos': alumnos.count(),
        'total_profesores': profesores.count(),
        'total_admins': admins.count(),
        'total_clases': clases.count(),
        'ultimos_alumnos': ultimos_alumnos,
        'ultimos_profesores': ultimos_profesores,
        'todas_solicitudes_retiro': todas_solicitudes_retiro,
        'finanzas': metricas.finanzas(),  # montos reales (paso 8); el template les da formato
        'grafico_registros': metricas.grafico(metricas.registros_por_mes()),
        'ingresos_hoy': ingresos.de_hoy(),  # personas distintas que iniciaron sesion hoy (H8)
        'soporte': metricas.soporte(),  # cifras agregadas, sin contenido (P13)
    }
    return render(request, 'admin_portal/dashboard_admin.html', context)


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
    return render(request, 'admin_portal/planes_adm.html', {
        'planes': metricas.planes(),
        'tarifa': {'base': paquetes.TARIFA_BASE, 'min': paquetes.TARIFA_MIN,
                   'max': paquetes.TARIFA_MAX, 'paso': paquetes.TARIFA_PASO},
    })

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

# --- Vistas CRUD ---
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
@require_POST
def alumnos_del(request, pk):
    
    alumno = get_object_or_404(Alumno, id_alumno=pk)
    
    # Se borra también la cuenta (CustomUser); el perfil de alumno cae en cascada.
    if alumno.user:
        alumno.user.delete() 
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


def _avanzar_retiro(request, pk, accion, exito):
    """Aplica un paso al retiro con la fila bloqueada: un doble clic o dos admins no lo repiten."""
    from alumnos.models import SolicitudRetiro
    with transaction.atomic():
        retiro = get_object_or_404(SolicitudRetiro.objects.select_for_update(), id_solicitud=pk)
        try:
            accion(retiro)
        except ValidationError as e:
            messages.error(request, e.messages[0])
        else:
            messages.success(request, f'Retiro #{pk} {exito}.')
    return redirect('dashboard_admin')


@admin_required
@require_POST
def aprobar_retiro(request, pk):
    return _avanzar_retiro(request, pk, lambda r: r.aprobar(request.user),
                           'aprobado. Transfiere y luego registra el número de operación')


@admin_required
@require_POST
def rechazar_retiro(request, pk):
    return _avanzar_retiro(request, pk, lambda r: r.rechazar(request.user, request.POST.get('motivo', '')),
                           'rechazado')


@admin_required
@require_POST
def marcar_pagado_retiro(request, pk):
    return _avanzar_retiro(request, pk,
                           lambda r: r.marcar_pagado(request.user, request.POST.get('numero_operacion', '')),
                           'registrado como pagado')



