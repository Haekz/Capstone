"""Saldos de los profesores: lo ganado por clases dictadas y videos compartidos, menos los retiros.

Una sola cuenta para el panel del profesor y para las finanzas del admin. ``saldos_de`` calcula
varios profesores con 3 consultas en total (clases, videos y retiros), sin importar cuantos sean.
"""

from collections import defaultdict

from django.db.models import Sum

from alumnos import paquetes, videos_extra
from alumnos.models import Inscripcion, SolicitudRetiro, VideoCompartido


def _saldos(valores, videos, aprobados, pendientes):
    """La cuenta en si, a partir de lo pagado por cada clase y cada video y de los retiros ya sumados."""
    total_ganado = sum(valores) + sum(videos)
    corresponde_al_profesor = (sum(paquetes.pago_profesor(v) for v in valores)
                               + sum(paquetes.pago_profesor(v, paquetes.COMISION_VIDEOS) for v in videos))
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
    con menos de 4 h, la clase se le paga igual (02-nov). Los videos, cada vez que los comparte (punto 12):
    lo ya entregado se paga aunque despues venza el paquete. Si soporte retira uno, deja de contar; si ya lo
    habia cobrado, el saldo queda debiendo y se descuenta de lo proximo que gane (decidido 09-nov).
    """
    ids = [p.pk for p in profesores]
    valores = defaultdict(list)
    for inscripcion in (Inscripcion.objects.filter(clase__profesor_id__in=ids).pagables()
                        .select_related('paquete', 'clase')):
        valores[inscripcion.clase.profesor_id].append(paquetes.valor_clase(inscripcion))

    videos = defaultdict(list)  # el valor de cada video compartido: promedio de lo pagado (agregado + extra activos)
    compartidos = (VideoCompartido.objects.entregados().filter(paquete__profesor_id__in=ids)
                   .annotate(**videos_extra.anotar('paquete_id')))
    for profesor_id, monto, cantidad, extra_monto, extra_cantidad in compartidos.values_list(
            'paquete__profesor_id', 'paquete__monto_videos', 'paquete__videos', 'extra_monto', 'extra_videos'):
        videos[profesor_id].append(paquetes.valor_video(monto + extra_monto, cantidad + extra_cantidad))

    aprobados, pendientes = defaultdict(int), defaultdict(int)
    for fila in (SolicitudRetiro.objects.filter(profesor_id__in=ids)
                 .values('profesor_id', 'estado').annotate(total=Sum('monto'))):
        if fila['estado'] in (SolicitudRetiro.APROBADO, SolicitudRetiro.PAGADO):
            aprobados[fila['profesor_id']] += fila['total']
        elif fila['estado'] == SolicitudRetiro.PENDIENTE:
            pendientes[fila['profesor_id']] += fila['total']

    return {i: _saldos(valores[i], videos[i], aprobados[i], pendientes[i]) for i in ids}


def calcular_saldos(profesor):
    """Saldos de un profesor: {'total_ganado', 'disponible', 'pendiente'}. Sin inscripciones, todo en 0."""
    return saldos_de([profesor])[profesor.pk]
