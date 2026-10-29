"""Revision de titulos profesionales: es de soporte, solo el agente con el ticket
ve el archivo y decide. El administrador no entra."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from alumnos.decorators import soporte_required
from alumnos.models import Profesor
from soporte.permisos import agente_en_sesion, ticket_asignado, tickets_del_agente
from user_profesor import titulo


def _profesor_con_ticket(request, pk):
    profesor = get_object_or_404(Profesor, id_profesor=pk)
    if ticket_asignado(request, profesor=profesor) is None:
        raise Http404('Título no encontrado.')
    return profesor


@never_cache
@soporte_required
def titulos_adm(request):
    agente = agente_en_sesion(request)
    profesores = Profesor.objects.order_by('titulo_estado', 'user__first_name')
    return render(request, 'admin_portal/titulos_adm.html', {
        'agente': agente,
        'en_revision': profesores.filter(titulo_estado=Profesor.TITULO_EN_REVISION,
                                         tickets__in=tickets_del_agente(request)),
        'otros': profesores.exclude(titulo_estado=Profesor.TITULO_EN_REVISION) if agente.es_lider else None,
    })


@never_cache
@soporte_required
def ver_titulo(request, pk):
    """Sirve el archivo solo al agente con el ticket: el titulo es un documento privado."""
    profesor = _profesor_con_ticket(request, pk)
    if not profesor.titulo_archivo:
        raise Http404('Sin título')
    try:
        archivo = profesor.titulo_archivo.open('rb')
    except FileNotFoundError:
        raise Http404('Archivo no encontrado')
    return FileResponse(archivo, filename=profesor.titulo_archivo.name.rsplit('/', 1)[-1])


@require_POST
@soporte_required
def resolver_titulo(request, pk):
    profesor = _profesor_con_ticket(request, pk)
    aprobar = request.POST.get('decision') == 'aprobar'
    try:
        titulo.resolver(profesor, aprobar, request.POST.get('observacion', ''))
    except ValidationError as e:
        messages.error(request, e.messages[0])
    else:
        estado = 'aprobado' if aprobar else 'rechazado'
        messages.success(request, f'Título de {profesor.nombre} {estado}.')
    return redirect('titulos_adm')
