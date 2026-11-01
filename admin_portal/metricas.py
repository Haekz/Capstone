"""Cifras reales del panel del admin (paso 8).

Siguen docs/POLITICA_PAQUETES.md: lo cobrado por clases que aun no se dictan es
una obligacion, no un ingreso, y no pasa a ser ganancia al vencer el paquete.
LBWUS gana su comision solo por las clases ya dictadas: es la misma cuenta que
el saldo del profesor (user_profesor.views.calcular_saldos), vista desde LBWUS.
"""

from django.db.models import Sum

from alumnos import paquetes
from alumnos.models import Inscripcion, PaqueteClases, SolicitudRetiro, Suscripcion


def _suma(consulta):
    return consulta.aggregate(total=Sum('monto'))['total'] or 0


def finanzas():
    """Montos en pesos para las tarjetas de Finanzas."""
    # Pagos aprobados por Webpay. Las suscripciones ya no se venden, pero su dinero entro.
    cobrado_paquetes = _suma(PaqueteClases.objects.filter(estado=PaqueteClases.ESTADO_ACTIVA))
    cobrado = cobrado_paquetes + _suma(Suscripcion.objects.filter(estado=Suscripcion.ESTADO_ACTIVA))
    dictadas = list(Inscripcion.objects.completadas().select_related('paquete'))
    dictado_de_paquetes = sum(paquetes.valor_clase(i) for i in dictadas if i.paquete_id)
    return {
        'cobrado': cobrado,
        'ganancia': sum(paquetes.comision(paquetes.valor_clase(i)) for i in dictadas),
        'por_dictar': max(0, cobrado_paquetes - dictado_de_paquetes),
        'retiros_pagados': _suma(SolicitudRetiro.objects.filter(estado=SolicitudRetiro.PAGADO)),
        # Pendientes de pagar: los que esperan revision y los aprobados sin transferir.
        'retiros_pendientes': _suma(SolicitudRetiro.objects.filter(
            estado__in=[SolicitudRetiro.PENDIENTE, SolicitudRetiro.APROBADO])),
    }
