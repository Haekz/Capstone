"""Revision de documentos de profesores (titulo y especializaciones): es de soporte, solo el agente con el
ticket de ese tema ve el documento (como imagen con marca de agua) y decide. El administrador no entra."""

from cryptography.fernet import InvalidToken
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from alumnos.decorators import soporte_required
from alumnos.models import Asignatura, Especializacion, Profesor
from apoderados import documentos
from soporte.models import Ticket
from soporte.permisos import agente_en_sesion, ticket_asignado, tickets_del_agente
from user_profesor import especializaciones, titulo

from .models import AccesoTitulo


def _profesor_con_ticket(request, pk):
    """Solo con el ticket del titulo: el de sus especializaciones no da acceso al titulo."""
    profesor = get_object_or_404(Profesor, id_profesor=pk)
    if ticket_asignado(request, profesor=profesor, categoria=Ticket.TITULOS) is None:
        raise Http404('Título no encontrado.')
    return profesor


def _especializacion_con_ticket(request, pk):
    """Solo con el ticket de especializaciones de su profesor: el del titulo no da acceso."""
    especializacion = get_object_or_404(Especializacion.objects.select_related('profesor__user'), pk=pk)
    if ticket_asignado(request, profesor=especializacion.profesor, categoria=Ticket.ESPECIALIZACIONES) is None:
        raise Http404('Especialización no encontrada.')
    return especializacion


def _imagen(request, contenido):
    """El documento como imagen con marca de agua de quien lo abre. El original no sale del servidor."""
    try:
        imagen = documentos.con_marca_de_agua(contenido, documentos.texto_de_revision(request.user))
    except InvalidToken:  # cambio la clave de cifrado: hay que pedir el documento de nuevo
        raise Http404('El documento ya no se puede leer.')
    respuesta = HttpResponse(imagen, content_type='image/jpeg')
    respuesta['Content-Disposition'] = 'inline'  # se ve en el navegador, sin descarga directa
    return respuesta


@never_cache
@soporte_required
def titulos_adm(request):
    agente = agente_en_sesion(request)
    profesores = Profesor.objects.order_by('titulo_estado', 'user__first_name')
    return render(request, 'admin_portal/titulos_adm.html', {
        'agente': agente,
        'en_revision': profesores.filter(titulo_estado=Profesor.TITULO_EN_REVISION,
                                         tickets__in=tickets_del_agente(request).filter(categoria=Ticket.TITULOS)),
        'especializaciones': Especializacion.objects.filter(
            estado=Especializacion.EN_REVISION,
            profesor__tickets__in=tickets_del_agente(request).filter(categoria=Ticket.ESPECIALIZACIONES),
        ).select_related('profesor__user').prefetch_related('propuestas').defer('contenido').order_by('subida'),
        'otros': profesores.exclude(titulo_estado=Profesor.TITULO_EN_REVISION) if agente.es_lider else None,
        'asignaturas_catalogo': Asignatura.objects.order_by('nombre'),  # las que soporte puede asignar al aprobar
        'accesos': (AccesoTitulo.objects.select_related('agente', 'profesor__user', 'especializacion')[:50]
                    if agente.es_lider else None),
    })


@never_cache
@soporte_required
def ver_titulo(request, pk):
    """Imagen del titulo con marca de agua, solo para el agente con el ticket. El original no sale del servidor."""
    profesor = _profesor_con_ticket(request, pk)
    if not profesor.titulo_contenido:
        raise Http404('Sin título')
    AccesoTitulo.objects.create(agente=request.user, profesor=profesor)
    return _imagen(request, profesor.titulo_contenido)


@never_cache
@soporte_required
def ver_especializacion(request, pk):
    """El certificado con marca de agua, solo para el agente con el ticket de especializaciones."""
    especializacion = _especializacion_con_ticket(request, pk)
    if not especializacion.contenido:
        raise Http404('Sin documento')
    AccesoTitulo.objects.create(agente=request.user, profesor=especializacion.profesor,
                                especializacion=especializacion)
    return _imagen(request, especializacion.contenido)


def _asignadas(clases):
    """Fin del mensaje de exito: que asignaturas nuevas quedo dictando."""
    return f' Asignaturas nuevas: {", ".join(c.asignatura.nombre for c in clases)}.' if clases else ''


@require_POST
@soporte_required
def resolver_titulo(request, pk):
    profesor = _profesor_con_ticket(request, pk)
    aprobar = request.POST.get('decision') == 'aprobar'
    try:
        nuevas = titulo.resolver(profesor, aprobar, request.POST.get('observacion', ''),
                                 request.POST.getlist('asignaturas'))
    except ValidationError as e:
        messages.error(request, e.messages[0])
    else:
        estado = 'aprobado' if aprobar else 'rechazado'
        messages.success(request, f'Título de {profesor.nombre} {estado}.{_asignadas(nuevas)}')
    return redirect('titulos_adm')


@require_POST
@soporte_required
def resolver_especializacion(request, pk):
    especializacion = _especializacion_con_ticket(request, pk)
    aprobar = request.POST.get('decision') == 'aprobar'
    try:
        nuevas = especializaciones.resolver(especializacion, aprobar, request.POST.get('observacion', ''),
                                            request.POST.getlist('asignaturas'))
    except ValidationError as e:
        messages.error(request, e.messages[0])
    else:
        estado = 'aprobada' if aprobar else 'rechazada'
        nombre, profesor = especializacion.nombre, especializacion.profesor.nombre
        messages.success(request, f'Especialización «{nombre}» de {profesor} {estado}.{_asignadas(nuevas)}')
    return redirect('titulos_adm')
