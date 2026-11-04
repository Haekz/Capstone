"""Registrar, verificar, entregar y cerrar un requerimiento de autoridad. Unico lugar que cambia su estado.

recibido -> verificado -> cerrado, o rechazado desde recibido o verificado. Solo avanza. Entregar exige estar
verificado. Cada paso queda con el agente y la hora.
"""

from django.db import transaction
from django.utils import timezone

from .models import Entrega, Requerimiento


class RequerimientoError(Exception):
    """Paso no permitido en el estado actual; el mensaje se le muestra al lider."""


def _bloquear(requerimiento, *estados):
    """El requerimiento con candado, solo si esta en alguno de ``estados`` (dos lideres a la vez no se pisan)."""
    actual = Requerimiento.objects.select_for_update().get(pk=requerimiento.pk)
    if actual.estado not in estados:
        nombres = dict(Requerimiento.ESTADOS)
        raise RequerimientoError(f'No se puede hacer eso: el requerimiento está «{nombres[actual.estado].lower()}».')
    return actual


def registrar(agente, autoridad, referencia, recibido, alcance, vence=None):
    if vence is not None and vence < recibido:
        raise RequerimientoError('El plazo de la autoridad no puede ser anterior a la fecha en que se recibió.')
    return Requerimiento.objects.create(registrado_por=agente, autoridad=autoridad, referencia=referencia,
                                        recibido=recibido, alcance=alcance, vence=vence)


def verificar(agente, requerimiento, verificacion):
    with transaction.atomic():
        actual = _bloquear(requerimiento, Requerimiento.RECIBIDO)
        actual.estado, actual.verificacion = Requerimiento.VERIFICADO, verificacion
        actual.verificado, actual.verificado_por = timezone.now(), agente
        actual.save(update_fields=['estado', 'verificacion', 'verificado', 'verificado_por'])
    return actual


def entregar(agente, requerimiento, datos, medio, destinatario):
    """Anota una entrega. Solo con el requerimiento verificado; puede haber varias."""
    with transaction.atomic():
        actual = _bloquear(requerimiento, Requerimiento.VERIFICADO)
        return Entrega.objects.create(requerimiento=actual, entregada_por=agente, datos=datos, medio=medio,
                                      destinatario=destinatario)


def _resolver(agente, requerimiento, estado, resolucion, *desde):
    with transaction.atomic():
        actual = _bloquear(requerimiento, *desde)
        actual.estado, actual.resolucion = estado, resolucion
        actual.resuelto, actual.resuelto_por = timezone.now(), agente
        actual.save(update_fields=['estado', 'resolucion', 'resuelto', 'resuelto_por'])
    return actual


def rechazar(agente, requerimiento, resolucion):
    """No corresponde atenderlo (no se pudo verificar, no es competente, pide demasiado)."""
    return _resolver(agente, requerimiento, Requerimiento.RECHAZADO, resolucion,
                     Requerimiento.RECIBIDO, Requerimiento.VERIFICADO)


def cerrar(agente, requerimiento, resolucion):
    """Se atendio (con o sin entregas). Solo un requerimiento verificado."""
    return _resolver(agente, requerimiento, Requerimiento.CERRADO, resolucion, Requerimiento.VERIFICADO)
