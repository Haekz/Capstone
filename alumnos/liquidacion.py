"""Ciclo de pago a profesores (paso 4; decisiones N1 y F1 a F5).

El profesor elige cobrar semanal (corte el viernes) o mensual (corte el ultimo
viernes del mes), pide el pago y se le paga el lunes siguiente al corte; si ese
lunes no es habil, el siguiente dia habil. Un cambio de frecuencia rige desde el
ciclo siguiente, nunca a mitad de uno. Bajo el minimo no se puede retirar: el
saldo se acumula hasta alcanzarlo.
"""

from datetime import date, timedelta

from django.core.exceptions import ValidationError

from soporte.plazos import es_habil

MINIMO = 10000
VIERNES = 4
SEMANAL, MENSUAL = 'semanal', 'mensual'
FRECUENCIAS = [(SEMANAL, 'Semanal'), (MENSUAL, 'Mensual')]


def _ultimo_viernes(anio, mes):
    ultimo_dia = date(anio + mes // 12, mes % 12 + 1, 1) - timedelta(days=1)
    return ultimo_dia - timedelta(days=(ultimo_dia.weekday() - VIERNES) % 7)


def proximo_corte(hoy, frecuencia):
    """Viernes de corte del ciclo en curso; hoy mismo si hoy es el dia de corte."""
    if frecuencia == SEMANAL:
        return hoy + timedelta(days=(VIERNES - hoy.weekday()) % 7)
    corte = _ultimo_viernes(hoy.year, hoy.month)
    return corte if corte >= hoy else _ultimo_viernes(hoy.year + hoy.month // 12, hoy.month % 12 + 1)


def dia_de_pago(corte):
    """Lunes siguiente al corte, o el siguiente dia habil si ese lunes es feriado."""
    dia = corte + timedelta(days=3)
    while not es_habil(dia):
        dia += timedelta(days=1)
    return dia


def frecuencia_vigente(profesor, hoy):
    if profesor.frecuencia_nueva and hoy >= profesor.frecuencia_nueva_desde:
        return profesor.frecuencia_nueva
    return profesor.frecuencia_pago


def proximo_pago(profesor, hoy):
    """Dia en que se pagaria un retiro pedido hoy."""
    return dia_de_pago(proximo_corte(hoy, frecuencia_vigente(profesor, hoy)))


def cambiar_frecuencia(profesor, nueva, hoy):
    """Programa ``nueva`` desde el ciclo siguiente y devuelve desde cuando rige.

    Devuelve None si ``nueva`` ya es la vigente (y anula un cambio pendiente).
    """
    if nueva not in dict(FRECUENCIAS):
        raise ValidationError('Elige pago semanal o mensual.')
    actual = frecuencia_vigente(profesor, hoy)
    profesor.frecuencia_pago = actual
    if nueva == actual:
        profesor.frecuencia_nueva, profesor.frecuencia_nueva_desde = '', None
    else:
        profesor.frecuencia_nueva = nueva
        profesor.frecuencia_nueva_desde = proximo_corte(hoy, actual) + timedelta(days=1)
    profesor.save(update_fields=['frecuencia_pago', 'frecuencia_nueva', 'frecuencia_nueva_desde'])
    return profesor.frecuencia_nueva_desde
