"""Vistas de reseñas verificadas.

Permisos: cada vista usa el decorador de rol existente, y cada consulta filtra
por el dueño, así que el recurso de otra persona responde 404.
"""

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from alumnos.decorators import admin_required, alumno_required, profesor_required
from alumnos.models import Inscripcion, Profesor, Tutor

from .consultas import RELACIONADAS, contexto_resenas
from .forms import ModeracionForm, ReporteForm, ResenaForm
from .models import MOTIVOS, ModeracionResena, ReporteResena, Resena


@never_cache
@alumno_required
def calificar(request, id_inscripcion):
    inscripcion = get_object_or_404(
        Inscripcion.objects.completadas().select_related('clase__asignatura', 'clase__profesor__user'),
        id_inscripcion=id_inscripcion, alumno_id=request.session['alumno_id'],
    )
    resena = Resena.objects.de_la_contratacion(inscripcion).first()
    editable = resena is None or resena.puede_actualizarse()
    form = ResenaForm(request.POST or None, instance=resena)

    if request.method == 'POST':
        if not editable:
            messages.error(request, 'Podrás actualizar tu reseña cuando completes una nueva clase de este paquete.')
            return redirect('resena_calificar', id_inscripcion)
        if form.is_valid():
            nueva = resena is None
            resena = form.save(commit=False)
            if nueva:
                resena.inscripcion = inscripcion
                resena.paquete_id = inscripcion.paquete_id
            resena.actualizada = timezone.now()
            try:
                with transaction.atomic():
                    resena.save()
            except IntegrityError:  # doble envío: la base de datos deja una sola
                messages.error(request, 'Ya existe una reseña para esta contratación.')
            else:
                messages.success(request, 'Tu reseña quedó publicada.' if nueva else 'Tu reseña quedó actualizada.')
            return redirect('resena_calificar', id_inscripcion)

    return render(request, 'resenas/calificar.html', {
        'inscripcion': inscripcion,
        'profesor': inscripcion.clase.profesor,
        'resena': resena,
        'editable': editable,
        'form': form,
    })


def _reportar(request, resena, volver):
    form = ReporteForm(request.POST)
    if ReporteResena.objects.filter(resena=resena, remitente=request.user).exists():
        messages.error(request, 'Ya reportaste esta reseña. Un administrador la revisará.')
    elif ReporteResena.supera_limite(request.user):
        messages.error(request, 'Alcanzaste el máximo de reportes por hoy. Inténtalo mañana.')
    elif not form.is_valid():
        messages.error(request, 'Indica el motivo del reporte.')
    else:
        reporte = form.save(commit=False)
        reporte.resena, reporte.remitente = resena, request.user
        try:
            with transaction.atomic():
                reporte.save()
        except IntegrityError:  # doble envío
            messages.error(request, 'Ya reportaste esta reseña. Un administrador la revisará.')
        else:
            messages.success(request, 'Gracias. Un administrador revisará la reseña; mientras tanto sigue visible.')
    return redirect(volver)


@require_POST
@alumno_required
def reportar_como_alumno(request, id_resena):
    resena = get_object_or_404(
        Resena.objects.visibles().select_related('inscripcion__clase'),
        pk=id_resena, inscripcion__clase__profesor__titulo_estado=Profesor.TITULO_APROBADO,
    )
    volver = reverse('perfil_profesor', args=[resena.inscripcion.clase.profesor_id]) + '#perfil-resenas'
    if resena.inscripcion.alumno_id == request.session['alumno_id']:
        messages.error(request, 'No puedes reportar tu propia reseña.')
        return redirect(volver)
    return _reportar(request, resena, volver)


@require_POST
@profesor_required
def reportar_como_profesor(request, id_resena):
    resena = get_object_or_404(
        Resena.objects.visibles().de_profesor(request.session['profesor_id']), pk=id_resena,
    )
    return _reportar(request, resena, reverse('resenas_profesor'))


@never_cache
@profesor_required
def resenas_profesor(request):
    profesor = get_object_or_404(Profesor.objects.select_related('user'),
                                 id_profesor=request.session['profesor_id'])
    return render(request, 'resenas/profesor.html', {
        'profesor': profesor,
        **contexto_resenas(profesor, ruta_reporte='resena_reportar_profesor'),
    })


@never_cache
@admin_required
def moderacion(request):
    pendientes = Prefetch(
        'reportes', to_attr='pendientes',
        queryset=ReporteResena.objects.filter(estado=ReporteResena.ESTADO_PENDIENTE).select_related('remitente'),
    )
    resenas = Resena.objects.select_related(*RELACIONADAS)
    return render(request, 'resenas/moderacion.html', {
        'admin': get_object_or_404(Tutor, id_tutor=request.session['admin_id']),
        'reportadas': (resenas.filter(reportes__estado=ReporteResena.ESTADO_PENDIENTE)
                       .distinct().prefetch_related(pendientes)),
        'ocultas': resenas.filter(estado=Resena.ESTADO_OCULTA),
        'historial': ModeracionResena.objects.select_related('administrador', 'resena')[:50],
        'motivos': MOTIVOS,
    })


@require_POST
@admin_required
def moderar(request, id_resena):
    resena = get_object_or_404(Resena, pk=id_resena)
    form = ModeracionForm(request.POST)
    if form.is_valid():
        moderacion = form.save(commit=False)
        resena.aplicar_moderacion(moderacion, request.user)
        messages.success(request, f'Reseña #{resena.pk}: {moderacion.get_accion_display().lower()}.')
    else:
        messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('resenas_moderacion')
