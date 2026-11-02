"""Campana del portal: avisos de plazos segun quien la abre (paso 8c).

Un aviso es algo que espera una accion de esa persona, con su plazo. Desaparece
solo cuando se resuelve, asi que no hay "leido" que guardar. Cada rol ve lo
suyo: el admin, los retiros de los profesores (titulos y reportes son de soporte).
"""

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone

from alumnos.models import SolicitudRetiro
from alumnos.roles import ADMIN, rol_en_sesion
from alumnos.templatetags.dinero import clp


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


def para(request):
    """Avisos de quien tiene la sesion abierta; ninguno si su rol no tiene."""
    if rol_en_sesion(request) == ADMIN:
        return _de_admin(timezone.localdate())
    return []
