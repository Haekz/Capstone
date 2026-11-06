"""Reglas de permiso de soporte que tambien usan otras apps (apoderados, admin_portal)."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect

from alumnos.decorators import soporte_required
from alumnos.models import Alumno
from alumnos.roles import APODERADO, SOPORTE, abre_tickets, redirigir_a_portal, rol_en_sesion
from apoderados.models import Vinculo
from apoderados.permisos import debe_renovar_clave

from .models import AgenteSoporte, Habilitacion, Ticket


def agente_en_sesion(request):
    """Perfil del agente con sesion abierta (como el Tutor en el portal admin)."""
    return get_object_or_404(AgenteSoporte.objects.select_related('user'),
                             pk=request.session.get(SOPORTE.clave_sesion))


def con_agente(tickets):
    """Los de ``tickets`` que su agente asignado ve: habilitado en la categoria o lider (a
    este le llegan escalados de cualquier categoria). Si a un agente le quitan la
    categoria, sus tickets quedan sin nadie que los vea, y el lider se entera."""
    habilitado = Habilitacion.objects.filter(agente=OuterRef('asignado'), categoria=OuterRef('categoria'))
    return tickets.filter(Q(asignado__es_lider=True) | Exists(habilitado))


def tickets_del_agente(request):
    """Tickets abiertos asignados al agente en sesion que puede ver (con_agente)."""
    return con_agente(Ticket.objects.filter(estado=Ticket.ABIERTO,
                                            asignado_id=request.session.get(SOPORTE.clave_sesion)))


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


def categorias_que_reporta(request):
    """Categorias en que el usuario en sesion puede abrir tickets (D10). El alumno
    menor ninguna: los abre su apoderado (D18, revisada el 01-nov)."""
    if not request.user.is_authenticated or not abre_tickets(rol_en_sesion(request), request.user):
        return ()
    return Ticket.DE_USUARIOS


def estudiantes_que_reporta(request):
    """Del apoderado en sesion, sus estudiantes con vinculo verificado: reporta por
    ellos (D18). Para otro rol, ninguno."""
    if rol_en_sesion(request) != APODERADO:
        return Alumno.objects.none()
    return (Alumno.objects.filter(vinculos_apoderado__apoderado__user=request.user,
                                  vinculos_apoderado__estado=Vinculo.VERIFICADO)
            .select_related('user').distinct())


def reporta_required(vista):
    """Alumno, profesor o apoderado con sesion. Otro rol vuelve a su portal; anonimo, al login
    (con ?next=, para volver aqui tras entrar)."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not categorias_que_reporta(request):
            rol = rol_en_sesion(request)
            return redirigir_a_portal(rol) if rol else redirect_to_login(request.get_full_path(), 'login')
        if debe_renovar_clave(request.user):  # misma regla que alumno_required
            return redirect('nueva_clave_estudiante')
        return vista(request, *args, **kwargs)

    return envoltura
