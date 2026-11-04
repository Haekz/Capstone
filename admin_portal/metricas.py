"""Cifras reales del panel del admin (paso 8).

Siguen docs/POLITICA_PAQUETES.md: lo cobrado por clases que aun no se dictan es
una obligacion, no un ingreso, y no pasa a ser ganancia al vencer el paquete.
LBWUS gana su comision solo por las clases ya dictadas: es la misma cuenta que
el saldo del profesor (user_profesor.saldos), vista desde LBWUS.

Tambien arma el grafico de registros nuevos por mes (antes, puntos fijos de Feb a Jun),
el de personas que entran por dia (promedio en meses y trimestres),
la pagina de planes (antes, tres planes por nivel que no existen) y las cifras de
soporte (P13: cuantos tickets y en cuanto tiempo, nunca su contenido).
"""

from collections import Counter
from datetime import date, datetime, time, timedelta

from django.db.models import Sum
from django.utils import timezone

from alumnos import paquetes
from alumnos.models import Alumno, Inscripcion, PaqueteClases, Profesor, SolicitudRetiro, Suscripcion
from soporte.models import Ticket
from user_profesor.saldos import saldos_de  # el mismo saldo que ve cada profesor

from .models import IngresoDiario

MESES = ('Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic')
PUNTOS_GRAFICO = 5
# Cortes del grafico de registros (H9): clave de la URL -> nombre en plural para el titulo.
PERIODOS = {'dia': 'días', 'mes': 'meses', 'trimestre': 'trimestres'}
# Geometria del SVG del panel (viewBox 600x220): X de 90 en pasos de 100; Y de 180 (cero) a 30 (tope).
X0, PASO_X, Y0, ALTO = 90, 100, 180, 150


def _suma(consulta):
    return consulta.aggregate(total=Sum('monto'))['total'] or 0


def finanzas():
    """Montos en pesos para las tarjetas de Finanzas (P12)."""
    # Pagos aprobados por Webpay. Las suscripciones ya no se venden, pero su dinero entro.
    paquetes_pagados = list(PaqueteClases.objects.filter(estado=PaqueteClases.ESTADO_ACTIVA)
                            .values_list('monto', flat=True))
    pagados = paquetes_pagados + list(Suscripcion.objects.filter(estado=Suscripcion.ESTADO_ACTIVA)
                                      .values_list('monto', flat=True))
    cobrado_paquetes = sum(paquetes_pagados)
    dictadas = list(Inscripcion.objects.pagables().select_related('paquete'))  # + canceladas tarde: se pagan
    dictado_de_paquetes = sum(paquetes.valor_clase(i) for i in dictadas if i.paquete_id)
    return {
        'cobrado': sum(pagados),
        # Si se dictara todo lo vendido; la ganancia real es solo la de lo ya dictado.
        'comision_estimada': sum(paquetes.comision(monto) for monto in pagados),
        'ganancia': sum(paquetes.comision(paquetes.valor_clase(i)) for i in dictadas),
        'por_dictar': max(0, cobrado_paquetes - dictado_de_paquetes),
        # Lo que los profesores ya pueden pedir (sin contar retiros en tramite).
        'saldo_profesores': sum(s['disponible'] for s in saldos_de(Profesor.objects.all()).values()),
        'retiros_pagados': _suma(SolicitudRetiro.objects.filter(estado=SolicitudRetiro.PAGADO)),
        # Pendientes de pagar: los que esperan revision y los aprobados sin transferir.
        'retiros_pendientes': _suma(SolicitudRetiro.objects.filter(
            estado__in=[SolicitudRetiro.PENDIENTE, SolicitudRetiro.APROBADO])),
    }


def _periodo(fecha, periodo):
    """Numero correlativo del dia, mes o trimestre de `fecha`: los consecutivos difieren en 1."""
    if periodo == 'dia':
        return fecha.toordinal()
    if periodo == 'mes':
        return fecha.year * 12 + fecha.month - 1
    return fecha.year * 4 + (fecha.month - 1) // 3


def _inicio(numero, periodo):
    """Primer dia del periodo `numero` (inversa de _periodo)."""
    if periodo == 'dia':
        return date.fromordinal(numero)
    if periodo == 'mes':
        anio, mes = divmod(numero, 12)
        return date(anio, mes + 1, 1)
    anio, trimestre = divmod(numero, 4)
    return date(anio, trimestre * 3 + 1, 1)


def _etiqueta(numero, periodo):
    """'03/02', 'Feb' o 'T1 26'."""
    inicio = _inicio(numero, periodo)
    if periodo == 'dia':
        return inicio.strftime('%d/%m')
    if periodo == 'mes':
        return MESES[inicio.month - 1]
    return f'T{numero % 4 + 1} {inicio:%y}'


