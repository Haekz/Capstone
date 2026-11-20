"""Reembolso automatico por Transbank de una devolucion de videos (decidido 13-nov).

Antes soporte transfería a mano todas las devoluciones. Ahora se intenta devolver por el mismo medio de pago
(Transaction.refund de Webpay Plus); si Transbank rechaza, queda como siempre: soporte la resuelve y, si no puede,
la escala al administrador (alumnos/devoluciones_videos.py: marcar_devuelta).

Reglas de Transbank (transbankdevelopers.cl/documentacion/webpay-plus): antes de 3 horas y por el total es una
reversa; despues, una anulacion; hasta 90 dias desde la venta; el parcial en credito solo vale sin cuotas o con cuotas
emisor. No las repetimos aqui: Transbank decide y cualquier rechazo cae al camino manual.

Una devolucion puede salir de varias transacciones: el agregado se pago dentro de la del paquete y cada extra tiene la
suya. Se reparte entre ellas sin pasarse de lo pagado en cada una, y cada reembolso queda registrado ANTES de llamar a
Transbank (ReembolsoTransbank): nunca se devuelve dos veces lo mismo. La llamada va fuera de toda transaccion de base
de datos, para no mantener bloqueos mientras se espera la red.
"""

import logging

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from . import webpay
from .models.videos import CompraVideosExtra, DevolucionVideos, ReembolsoTransbank

logger = logging.getLogger(__name__)

LARGO_ERROR = 200  # DevolucionVideos.error_reembolso
EN_CURSO = 'Hay un reembolso en curso o sin confirmar para este caso. Verifícalo en Transbank antes de repetir.'


def _pagos(paquete):
    """[(token_ws, monto)] de las transacciones que pagaron videos del paquete: los extra (los mas nuevos primero) y
    despues el agregado, que viaja dentro de la transaccion del paquete. Sin token no se puede reembolsar."""
    extras = (paquete.compras_videos_extra.filter(estado=CompraVideosExtra.ESTADO_ACTIVA).exclude(token_ws='')
              .order_by('-fecha_pago', '-id'))
    pagos = [(compra.token_ws, compra.monto) for compra in extras]
    if paquete.token_ws and paquete.monto_videos:
        pagos.append((paquete.token_ws, paquete.monto_videos))
    return pagos


def _ya_reembolsado(token_ws):
    """Lo pedido a Transbank por esa transaccion, confirmado o no: un pedido sin respuesta se cuenta como hecho."""
    return ReembolsoTransbank.objects.filter(token_ws=token_ws).aggregate(total=Sum('monto'))['total'] or 0


def _repartir(devolucion):
    """[(token_ws, monto)] que cubre lo que falta devolver, o None si no alcanza (queda a mano).

    Una devolucion usa cada transaccion una sola vez (unicidad del registro): si una parte falla y se reintenta, se
    saltan las ya pedidas y lo que no cubran las demas se devuelve a mano.
    """
    usados = set(devolucion.reembolsos.values_list('token_ws', flat=True))
    falta = devolucion.por_devolver
    partes = []
    for token_ws, pagado in _pagos(devolucion.paquete):
        if falta == 0:
            break
        if token_ws in usados:
            continue
        tomar = min(falta, pagado - _ya_reembolsado(token_ws))
        if tomar > 0:
            partes.append((token_ws, tomar))
            falta -= tomar
    return partes if falta == 0 else None


def _fallo(devolucion, motivo):
    devolucion.error_reembolso = motivo[:LARGO_ERROR]
    devolucion.save(update_fields=['error_reembolso'])
    return False


def _pedir(token_ws, monto):
    """Respuesta de Transbank, o ValueError si responde con codigo de rechazo (una reversa solo trae el tipo)."""
    respuesta = webpay._tx().refund(token_ws, monto)
    if respuesta.get('type') == 'NULLIFIED' and respuesta.get('response_code') != 0:
        raise ValueError(f'Transbank no anuló la compra (código {respuesta.get("response_code")}).')
    return respuesta


def intentar(devolucion):
    """Intenta devolver por Transbank lo que falta de ``devolucion``. True si queda completamente devuelta.

    Si no se puede (sin token, sin saldo en esas transacciones, plazo, tarjeta, red), False y el motivo en
    ``devolucion.error_reembolso`` para que soporte lo vea; queda para devolver a mano. Se puede repetir.
    """
    if devolucion.devuelta:
        return False
    if devolucion.reembolsos.filter(confirmado__isnull=True).exists():  # uno a medias: puede haber salido el dinero
        return _fallo(devolucion, EN_CURSO)
    partes = _repartir(devolucion)
    if partes is None:
        return _fallo(devolucion, 'Los pagos de estos videos no alcanzan o no tienen datos para devolver por Transbank.')
    for token_ws, monto in partes:
        try:
            with transaction.atomic():  # punto de guardado: un choque de unicidad no rompe la transaccion de afuera
                reembolso = ReembolsoTransbank.objects.create(devolucion=devolucion, token_ws=token_ws, monto=monto)
        except IntegrityError:
            return _fallo(devolucion, EN_CURSO)  # otro intento se nos adelanto
        try:
            respuesta = _pedir(token_ws, monto)
        except Exception as error:  # rechazo de Transbank, red o credenciales: cualquiera cae al camino manual
            reembolso.delete()
            logger.warning('Reembolso rechazado (devolucion %s): %s', devolucion.pk, error)
            return _fallo(devolucion, f'Transbank no pudo devolver: {error}')
        reembolso.tipo = respuesta.get('type', '')
        reembolso.codigo_autorizacion = respuesta.get('authorization_code', '')
        reembolso.confirmado = timezone.now()
        reembolso.save(update_fields=['tipo', 'codigo_autorizacion', 'confirmado'])
    devolucion.refresh_from_db()
    if devolucion.por_devolver:
        return _fallo(devolucion, 'Transbank devolvió solo una parte.')
    devolucion.devuelta = timezone.now()
    devolucion.error_reembolso = ''
    devolucion.save(update_fields=['devuelta', 'error_reembolso'])
    return True
