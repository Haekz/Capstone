"""Ciclo de pago a profesores (paso 4; decisiones N1 y F1 a F5).

El profesor pide el pago y se le paga el lunes siguiente al corte de su ciclo
(corte semanal: el viernes). Si ese lunes no es habil, el siguiente dia habil.
Bajo el minimo no se puede retirar: el saldo se acumula hasta alcanzarlo.
"""

from datetime import timedelta

from soporte.plazos import es_habil

MINIMO = 10000
VIERNES = 4


def proximo_corte(hoy):
    """Viernes de corte del ciclo en curso; hoy mismo si hoy es viernes."""
    return hoy + timedelta(days=(VIERNES - hoy.weekday()) % 7)


def dia_de_pago(corte):
    """Lunes siguiente al corte, o el siguiente dia habil si ese lunes es feriado."""
    dia = corte + timedelta(days=3)
    while not es_habil(dia):
        dia += timedelta(days=1)
    return dia
