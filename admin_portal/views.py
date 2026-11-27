from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from alumnos import paquetes
from alumnos.models import Alumno, Profesor, Tutor, Clase
from alumnos.decorators import admin_required
from lbwus import salud
from supresiones import registro

from . import ingresos, metricas
from .forms import AjustesAdminForm


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
    return render(request, 'admin_portal/dashboard_admin.html', _contexto_dashboard(request, _admin_en_sesion(request)))


@never_cache
@admin_required
@require_POST
def ajustes_admin(request):
    """Guarda los datos del propio admin (seccion Ajustes). Con errores vuelve a mostrar el dashboard en Ajustes, con
    lo escrito y cada error junto a su campo; el menu sigue con lo guardado hasta que se guarde."""
    admin = _admin_en_sesion(request)
    form = AjustesAdminForm(request.POST, user=admin.user)
    if form.is_valid():
        form.save()
        messages.success(request, 'Guardamos tus datos.')
        return redirect(reverse('dashboard_admin') + '#ajustes')
    messages.error(request, 'Revisa los campos marcados en Ajustes.')
    return render(request, 'admin_portal/dashboard_admin.html',
                  _contexto_dashboard(request, admin, form_ajustes=form, seccion_inicial='ajustes'))


def _admin_en_sesion(request):
    return get_object_or_404(Tutor.objects.select_related('user'), id_tutor=request.session.get('admin_id'))


def _contexto_dashboard(request, admin, form_ajustes=None, seccion_inicial='resumen'):
    """Todo lo que muestra el dashboard. seccion_inicial: la que se abre si la direccion no trae #seccion."""
    # Consulta a la base de datos de los contadores del sistema. Los reportes de
    # usuarios los atiende soporte (paso 6e): el admin no ve su contenido.
    # select_related: la plantilla muestra nombre, correo y especialidad de cada fila (sin N+1).
    # Sin order_by, PostgreSQL devuelve las filas en cualquier orden: "ultimos" no lo eran y las tablas saltaban.
    alumnos = Alumno.objects.select_related('user').order_by('pk')
    profesores = Profesor.objects.select_related('user', 'especialidad').order_by('pk')
    admins = Tutor.objects.select_related('user').order_by('pk')
    clases = Clase.objects.select_related('asignatura', 'profesor__user').order_by('pk')

    ultimos_alumnos = alumnos.order_by('-pk')[:3]
    ultimos_profesores = profesores.order_by('-pk')[:3]

    from alumnos.models import SolicitudRetiro

    todas_solicitudes_retiro = SolicitudRetiro.objects.select_related(
        'banco', 'profesor__user', 'profesor__cuenta_bancaria').order_by('-fecha_solicitud')

    # Corte del grafico de registros (H9); cualquier otro valor vuelve a meses.
    periodo = request.GET.get('periodo')
    if periodo not in metricas.PERIODOS:
        periodo = 'mes'

    cifras_soporte = metricas.soporte()  # cifras agregadas, sin contenido (P13); las usan el banner y el panel
    pendientes = metricas.pendientes(cifras_soporte)  # lo que espera una decision del admin (banner del Resumen)

    context = {
        'admin': admin,
        'alumnos': alumnos,
        'profesores': profesores,
        'admins': admins,
        'clases': clases,  # tabla "Clases" del panel (se habia perdido del contexto)
        'total_alumnos': alumnos.count(),
        'total_profesores': profesores.count(),
        'total_admins': admins.count(),
        'total_clases': clases.count(),
        'ultimos_alumnos': ultimos_alumnos,
        'ultimos_profesores': ultimos_profesores,
        'todas_solicitudes_retiro': todas_solicitudes_retiro,
        'finanzas': metricas.finanzas(),  # montos reales (paso 8); el template les da formato
        **paquetes.porcentajes(),  # las tasas de las leyendas de Finanzas: salen de paquetes.py, no de la plantilla
        'grafico_registros': metricas.grafico(metricas.registros(periodo)),
        'grafico_personas': metricas.grafico(metricas.personas(periodo)),  # mismo periodo (H8 + H9)
        'periodo': periodo,
        'periodo_nombre': metricas.PERIODOS[periodo],
        'periodos': metricas.PERIODOS,
        'ingresos_hoy': ingresos.de_hoy(),  # personas distintas que iniciaron sesion hoy (H8)
        'soporte': cifras_soporte,
        'pendientes': pendientes,
        'total_pendientes': sum(p['n'] for p in pendientes),
        'form_ajustes': form_ajustes or AjustesAdminForm(user=admin.user),
        'seccion_inicial': seccion_inicial,
        'tareas_atrasadas': salud.tareas_atrasadas(),  # el Cron no completo tareas_diarias en 26 h (SCRUM-100)
    }
    return context


def home_adm(request):
    context = {}
    return render(request, 'admin_portal/home_adm.html', context)


@never_cache
@admin_required
def planes_adm(request):
    return render(request, 'admin_portal/planes_adm.html', {
        'planes': metricas.planes(),
        'tarifa': paquetes.TARIFA,
    })


@never_cache
@admin_required
def nosotros_adm(request):
    context = {}
    return render(request, 'admin_portal/nosotros_adm.html', context)

# --- Usuarios: el admin solo ve el listado y elimina; no crea ni edita alumnos (decidido 21-nov) ---
def _a_usuarios():
    """El unico listado de usuarios es la seccion Usuarios del dashboard."""
    return redirect(reverse('dashboard_admin') + '#usuarios')


@never_cache
@admin_required
def crud(request):
    """Ruta antigua del listado de alumnos (tambien reporte_alumnos): se mantiene para no romper enlaces guardados."""
    return _a_usuarios()


@admin_required
@require_POST
def alumnos_del(request, pk):
    alumno = get_object_or_404(Alumno, id_alumno=pk)

    # Se borra tambien la cuenta (CustomUser); el perfil de alumno cae en cascada. Si la cuenta tiene
    # conversaciones reportadas o historial de pagos y clases no se borra: se seudonimiza (mensajes/supresion.py).
    # Pasa por el registro de supresiones, igual que la solicitud del usuario.
    borrada = registro.eliminar(alumno.user)
    if borrada and Alumno.objects.filter(id_alumno=pk).exists():
        alumno.delete()

    if borrada:
        messages.success(request, 'Bien, datos eliminados...')
    else:
        messages.info(request, 'La cuenta se seudonimizó: se conservan, sin sus datos personales, sus pagos y clases y '
                               'sus conversaciones reportadas (estas, solo para soporte).')
    return _a_usuarios()


@never_cache
@require_POST
def logout_admin(request):
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    request.session.flush()
    return redirect('home')


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



