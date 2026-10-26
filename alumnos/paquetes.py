"""Paquetes de clases: Flexible, Progreso e Intensivo (analisis de mercado 2.13-2.14, F-11).

Unica fuente de precios: la pagina de planes, el cobro en Webpay y el saldo del
profesor usan estas funciones. El precio depende de la tarifa por clase de
cada profesor; con la tarifa base ($15.000) da $15.000 / $59.000 / $116.000.

Fracciones exactas: nada de floats con plata.
"""

from dataclasses import dataclass
from fractions import Fraction

from django.core.exceptions import ValidationError

TARIFA_BASE = 15000
TARIFA_MIN = 10000
TARIFA_MAX = 50000
TARIFA_PASO = 1000
DURACION_CLASE_MIN = 60
COMISION = Fraction(15, 100)  # la retiene LBWUS, IVA incluido
IVA = Fraction(19, 100)
REDONDEO_PAQUETE = 1000


@dataclass(frozen=True)
class Plan:
    codigo: str
    nombre: str
    clases: int
    descuento: Fraction  # sobre la tarifa por clase
    vigencia_dias: int


PLANES = (
    Plan('flexible', 'Flexible', 1, Fraction(0), 30),
    Plan('progreso', 'Progreso', 4, Fraction(1, 60), 60),     # 1,7% por clase
    Plan('intensivo', 'Intensivo', 8, Fraction(1, 30), 90),   # 3,3% por clase
)
POR_CODIGO = {plan.codigo: plan for plan in PLANES}
CHOICES = [(plan.codigo, plan.nombre) for plan in PLANES]


def _redondear(valor, paso=1):
    """Al multiplo de `paso` mas cercano; las mitades suben."""
    return int(Fraction(valor) / paso + Fraction(1, 2)) * paso


def precio(plan, tarifa):
    """Precio del paquete: clases x tarifa con el descuento, redondeado a $1.000."""
    return _redondear(plan.clases * tarifa * (1 - plan.descuento), REDONDEO_PAQUETE)


def comision(monto):
    """Parte de LBWUS (15%, IVA incluido) de un monto pagado."""
    return _redondear(monto * COMISION)


def iva_incluido(monto):
    """IVA contenido en un monto que ya lo incluye."""
    return _redondear(monto * IVA / (1 + IVA))


def pago_profesor(monto):
    """Lo que le queda al profesor (85%) de un monto pagado."""
    return monto - comision(monto)


@dataclass(frozen=True)
class Cotizacion:
    """Un plan con el precio de un profesor, listo para mostrar."""
    plan: Plan
    tarifa: int

    @property
    def precio(self):
        return precio(self.plan, self.tarifa)

    @property
    def precio_por_clase(self):
        return self.precio // self.plan.clases  # exacto: multiplo de $1.000 entre 1, 4 u 8

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


def cotizar(tarifa):
    return [Cotizacion(plan, tarifa) for plan in PLANES]


def validar_tarifa(valor):
    """Tarifa por clase que define el profesor. Devuelve el entero o lanza ValidationError."""
    try:
        tarifa = int(str(valor).strip())
    except (TypeError, ValueError):
        raise ValidationError('La tarifa debe ser un número entero en pesos.')
    if not TARIFA_MIN <= tarifa <= TARIFA_MAX or tarifa % TARIFA_PASO:
        raise ValidationError(
            f'La tarifa debe estar entre ${TARIFA_MIN:,} y ${TARIFA_MAX:,}, '
            f'en múltiplos de ${TARIFA_PASO:,}.'.replace(',', '.')
        )
    return tarifa
