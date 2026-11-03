"""Pantalla de los lideres de soporte para los requerimientos de autoridad (E6). Solo lideres: ni el agente comun
ni el administrador. Todos los cambios pasan por gestion.py."""

from collections import namedtuple

from django.contrib import messages
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from soporte.permisos import agente_en_sesion, lider_required

from . import forms, gestion
from .models import Requerimiento

R = Requerimiento
# nombre en la URL -> formulario, funcion de gestion, estados en que se ofrece y mensaje de exito
Accion = namedtuple('Accion', 'titulo boton formulario funcion estados exito')
ACCIONES = {
    'verificar': Accion('Verificar', 'Marcar como verificado', forms.VerificarForm, gestion.verificar,
                        (R.RECIBIDO,), 'Requerimiento verificado: ya se pueden registrar entregas.'),
    'entregar': Accion('Registrar una entrega', 'Registrar la entrega', forms.EntregarForm, gestion.entregar,
                       (R.VERIFICADO,), 'Entrega registrada.'),
    'cerrar': Accion('Cerrar', 'Cerrar el requerimiento', forms.CerrarForm, gestion.cerrar,
                     (R.VERIFICADO,), 'Requerimiento cerrado.'),
    'rechazar': Accion('Rechazar', 'Rechazar el requerimiento', forms.RechazarForm, gestion.rechazar,
                       (R.RECIBIDO, R.VERIFICADO), 'Requerimiento rechazado.'),
}


@never_cache
@lider_required
def lista(request):
    return render(request, 'requerimientos/lista.html', {
        'agente': agente_en_sesion(request),
        'abiertos': R.objects.filter(estado__in=R.ABIERTOS).order_by(F('vence').asc(nulls_last=True), 'registrado'),
        'resueltos': R.objects.exclude(estado__in=R.ABIERTOS)[:50],
    })


@never_cache
@lider_required
def nuevo(request):
    agente = agente_en_sesion(request)
    form = forms.RegistrarForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            requerimiento = gestion.registrar(agente, **form.cleaned_data)
        except gestion.RequerimientoError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, 'Requerimiento registrado. Falta verificarlo antes de entregar nada.')
            return redirect('requerimiento_detalle', requerimiento.pk)
    return render(request, 'requerimientos/nuevo.html', {'agente': agente, 'form': form})


@never_cache
@lider_required
def detalle(request, pk):
    requerimiento = get_object_or_404(R.objects.select_related('registrado_por__user', 'verificado_por__user',
                                                               'resuelto_por__user'), pk=pk)
    ofrecidas = [(nombre, accion, accion.formulario()) for nombre, accion in ACCIONES.items()
                 if requerimiento.estado in accion.estados]
    return render(request, 'requerimientos/detalle.html', {
        'agente': agente_en_sesion(request), 'r': requerimiento, 'acciones': ofrecidas,
        'entregas': requerimiento.entregas.select_related('entregada_por__user'),
    })


@require_POST
@lider_required
def accion(request, pk, nombre):
    if nombre not in ACCIONES:
        raise Http404
    requerimiento = get_object_or_404(R, pk=pk)
    spec = ACCIONES[nombre]
    form = spec.formulario(request.POST)
    if not form.is_valid():
        messages.error(request, next(iter(form.errors.values()))[0])
        return redirect('requerimiento_detalle', pk)
    datos = {campo: valor for campo, valor in form.cleaned_data.items() if not campo.startswith('ok_')}
    try:
        spec.funcion(agente_en_sesion(request), requerimiento, **datos)
    except gestion.RequerimientoError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, spec.exito)
    return redirect('requerimiento_detalle', pk)
