"""Pantalla "Asignaturas" del admin: ver el catalogo, crear, renombrar y eliminar las que nadie usa (fase 4).

Las reglas estan en alumnos/catalogo.py; aqui solo se muestran y se reciben los formularios.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from alumnos import catalogo
from alumnos.decorators import admin_required
from alumnos.models import Asignatura


@never_cache
@admin_required
def asignaturas_adm(request):
    usadas = catalogo.en_uso()
    asignaturas = Asignatura.objects.annotate(clases=Count('clase')).order_by('nombre')
    return render(request, 'admin_portal/asignaturas_adm.html', {
        'asignaturas': [(a, a.pk in usadas) for a in asignaturas],
        'largo_maximo': catalogo.LARGO,
    })


def _aplicar(request, accion, exito):
    """Corre la accion del catalogo y avisa el resultado."""
    try:
        resultado = accion()
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, exito(resultado))
    return redirect('asignaturas_adm')


@require_POST
@admin_required
def crear_asignatura(request):
    return _aplicar(request, lambda: catalogo.crear(request.POST.get('nombre')),
                    lambda a: f'Asignatura «{a.nombre}» creada. Soporte ya puede asignarla.')


@require_POST
@admin_required
def renombrar_asignatura(request, pk):
    asignatura = get_object_or_404(Asignatura, pk=pk)
    anterior = asignatura.nombre
    return _aplicar(request, lambda: catalogo.renombrar(asignatura, request.POST.get('nombre')),
                    lambda a: f'«{anterior}» ahora se llama «{a.nombre}».')


@require_POST
@admin_required
def eliminar_asignatura(request, pk):
    asignatura = get_object_or_404(Asignatura, pk=pk)
    return _aplicar(request, lambda: catalogo.eliminar(asignatura),
                    lambda _: f'Asignatura «{asignatura.nombre}» eliminada.')
