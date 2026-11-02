"""Revision de las conversaciones reportadas por el lider de soporte (paso C1f, decidido 02-nov).

Tras la respuesta legal, una conversacion reportada no se conserva para siempre por defecto:

- Con un ticket de su reporte abierto se conserva: soporte la esta revisando.
- Al cerrarse queda *pendiente*: se sigue conservando, pero el lider debe decidir.
- El lider la **libera** (vuelve a la regla de 90 dias, retencion.py) o la **conserva** como retencion
  excepcional, registrando motivo, alcance, fundamento, condicion de termino y proxima revision (a
  MESES_REVISION); el responsable queda registrado. Llegada esa fecha vuelve a pendiente.
- Un reporte posterior a la decision la deja sin efecto: se vuelve a empezar.
"""

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Subquery
from django.utils import timezone

from soporte.models import Ticket

from .models import Conversacion, DecisionRetencion, ReporteConversacion
from .servicio import MensajeError

MESES_REVISION = 6  # decision funcional: la periodicidad la define la plataforma, no la ley


def _decisiones():
    return DecisionRetencion.objects.filter(conversacion=OuterRef('pk')).order_by('-decidida', '-pk')


def _con_decision_vigente():
    """Las reportadas, con la ultima decision del lider y si hubo un reporte despues de ella."""
    posterior = ReporteConversacion.objects.filter(conversacion=OuterRef('pk'), creado__gt=OuterRef('ultima_fecha'))
    return (Conversacion.objects.reportadas()
            .annotate(ultima=Subquery(_decisiones().values('decision')[:1]),
                      ultima_fecha=Subquery(_decisiones().values('decidida')[:1]),
                      ultima_hasta=Subquery(_decisiones().values('proxima_revision')[:1]))
            .annotate(posterior=Exists(posterior)))


def liberadas():
    """Reportadas cuyo lider decidio liberar, sin un reporte posterior."""
    return _con_decision_vigente().filter(ultima=DecisionRetencion.LIBERAR, posterior=False)


def retenidas():
    """Reportadas que NO se pueden borrar: todas salvo las liberadas (con ticket abierto, pendientes
    de decision o conservadas)."""
    return Conversacion.objects.reportadas().exclude(pk__in=liberadas().values('pk'))


def pendientes(hoy):
    """Reportadas con todos sus tickets cerrados y sin decision vigente: esperan al lider. Incluye las
    conservadas cuya fecha de revision ya llego. `cerrado_el`: cuando se cerro su ultimo ticket."""
    ticket_abierto = ReporteConversacion.objects.filter(conversacion=OuterRef('pk'), ticket__estado=Ticket.ABIERTO)
    ultimo_cierre = (ReporteConversacion.objects.filter(conversacion=OuterRef('pk'))
                     .order_by('-ticket__cerrado').values('ticket__cerrado')[:1])
    sin_decision_vigente = (Q(ultima__isnull=True) | Q(posterior=True)
                            | Q(ultima=DecisionRetencion.CONSERVAR, ultima_hasta__lte=hoy))
    return (_con_decision_vigente()
            .annotate(con_ticket_abierto=Exists(ticket_abierto), cerrado_el=Subquery(ultimo_cierre))
            .filter(con_ticket_abierto=False).filter(sin_decision_vigente)
            .order_by('cerrado_el', 'pk'))


def pendiente_desde(conversacion):
    """Desde cuando espera decision (fecha): el cierre de su ultimo ticket o, si estaba conservada, el dia
    en que vencio su revision. `conversacion` viene de pendientes()."""
    desde = timezone.localdate(conversacion.cerrado_el) if conversacion.cerrado_el else timezone.localdate()
    if conversacion.ultima == DecisionRetencion.CONSERVAR and conversacion.ultima_hasta and not conversacion.posterior:
        desde = max(desde, conversacion.ultima_hasta)
    return desde


def _exigir_lider_y_pendiente(agente, conversacion, hoy):
    if not agente.es_lider:
        raise MensajeError('Solo un líder de soporte decide sobre una conversación reportada.')
    if not pendientes(hoy).filter(pk=conversacion.pk).exists():
        raise MensajeError('Esta conversación no está esperando una decisión.')


def liberar(agente, conversacion, hoy=None):
    """No hay base para seguir conservandola: vuelve a la regla normal de borrado."""
    hoy = hoy or timezone.localdate()
    with transaction.atomic():
        _exigir_lider_y_pendiente(agente, conversacion, hoy)
        return DecisionRetencion.objects.create(conversacion=conversacion, decision=DecisionRetencion.LIBERAR,
                                                decidida_por=agente)


def conservar(agente, conversacion, motivo, alcance, fundamento, termino, hoy=None):
    """Retencion excepcional: exige el motivo y los tres textos, y fija la proxima revision."""
    hoy = hoy or timezone.localdate()
    textos = {'alcance': alcance, 'fundamento': fundamento, 'termino': termino}
    if motivo not in dict(DecisionRetencion.MOTIVOS) or not all((t or '').strip() for t in textos.values()):
        raise MensajeError('Indica el motivo, los datos que se conservan, el fundamento y la condición de término.')
    with transaction.atomic():
        _exigir_lider_y_pendiente(agente, conversacion, hoy)
        return DecisionRetencion.objects.create(
            conversacion=conversacion, decision=DecisionRetencion.CONSERVAR, decidida_por=agente, motivo=motivo,
            proxima_revision=hoy + relativedelta(months=MESES_REVISION),
            **{campo: texto.strip() for campo, texto in textos.items()})
