"""Reglas de los videos extra (fase 6, politica seccion 12): quien puede comprar, cuantos y a que precio.

Despues de contratar, cualquier paquete vigente al que le queden 14 dias o mas puede sumar hasta 6 videos extra
(en total, no por compra). Una compra pendiente ya cuenta para el tope; una rechazada no. El precio sale de
paquetes.precio_videos_extra. Solo reglas: el pago con Webpay va aparte.

Un extra solo cuenta para entregar, plazo y saldo cuando su pago esta confirmado (estado activa): anotar() y
contratados() son el unico lugar que lo calcula (fase 6d).
"""

from django.core.exceptions import ValidationError
from django.db.models import IntegerField, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from . import paquetes
from .models import PaqueteClases
from .models.videos import CompraVideosExtra


def anotar(paquete_ref='pk'):
    """Para ``.annotate(**anotar())``: extra_videos y extra_monto de las compras ACTIVAS del paquete, sin consultas
    extra por fila. ``paquete_ref``: como llega al paquete desde lo que se consulta ('paquete_id' desde un video)."""
    def suma(campo):
        activas = (CompraVideosExtra.objects.filter(paquete=OuterRef(paquete_ref), estado=CompraVideosExtra.ESTADO_ACTIVA)
                   .values('paquete').annotate(total=Sum(campo)).values('total'))
        return Coalesce(Subquery(activas, output_field=IntegerField()), 0)

    return {'extra_videos': suma('cantidad'), 'extra_monto': suma('monto')}


def contratados(paquete):
    """Videos que el profesor debe entregar en total: los del agregado y los extra ya pagados."""
    extra = paquete.compras_videos_extra.filter(estado=CompraVideosExtra.ESTADO_ACTIVA).aggregate(total=Sum('cantidad'))
    return paquete.videos + (extra['total'] or 0)


def comprados(paquete):
    """Extras ya comprados o en proceso de pago (los rechazados no cuentan)."""
    return (paquete.compras_videos_extra.exclude(estado=CompraVideosExtra.ESTADO_RECHAZADA)
            .aggregate(total=Sum('cantidad'))['total'] or 0)


def disponibles(paquete):
    """Cuantos mas puede comprar este paquete sin pasar el tope."""
    return max(0, paquetes.MAX_VIDEOS_EXTRA - comprados(paquete))


def ofertas(alumno_id, ahora=None):
    """Lo que el alumno puede comprar ahora, para la pantalla: por cada paquete vigente que cumple las reglas,
    [{'paquete': ..., 'opciones': [(cantidad, precio), ...], 'dias_entrega': ...}] desde 1 hasta lo que le queda bajo el tope.
    El precio es informativo: el que se cobra lo vuelve a calcular el servidor (webpay.iniciar_compra_videos_extra)."""
    ofertas = []
    for paquete in (PaqueteClases.objects.vigentes().filter(alumno_id=alumno_id)
                    .select_related('profesor__user').order_by('fecha_fin')):
        try:
            validar(paquete, 1, ahora)
        except ValidationError:
            continue
        ofertas.append({'paquete': paquete, 'dias_entrega': paquetes.DIAS_ENTREGA_EXTRA,
                        'opciones': [(n, paquetes.precio_videos_extra(n)) for n in range(1, disponibles(paquete) + 1)]})
    return ofertas


def validar(paquete, cantidad, ahora=None):
    """El precio de comprar ``cantidad`` extras para ``paquete``, o ValidationError con el motivo."""
    ahora = ahora or timezone.now()
    if paquete.estado != PaqueteClases.ESTADO_ACTIVA or not paquete.fecha_fin or paquete.fecha_fin <= ahora:
        raise ValidationError('Solo puedes comprar videos extra con un paquete vigente.')
    if (paquete.fecha_fin - ahora).days < paquetes.MIN_DIAS_PARA_EXTRA:
        raise ValidationError(f'Le deben quedar al menos {paquetes.MIN_DIAS_PARA_EXTRA} días al paquete para '
                              'comprar videos extra: tu profesor necesita tiempo para compartirlos.')
    precio = paquetes.precio_videos_extra(cantidad)  # ValidationError si no esta entre 1 y el maximo
    if cantidad > disponibles(paquete):
        raise ValidationError(f'Puedes tener máximo {paquetes.MAX_VIDEOS_EXTRA} videos extra por paquete; '
                              f'te quedan {disponibles(paquete)}.')
    return precio
