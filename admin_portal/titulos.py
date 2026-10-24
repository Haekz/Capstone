"""Revision de titulos profesionales (solo admins)."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from alumnos.decorators import admin_required
from alumnos.models import Profesor, Tutor
from user_profesor import titulo


@never_cache
@admin_required
def titulos_adm(request):
    profesores = Profesor.objects.order_by('titulo_estado', 'user__first_name')
    return render(request, 'admin_portal/titulos_adm.html', {
        'admin': get_object_or_404(Tutor, id_tutor=request.session['admin_id']),
        'en_revision': profesores.filter(titulo_estado=Profesor.TITULO_EN_REVISION),
        'otros': profesores.exclude(titulo_estado=Profesor.TITULO_EN_REVISION),
    })


@never_cache
@admin_required
def ver_titulo(request, pk):
    """Sirve el archivo solo a admins: el titulo es un documento privado."""
    profesor = get_object_or_404(Profesor, id_profesor=pk)
    if not profesor.titulo_archivo:
        raise Http404('Sin título')
    try:
        archivo = profesor.titulo_archivo.open('rb')
    except FileNotFoundError:
        raise Http404('Archivo no encontrado')
    return FileResponse(archivo, filename=profesor.titulo_archivo.name.rsplit('/', 1)[-1])


@require_POST
@admin_required
def resolver_titulo(request, pk):
    profesor = get_object_or_404(Profesor, id_profesor=pk)
    aprobar = request.POST.get('decision') == 'aprobar'
    try:
        titulo.resolver(profesor, aprobar, request.POST.get('observacion', ''))
    except ValidationError as e:
        messages.error(request, e.messages[0])
    else:
        estado = 'aprobado' if aprobar else 'rechazado'
        messages.success(request, f'Título de {profesor.nombre} {estado}.')
    return redirect('titulos_adm')
