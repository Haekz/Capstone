"""Reglas de permiso de soporte que tambien usan otras apps (apoderados, admin_portal)."""

from functools import wraps

from django.db.models import F
from django.shortcuts import get_object_or_404, redirect

from alumnos.decorators import soporte_required
from alumnos.roles import SOPORTE

from .models import AgenteSoporte, Ticket


def agente_en_sesion(request):
    """Perfil del agente con sesion abierta (como el Tutor en el portal admin)."""
    return get_object_or_404(AgenteSoporte.objects.select_related('user'),
                             pk=request.session.get(SOPORTE.clave_sesion))


def tickets_del_agente(request):
    """Tickets abiertos asignados al agente en sesion, en categorias en que sigue habilitado."""
    return Ticket.objects.filter(estado=Ticket.ABIERTO, asignado_id=request.session.get(SOPORTE.clave_sesion),
                                 asignado__habilitaciones__categoria=F('categoria'))


def ticket_asignado(request, **revisado):
    """Ticket abierto de ``revisado`` asignado al agente en sesion, o None.

    Sin ticket propio no se ven documentos ni se decide: ni el lider ni el
    administrador. Un id ajeno o manipulado da None.
    """
    return tickets_del_agente(request).filter(**revisado).first()


def lider_required(vista):
    """Rol soporte y cargo de lider; un agente vuelve a su panel."""
    @wraps(vista)
    def solo_lider(request, *args, **kwargs):
        if not agente_en_sesion(request).es_lider:
            return redirect(SOPORTE.ruta_portal)
        return vista(request, *args, **kwargs)

    return soporte_required(solo_lider)
