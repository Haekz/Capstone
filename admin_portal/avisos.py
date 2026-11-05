"""Campana del portal: avisos de plazos segun quien la abre (paso 8c).

Un aviso es algo que espera una accion de esa persona, con su plazo. Desaparece
solo cuando se resuelve, asi que no hay "leido" que guardar. Cada rol ve lo
suyo: el admin, los retiros de los profesores y las reseñas reportadas (titulos
y reportes de usuarios son de soporte);
el agente de soporte, sus tickets por vencer o atrasados; el lider, ademas, los
tickets que nadie atiende y los atrasos del equipo.
"""

from dataclasses import dataclass

from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from alumnos.models import SolicitudRetiro
from alumnos.roles import ADMIN, SOPORTE, rol_en_sesion
from alumnos.templatetags.dinero import clp
from mensajes import revision
from resenas.models import ReporteResena
from soporte import plazos
from soporte.models import AgenteSoporte, Ticket
from soporte.permisos import tickets_del_agente


@dataclass(frozen=True)
class Aviso:
    titulo: str
    detalle: str
    url: str
    urgente: bool = False


def _retiros(cantidad):
    return f'{cantidad} retiro' if cantidad == 1 else f'{cantidad} retiros'


def _tickets(cantidad):
    return f'{cantidad} ticket' if cantidad == 1 else f'{cantidad} tickets'


def _hace(dia, hoy):
    dias = (hoy - dia).days
    return 'hoy' if dias <= 0 else 'hace 1 día' if dias == 1 else f'hace {dias} días'


def _suman(retiros):
    return clp(sum(r.monto for r in retiros))


def _de_admin(hoy):
    """Retiros (por revisar, para pagar hoy o atrasados, en espera) y reseñas por moderar."""
    finanzas = reverse('dashboard_admin') + '#section-finanzas'
    avisos = []

    atrasados, de_hoy, en_espera = [], [], []
    aprobados = SolicitudRetiro.objects.filter(estado=SolicitudRetiro.APROBADO).select_related(
        'profesor__user', 'profesor__cuenta_bancaria')
    for retiro in aprobados:
        cuenta = getattr(retiro.profesor, 'cuenta_bancaria', None)
        if cuenta is not None and cuenta.bloqueada:
            en_espera.append((retiro, cuenta))
            continue
        pagar_el = retiro.pagar_el or hoy  # sin fecha (retiros antiguos): se debe, se avisa ya
        if pagar_el < hoy:
            atrasados.append(retiro)
        elif pagar_el == hoy:
            de_hoy.append(retiro)

    if atrasados:
        desde = min(r.pagar_el or hoy for r in atrasados)
        cuando = f'Debía pagarse el {desde:%d/%m}' if len(atrasados) == 1 else f'Debían pagarse desde el {desde:%d/%m}'
        avisos.append(Aviso(f'{_retiros(len(atrasados))} con pago atrasado',
                            f'Suman {_suman(atrasados)}. {cuando}.',
                            finanzas, urgente=True))
    if de_hoy:
        avisos.append(Aviso(f'{_retiros(len(de_hoy))} para pagar hoy',
                            f'Suman {_suman(de_hoy)}. Transfiere y registra el número de operación.',
                            finanzas))

    pendientes = list(SolicitudRetiro.objects.filter(estado=SolicitudRetiro.PENDIENTE)
                      .order_by('fecha_solicitud'))
    if pendientes:
        vencidos = any(r.pagar_el and r.pagar_el <= hoy for r in pendientes)
        avisos.append(Aviso(
            f'{_retiros(len(pendientes))} por revisar',
            f'Suman {_suman(pendientes)}. El más antiguo llegó '
            f'{_hace(timezone.localdate(pendientes[0].fecha_solicitud), hoy)}.'
            + (' Hay retiros que ya debían pagarse.' if vencidos else ''),
            finanzas, urgente=vencidos))

    for retiro, cuenta in en_espera:
        desde = timezone.localtime(cuenta.pagable_desde)
        avisos.append(Aviso(f'Retiro de {retiro.profesor.nombre}: espera para transferir',
                            f'Su cuenta bancaria cambió: se puede pagar desde el {desde:%d/%m %H:%M}.',
                            finanzas))

    reportes = ReporteResena.objects.filter(estado=ReporteResena.ESTADO_PENDIENTE)
    primero = reportes.order_by('creado').first()
    if primero:
        resenas = reportes.values('resena').distinct().count()  # varios reportes de una misma reseña: una
        avisos.append(Aviso(
            '1 reseña reportada' if resenas == 1 else f'{resenas} reseñas reportadas',
            f'Por moderar. El reporte más antiguo llegó {_hace(timezone.localdate(primero.creado), hoy)}.',
            reverse('resenas_moderacion')))
    return avisos


