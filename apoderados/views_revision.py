"""Revision de soporte: el agente ve sus registros y vinculos pendientes, abre los documentos y decide.

Solo el agente con el ticket ve los documentos (con marca de agua y registro de cada apertura) y los
revisa. El lider ademas ve el historial, los vinculos vigentes, las revocaciones y los accesos.
"""


from cryptography.fernet import InvalidToken
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from alumnos.decorators import soporte_required
from soporte.permisos import agente_en_sesion, ticket_asignado, tickets_del_agente

from .documentos import con_marca_de_agua, texto_de_revision
from .forms import RevisionIdentidadForm, RevisionVinculoForm
from .models import AccesoDocumento, Apoderado, Documento, RevisionIdentidad, RevisionVinculo, Revocacion, Vinculo


@never_cache
@soporte_required
def revision(request):
    """Lo que el agente tiene asignado. El lider ademas ve registros, vinculos y accesos."""
    agente = agente_en_sesion(request)
    mios = tickets_del_agente(request)
    contexto = {
        'agente': agente,
        'pendientes': (Apoderado.objects.filter(estado=Apoderado.REVISION_PENDIENTE, tickets__in=mios)
                       .select_related('user').prefetch_related('documentos')),
        # Solo los que se pueden revisar: el apoderado ya tiene su identidad verificada.
        'vinculos_pendientes': (Vinculo.objects.filter(estado=Vinculo.PENDIENTE, apoderado__estado=Apoderado.VERIFICADO,
                                                       tickets__in=mios)
                                .select_related('apoderado__user', 'alumno__user')
                                .prefetch_related('invitaciones', 'documentos')),
    }
    if agente.es_lider:
        contexto.update({
            'historial': RevisionIdentidad.objects.select_related('apoderado__user', 'administrador')[:50],
            'historial_vinculos': (RevisionVinculo.objects
                                   .select_related('vinculo__apoderado__user', 'vinculo__alumno__user',
                                                   'administrador')[:50]),
            'vinculos_vigentes': (Vinculo.objects.filter(estado=Vinculo.VERIFICADO)
                                  .select_related('apoderado__user', 'alumno__user')),
            'revocaciones': Revocacion.objects.select_related('vinculo__apoderado__user', 'vinculo__alumno__user',
                                                              'autor').order_by('-fecha')[:50],
            'accesos': AccesoDocumento.objects.select_related('administrador', 'apoderado__user')[:50],
        })
    return render(request, 'apoderados/revision.html', contexto)


@never_cache
@soporte_required
def ver_documento(request, id_documento):
    """Documento por revisar, con marca de agua de quien lo abre. Cada apertura queda registrada.
    Solo para el agente con el ticket de ese apoderado o vinculo."""
    documento = get_object_or_404(Documento.objects.select_related('apoderado', 'vinculo__apoderado'),
                                  pk=id_documento)
    if ticket_asignado(request, apoderado_id=documento.apoderado_id, vinculo_id=documento.vinculo_id) is None:
        raise Http404('Documento no encontrado.')
    try:
        imagen = con_marca_de_agua(documento.contenido, texto_de_revision(request.user))
    except InvalidToken:  # cambio la clave de cifrado: hay que pedir el documento de nuevo
        raise Http404('El documento ya no se puede leer.')
    AccesoDocumento.objects.create(administrador=request.user, apoderado=documento.titular,
                                   vinculo=documento.vinculo, tipo=documento.tipo)
    respuesta = HttpResponse(imagen, content_type='image/jpeg')
    respuesta['Content-Disposition'] = 'inline'  # se ve en el navegador, sin descarga directa
    return respuesta


def _revisar(request, revisado, formulario, nombre):
    form = formulario(request.POST, revisado=revisado)
    if form.is_valid():
        revisado.aplicar_revision(form.save(commit=False), request.user)
        messages.success(request, f'{nombre}: {revisado.get_estado_display().lower()}.')
    else:
        messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('apoderados_revision')


@require_POST
@soporte_required
def revisar(request, id_apoderado):
    # Solo se revisa quien confirmo su correo y aun no tiene decision, con ticket propio.
    apoderado = get_object_or_404(Apoderado.objects.select_related('user'),
                                  pk=id_apoderado, estado=Apoderado.REVISION_PENDIENTE)
    if ticket_asignado(request, apoderado=apoderado) is None:
        raise Http404('Apoderado no encontrado.')
    return _revisar(request, apoderado, RevisionIdentidadForm, apoderado.nombre)


@require_POST
@soporte_required
def revisar_vinculo(request, id_vinculo):
    # Solo vinculos pendientes de apoderados con identidad verificada, con ticket propio.
    vinculo = get_object_or_404(Vinculo.objects.select_related('apoderado__user', 'alumno__user'),
                                pk=id_vinculo, estado=Vinculo.PENDIENTE,
                                apoderado__estado=Apoderado.VERIFICADO)
    if ticket_asignado(request, vinculo=vinculo) is None:
        raise Http404('Vínculo no encontrado.')
    return _revisar(request, vinculo, RevisionVinculoForm,
                    f'Vínculo {vinculo.apoderado.nombre} - {vinculo.alumno.user.first_name}')
