"""Paquetes de clases: Flexible, Progreso e Intensivo (analisis de mercado 2.13-2.14, F-11).

Unica fuente de precios: la pagina de planes, el cobro en Webpay y el saldo del
profesor usan estas funciones. Los precios los fija LBWUS, iguales con todos los
profesores (decidido 14-nov-2026): $15.990 / $62.990 / $123.990.

Fracciones exactas: nada de floats con plata.
"""

from dataclasses import dataclass
from datetime import timedelta
from fractions import Fraction

from django.core.exceptions import ValidationError

TARIFA = 15990  # una clase suelta; los paquetes le aplican su descuento. El profesor no la elige.
DURACION_CLASE_MIN = 60
COMISION = Fraction(15, 100)  # la retiene LBWUS, IVA incluido
IVA = Fraction(19, 100)
REDONDEO_PAQUETE = 1000
TERMINACION = 990  # todo precio de paquete termina en $990
VALOR_INSCRIPCION = 15000  # inscripciones antiguas, sin paquete: valor fijo por clase (historico, no cambia)

# Agregado de videos (decidido 08-nov-2026): precio fijo, igual con todos los profesores.
PRECIO_VIDEO = 5000
PROMO_VIDEOS_CANTIDAD = 3
PROMO_VIDEOS_PRECIO = 13500  # 3 videos extra con 10% de descuento
MAX_VIDEOS_EXTRA = 6  # comprados despues de contratar, por paquete
MIN_DIAS_PARA_EXTRA = 14  # al paquete deben quedarle al menos estos dias para comprar extras
DIAS_ENTREGA_EXTRA = 14  # el profesor los comparte dentro de estos dias desde cada compra
COMISION_VIDEOS = Fraction(25, 100)  # LBWUS aloja los videos; IVA incluido


@dataclass(frozen=True)
class Plan:
    codigo: str
    nombre: str
    clases: int
    descuento: Fraction  # sobre la tarifa por clase
    vigencia_dias: int
    entregas: tuple  # agregado de videos: ((dia limite desde la compra, videos), ...)

    @property
    def videos(self):
        return sum(cantidad for _, cantidad in self.entregas)


# Vigencias (decidido 14-nov-2026): 1 y 4 clases, 1 mes; 8 clases, 2 meses.
# Entregas de videos: la ultima, 7 dias antes de que venza el paquete (09-nov), para que un atraso alcance a corregirse.
PLANES = (
    Plan('flexible', 'Flexible', 1, Fraction(0), 30, ((14, 1),)),
    Plan('progreso', 'Progreso', 4, Fraction(1, 60), 30, ((15, 2), (23, 2))),                # 1,7% por clase
    Plan('intensivo', 'Intensivo', 8, Fraction(1, 30), 60, ((20, 2), (40, 2), (53, 2))),     # 3,3% por clase
)
POR_CODIGO = {plan.codigo: plan for plan in PLANES}
CHOICES = [(plan.codigo, plan.nombre) for plan in PLANES]

# Lo ya vendido no cambia (14-nov): un paquete conserva la duracion con que se compro, y con ella su calendario.
# {(plan, vigencia en dias): entregas} de las vigencias que ya no se venden. Historico: no se toca.
ENTREGAS_ANTERIORES = {
    ('progreso', 60): ((30, 2), (53, 2)),
    ('intensivo', 90): ((30, 2), (60, 2), (83, 2)),
}


def _redondear(valor, paso=1):
    """Al multiplo de `paso` mas cercano; las mitades suben."""
    return int(Fraction(valor) / paso + Fraction(1, 2)) * paso


def precio(plan):
    """Precio del paquete: clases x TARIFA con el descuento, al numero terminado en $990 mas cercano."""
    ajuste = REDONDEO_PAQUETE - TERMINACION
    return _redondear(plan.clases * TARIFA * (1 - plan.descuento) + ajuste, REDONDEO_PAQUETE) - ajuste


def comision(monto, tasa=COMISION):
    """Parte de LBWUS (IVA incluido) de un monto pagado: 15% en clases, COMISION_VIDEOS en videos."""
    return _redondear(monto * tasa)


def iva_incluido(monto):
    """IVA contenido en un monto que ya lo incluye."""
    return _redondear(monto * IVA / (1 + IVA))


def pago_profesor(monto, tasa=COMISION):
    """Lo que le queda al profesor de un monto pagado (85% en clases)."""
    return monto - comision(monto, tasa)


def precio_agregado(plan):
    """Videos que trae el plan al contratarlo, a precio fijo por video."""
    return plan.videos * PRECIO_VIDEO


def valor_video(monto_videos, videos):
    """Lo pagado por cada video: el monto (del agregado mas los extra pagados) se reparte en partes iguales. Al
    profesor le queda pago_profesor(valor, COMISION_VIDEOS), y solo cuando lo comparte (seccion 12 de la politica)."""
    return monto_videos // videos if videos else 0


def fechas_entrega(plan, inicio, vigencia_dias=None):
    """Fechas limite del profesor para compartir videos: [(fecha, videos acumulados que debe haber entregado)].

    `vigencia_dias` es la duracion del paquete (PaqueteClases.dias): si es una de las que ya no se venden, rige su
    calendario de entonces; con cualquier otra, o sin decirla, el del plan.
    """
    entregas = ENTREGAS_ANTERIORES.get((plan.codigo, vigencia_dias), plan.entregas)
    fechas, acumulado = [], 0
    for dias, cantidad in entregas:
        acumulado += cantidad
        fechas.append((inicio + timedelta(days=dias), acumulado))
    return fechas


def precio_videos_extra(cantidad):
    """Videos comprados despues de contratar: cada grupo de 3 va con la promocion."""
    if not 1 <= cantidad <= MAX_VIDEOS_EXTRA:
        raise ValidationError(f'Se pueden comprar entre 1 y {MAX_VIDEOS_EXTRA} videos extra.')
    promociones, sueltos = divmod(cantidad, PROMO_VIDEOS_CANTIDAD)
    return promociones * PROMO_VIDEOS_PRECIO + sueltos * PRECIO_VIDEO


def valor_clase(inscripcion):
    """Lo que pago el alumno por esa clase: su parte del paquete, o el valor fijo si no tiene."""
    return inscripcion.paquete.precio_por_clase if inscripcion.paquete_id else VALOR_INSCRIPCION


@dataclass(frozen=True)
class Cotizacion:
    """Un plan con su precio, listo para mostrar."""
    plan: Plan
    tarifa = TARIFA

    @property
    def precio(self):
        return precio(self.plan)

    @property
    def precio_por_clase(self):
        # Hacia abajo, igual que PaqueteClases.precio_por_clase: $62.990 / 4 = $15.747 (sobran $2 del paquete)
        return self.precio // self.plan.clases

    @property
    def descuento_por_clase(self):
        return self.tarifa - self.precio_por_clase

    @property
    def descuento_pct(self):
        """'1,7' (coma decimal chilena, sin depender del idioma de Django)."""
        pct = Fraction(self.descuento_por_clase * 100, self.tarifa)
        return f'{float(pct):.1f}'.replace('.', ',')

    @property
    def ahorro_total(self):
        return self.plan.clases * self.tarifa - self.precio

    @property
    def comision(self):
        return comision(self.precio)

    @property
    def iva_comision(self):
        return iva_incluido(self.comision)

    @property
    def pago_profesor(self):
        return pago_profesor(self.precio)

    @property
    def precio_videos(self):
        return precio_agregado(self.plan)


def cotizar():
    return [Cotizacion(plan) for plan in PLANES]