def _de_agente(request, ahora):
    """Sus tickets sin respuesta: atrasados, y los que vencen a mas tardar el proximo dia habil.

    Misma regla de atraso que Ticket.atrasado: responder un ticket de usuario cumple el plazo.
    """
    hoy = timezone.localdate(ahora)
    avisos = []
    for ticket in (tickets_del_agente(request)
                   .filter(respondido__isnull=True, vence__lte=plazos.vencimiento(ahora, 1))
                   .order_by('vence')):
        vence = timezone.localtime(ticket.vence)
        # El de un usuario o visitante se abre en su conversacion; las verificaciones, desde el panel.
        url = reverse('soporte_reporte', args=[ticket.pk]) if ticket.es_conversacion else reverse('panel_soporte')
        if ticket.vence < ahora:
            avisos.append(Aviso(f'Ticket #{ticket.pk} atrasado', f'{ticket.asunto}. Venció el {vence:%d/%m}.',
                                url, urgente=True))
        else:
            cuando = 'hoy' if vence.date() == hoy else f'el {vence:%d/%m}'
            avisos.append(Aviso(f'Ticket #{ticket.pk} vence {cuando}', f'{ticket.asunto}.',
                                url, urgente=ticket.categoria == Ticket.CONDUCTA))
    return avisos


def _del_lider(agente_id, ahora):
    """Lo que solo resuelve el lider: tickets que ningun agente ve y atrasos de otros agentes.

    "Con agente" es la regla de tickets_del_agente: asignado y habilitado en la categoria.
    Si al agente le quitan la categoria, sus tickets quedan sin nadie que los vea.
    """
    panel = reverse('panel_soporte')
    abiertos = Ticket.objects.filter(estado=Ticket.ABIERTO)
    con_agente = abiertos.filter(asignado__habilitaciones__categoria=F('categoria'))
    avisos = []

    sin_agente = list(abiertos.exclude(pk__in=con_agente.values('pk')))
    if sin_agente:
        avisos.append(Aviso(
            f'{_tickets(len(sin_agente))} sin agente',
            'Sin asignar, o su agente ya no está habilitado en la categoría: nadie los ve. Reasígnalos.',
            panel, urgente=any(t.respondido is None and t.vence < ahora for t in sin_agente)))

    atrasados = list(con_agente.filter(respondido__isnull=True, vence__lt=ahora)
                     .exclude(asignado_id=agente_id).order_by('vence'))  # los propios ya salen arriba
    if atrasados:
        primero = atrasados[0]
        avisos.append(Aviso(
            f'{_tickets(len(atrasados))} {"atrasado" if len(atrasados) == 1 else "atrasados"} del equipo',
            f'El más atrasado es el #{primero.pk}: venció el {timezone.localtime(primero.vence):%d/%m}.',
            panel, urgente=True))

    hoy = timezone.localdate()
    por_revisar = list(revision.pendientes(hoy))
    if por_revisar:
        avisos.append(Aviso(
            f'{len(por_revisar)} {"conversación reportada" if len(por_revisar) == 1 else "conversaciones reportadas"} por revisar',
            'Su ticket ya se cerró: decide si se libera o se conserva como retención excepcional. Mientras tanto se conserva.',
            reverse('mensajes_revision'),
            urgente=any(plazos.dias_habiles_entre(revision.pendiente_desde(c), hoy) >= Ticket.AVISO_CADA
                        for c in por_revisar)))
    return avisos


def para(request):
    """Avisos de quien tiene la sesion abierta; ninguno si su rol no tiene."""
    rol = rol_en_sesion(request)
    if rol == ADMIN:
        return _de_admin(timezone.localdate())
    if rol == SOPORTE:
        ahora, agente_id = timezone.now(), request.session.get(SOPORTE.clave_sesion)
        avisos = _de_agente(request, ahora)
        if AgenteSoporte.objects.filter(pk=agente_id, es_lider=True).exists():
            avisos += _del_lider(agente_id, ahora)
        return avisos
    return []
