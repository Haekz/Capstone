"""Campana del portal: avisos de plazos segun quien la abre (paso 8c).

Un aviso es algo que espera una accion de esa persona, con su plazo. Desaparece
solo cuando se resuelve, asi que no hay "leido" que guardar. Cada rol ve lo
suyo: el admin, los retiros de los profesores (titulos y reportes son de soporte);
el agente de soporte, sus tickets por vencer o atrasados.
"""

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone

from alumnos.models import SolicitudRetiro
from alumnos.roles import ADMIN, SOPORTE, rol_en_sesion
from alumnos.templatetags.dinero import clp
from soporte import plazos
from soporte.models import Ticket
from soporte.permisos import tickets_del_agente


@dataclass(frozen=True)
class Aviso:
    titulo: str
    detalle: str
    url: str
    urgente: bool = False


def _retiros(cantidad):
    return f'{cantidad} retiro' if cantidad == 1 else f'{cantidad} retiros'


def _hace(dia, hoy):
    dias = (hoy - dia).days
    return 'hoy' if dias <= 0 else 'hace 1 día' if dias == 1 else f'hace {dias} días'


def _suman(retiros):
    return clp(sum(r.monto for r in retiros))


def _de_admin(hoy):
    """Retiros: por revisar, para pagar hoy o atrasados, y los que aun no se pueden pagar."""
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
        # El de un usuario se abre en su conversacion; las verificaciones, desde el panel.
        url = reverse('soporte_reporte', args=[ticket.pk]) if ticket.autor_id else reverse('panel_soporte')
        if ticket.vence < ahora:
            avisos.append(Aviso(f'Ticket #{ticket.pk} atrasado', f'{ticket.asunto}. Venció el {vence:%d/%m}.',
                                url, urgente=True))
        else:
            cuando = 'hoy' if vence.date() == hoy else f'el {vence:%d/%m}'
            avisos.append(Aviso(f'Ticket #{ticket.pk} vence {cuando}', f'{ticket.asunto}.',
                                url, urgente=ticket.categoria == Ticket.CONDUCTA))
    return avisos


def para(request):
    """Avisos de quien tiene la sesion abierta; ninguno si su rol no tiene."""
    rol = rol_en_sesion(request)
    if rol == ADMIN:
        return _de_admin(timezone.localdate())
    if rol == SOPORTE:
        return _de_agente(request, timezone.now())
    return []