def registros(periodo='mes', hoy=None, puntos=PUNTOS_GRAFICO):
    """[(etiqueta, cantidad)] de alumnos y profesores registrados por periodo; el ultimo es el de `hoy`."""
    hoy = hoy or timezone.localdate()
    actual = _periodo(hoy, periodo)
    numeros = range(actual - puntos + 1, actual + 1)
    desde = timezone.make_aware(datetime.combine(_inicio(numeros[0], periodo), time.min))
    conteo = Counter()
    for modelo in (Alumno, Profesor):
        for fecha in modelo.objects.filter(user__date_joined__gte=desde).values_list('user__date_joined', flat=True):
            conteo[_periodo(timezone.localdate(fecha), periodo)] += 1  # dia de Chile, no de UTC
    return [(_etiqueta(numero, periodo), conteo[numero]) for numero in numeros]


def personas(periodo='mes', hoy=None, puntos=PUNTOS_GRAFICO):
    """[(etiqueta, personas)] que iniciaron sesion por periodo (H8 + H9, decidido 02-nov).

    Por dia, las personas distintas de ese dia (todos los roles). Por mes o trimestre, el
    promedio por dia: sumar los dias contaria varias veces a quien entra seguido. Solo cuentan
    los dias desde el primer registro (antes no se contaba, no es que nadie entrara) y hasta hoy.
    """
    hoy = hoy or timezone.localdate()
    actual = _periodo(hoy, periodo)
    numeros = range(actual - puntos + 1, actual + 1)
    primero = IngresoDiario.objects.order_by('fecha').values_list('fecha', flat=True).first()
    por_periodo = Counter()
    for fecha, cantidad in IngresoDiario.objects.filter(fecha__gte=_inicio(numeros[0], periodo), fecha__lte=hoy) \
            .values_list('fecha', 'personas'):
        por_periodo[_periodo(fecha, periodo)] += cantidad
    serie = []
    for numero in numeros:
        desde = max(_inicio(numero, periodo), primero or hoy + timedelta(days=1))
        hasta = min(_inicio(numero + 1, periodo) - timedelta(days=1), hoy)
        dias = (hasta - desde).days + 1
        serie.append((_etiqueta(numero, periodo), round(por_periodo[numero] / dias) if dias > 0 else 0))
    return serie


def grafico(serie):
    """Coordenadas del SVG del panel para una serie de hasta PUNTOS_GRAFICO puntos."""
    tope = max(3, -(-max(c for _, c in serie) // 3) * 3)  # multiplo de 3: marcas enteras
    puntos = [{'etiqueta': etiqueta, 'cantidad': cantidad, 'x': X0 + i * PASO_X,
               'y': round(Y0 - cantidad * ALTO / tope, 1)} for i, (etiqueta, cantidad) in enumerate(serie)]
    linea = 'M ' + ' L '.join(f"{p['x']} {p['y']}" for p in puntos)
    return {
        'puntos': puntos,
        'marcas': [{'valor': tope * k // 3, 'y': Y0 - ALTO * k // 3} for k in (3, 2, 1, 0)],
        'linea': linea,
        'area': f"{linea} L {puntos[-1]['x']} {Y0} L {X0} {Y0} Z",
        'resumen': ', '.join(f'{etiqueta}: {cantidad}' for etiqueta, cantidad in serie),
    }


def planes():
    """Cada paquete con la tarifa base (alumnos/paquetes.py) y cuantos hay vigentes de el."""
    vigentes = Counter(PaqueteClases.objects.vigentes().values_list('plan', flat=True))
    return [(cotizacion, vigentes[cotizacion.plan.codigo])
            for cotizacion in paquetes.cotizar(paquetes.TARIFA_BASE)]


def _promedio(duraciones, unidad):
    """Promedio de timedeltas en `unidad` ('4,5', coma decimal chilena); None si no hay."""
    if not duraciones:
        return None
    return f'{sum(duraciones, timedelta()) / len(duraciones) / unidad:.1f}'.replace('.', ',')


def soporte(ahora=None):
    """Cifras de soporte para el admin (P13). Lee solo categoria, estado y fechas: ni titulo ni mensajes."""
    ahora = ahora or timezone.now()
    tickets = list(Ticket.objects.values('categoria', 'estado', 'creado', 'vence', 'respondido', 'cerrado'))
    for t in tickets:  # misma regla que Ticket.atrasado
        t['atrasado'] = t['estado'] == Ticket.ABIERTO and t['respondido'] is None and ahora > t['vence']
    por_categoria = []
    for codigo, nombre in Ticket.CATEGORIAS:
        suyos = [t for t in tickets if t['categoria'] == codigo]
        por_categoria.append({'nombre': nombre,
                              'abiertos': sum(t['estado'] == Ticket.ABIERTO for t in suyos),
                              'atrasados': sum(t['atrasado'] for t in suyos),
                              'cerrados': sum(t['estado'] == Ticket.CERRADO for t in suyos)})
    return {
        'por_categoria': por_categoria,
        'abiertos': sum(c['abiertos'] for c in por_categoria),
        'atrasados': sum(c['atrasados'] for c in por_categoria),
        # Solo los tickets de usuarios se responden; las verificaciones se cierran al decidir.
        'horas_respuesta': _promedio([t['respondido'] - t['creado'] for t in tickets if t['respondido']],
                                     timedelta(hours=1)),
        'dias_cierre': _promedio([t['cerrado'] - t['creado'] for t in tickets if t['cerrado']], timedelta(days=1)),
    }
