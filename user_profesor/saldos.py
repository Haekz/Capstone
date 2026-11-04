"""Saldos de los profesores: lo ganado por clases dictadas menos los retiros.

Una sola cuenta para el panel del profesor y para las finanzas del admin. ``saldos_de`` calcula
varios profesores con 3 consultas en total, sin importar cuantos sean (antes eran 3 por profesor).
"""

from collections import defaultdict

from django.db.models import Sum

from alumnos import paquetes
from alumnos.models import Inscripcion, SolicitudRetiro


def _saldos(valores, aprobados, pendientes):
    """La cuenta en si, a partir de lo pagado por cada clase y los retiros ya sumados."""
    total_ganado = sum(valores)
    corresponde_al_profesor = sum(paquetes.pago_profesor(v) for v in valores)
    return {
        'total_ganado': total_ganado,
        'disponible': max(0, corresponde_al_profesor - aprobados - pendientes),
        # La comision de la plataforma mas lo que aun esta en tramite.
        'pendiente': (total_ganado - corresponde_al_profesor) + pendientes,
    }


def saldos_de(profesores):
    """{id_profesor: saldos} de ``profesores`` (queryset o lista); quien no tiene movimientos queda en 0.

    Solo cuentan las clases ya dictadas: una reserva futura todavia se puede cancelar, y lo no
    realizado no se liquida (docs/POLITICA_PAQUETES.md, punto 10). Excepcion: si el alumno cancela
    con menos de 4 h, la clase se le paga igual (02-nov).
    """
    ids = [p.pk for p in profesores]
    valores = defaultdict(list)
    for inscripcion in (Inscripcion.objects.filter(clase__profesor_id__in=ids).pagables()
                        .select_related('paquete', 'clase')):
        valores[inscripcion.clase.profesor_id].append(paquetes.valor_clase(inscripcion))

    aprobados, pendientes = defaultdict(int), defaultdict(int)
    for fila in (SolicitudRetiro.objects.filter(profesor_id__in=ids)
                 .values('profesor_id', 'estado').annotate(total=Sum('monto'))):
        if fila['estado'] in (SolicitudRetiro.APROBADO, SolicitudRetiro.PAGADO):
            aprobados[fila['profesor_id']] += fila['total']
        elif fila['estado'] == SolicitudRetiro.PENDIENTE:
            pendientes[fila['profesor_id']] += fila['total']

    return {i: _saldos(valores[i], aprobados[i], pendientes[i]) for i in ids}


def calcular_saldos(profesor):
    """Saldos de un profesor: {'total_ganado', 'disponible', 'pendiente'}. Sin inscripciones, todo en 0."""
    return saldos_de([profesor])[profesor.pk]
