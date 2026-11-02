"""Cifras reales del panel del admin (paso 8).

Siguen docs/POLITICA_PAQUETES.md: lo cobrado por clases que aun no se dictan es
una obligacion, no un ingreso, y no pasa a ser ganancia al vencer el paquete.
LBWUS gana su comision solo por las clases ya dictadas: es la misma cuenta que
el saldo del profesor (user_profesor.views.calcular_saldos), vista desde LBWUS.

Tambien arma el grafico de registros nuevos por mes (antes, puntos fijos de Feb a Jun)
y la pagina de planes (antes, tres planes por nivel que no existen).
"""

from collections import Counter
from datetime import datetime

from django.db.models import Sum
from django.utils import timezone

from alumnos import paquetes
from alumnos.models import Alumno, Inscripcion, PaqueteClases, Profesor, SolicitudRetiro, Suscripcion

MESES = ('Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic')
MESES_GRAFICO = 5
# Geometria del SVG del panel (viewBox 600x220): X de 90 en pasos de 100; Y de 180 (cero) a 30 (tope).
X0, PASO_X, Y0, ALTO = 90, 100, 180, 150


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


def registros_por_mes(hoy=None, meses=MESES_GRAFICO):
    """[(mes, cantidad)] de alumnos y profesores registrados; el ultimo es el mes de `hoy`."""
    hoy = hoy or timezone.localdate()
    actual = hoy.year * 12 + hoy.month - 1
    periodos = [divmod(i, 12) for i in range(actual - meses + 1, actual + 1)]  # (anio, mes desde 0)
    anio, mes = periodos[0]
    desde = timezone.make_aware(datetime(anio, mes + 1, 1))
    conteo = Counter()
    for modelo in (Alumno, Profesor):
        for fecha in modelo.objects.filter(user__date_joined__gte=desde).values_list('user__date_joined', flat=True):
            local = timezone.localtime(fecha)
            conteo[local.year, local.month - 1] += 1
    return [(MESES[mes], conteo[anio, mes]) for anio, mes in periodos]


def grafico(serie):
    """Coordenadas del SVG del panel para una serie de hasta MESES_GRAFICO puntos."""
    tope = max(3, -(-max(c for _, c in serie) // 3) * 3)  # multiplo de 3: marcas enteras
    puntos = [{'mes': mes, 'cantidad': cantidad, 'x': X0 + i * PASO_X,
               'y': round(Y0 - cantidad * ALTO / tope, 1)} for i, (mes, cantidad) in enumerate(serie)]
    linea = 'M ' + ' L '.join(f"{p['x']} {p['y']}" for p in puntos)
    return {
        'puntos': puntos,
        'marcas': [{'valor': tope * k // 3, 'y': Y0 - ALTO * k // 3} for k in (3, 2, 1, 0)],
        'linea': linea,
        'area': f"{linea} L {puntos[-1]['x']} {Y0} L {X0} {Y0} Z",
        'resumen': ', '.join(f'{mes}: {cantidad}' for mes, cantidad in serie),
    }


def planes():
    """Cada paquete con la tarifa base (alumnos/paquetes.py) y cuantos hay vigentes de el."""
    vigentes = Counter(PaqueteClases.objects.vigentes().values_list('plan', flat=True))
    return [(cotizacion, vigentes[cotizacion.plan.codigo])
            for cotizacion in paquetes.cotizar(paquetes.TARIFA_BASE)]
