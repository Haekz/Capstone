"""Crea y quita los bloques de la agenda semanal (paso B1b, decidido 02-nov).

- 60 min, 1 alumno, proximas 4 semanas, un bloque por asignatura del profesor:
  el alumno elige cual y B1a impide que reserven dos a la misma hora.
- Idempotente: lo que ya existe no se duplica y un bloque cancelado no vuelve.
- Solo profesores habilitados (titulo aprobado): el resto no puede hacer clases.
"""

from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from alumnos.models import Clase, SesionClase

from .models import BloqueAgenda

SEMANAS = 4
DURACION = timedelta(minutes=60)


def _inicios(franja, desde, hasta):
    """Inicio de cada bloque de la franja dentro de (desde, hasta], en hora de Chile."""
    primer_dia = timezone.localdate(desde)
    for n in range(SEMANAS * 7 + 1):
        dia = primer_dia + timedelta(days=n)
        if dia.weekday() != franja.dia_semana:
            continue
        inicio, fin = datetime.combine(dia, franja.hora_inicio), datetime.combine(dia, franja.hora_fin)
        while inicio + DURACION <= fin:
            aware = timezone.make_aware(inicio)
            if desde < aware <= hasta:
                yield aware
            inicio += DURACION


def generar(profesor, ahora=None):
    """Crea los bloques que faltan en las proximas 4 semanas. Devuelve cuantos creo."""
    if not profesor.puede_hacer_clases:
        return 0
    ahora = ahora or timezone.now()
    hasta = ahora + timedelta(weeks=SEMANAS)
    clases = list(Clase.objects.filter(profesor=profesor))
    existentes = set(SesionClase.objects.filter(
        clase__in=clases, fecha_hora_inicio__gt=ahora, fecha_hora_inicio__lte=hasta,
    ).values_list('clase_id', 'fecha_hora_inicio'))  # incluye las canceladas: no vuelven
    nuevos = [(franja, clase, inicio)
              for franja in profesor.horario_semanal.all()
              for inicio in _inicios(franja, ahora, hasta)
              for clase in clases if (clase.pk, inicio) not in existentes]
    with transaction.atomic():
        sesiones = SesionClase.objects.bulk_create([
            SesionClase(clase=clase, fecha_hora_inicio=inicio, fecha_hora_fin=inicio + DURACION, cupo_maximo=1)
            for _, clase, inicio in nuevos
        ])
        BloqueAgenda.objects.bulk_create([BloqueAgenda(sesion=sesion, horario=franja)
                                          for sesion, (franja, _, _) in zip(sesiones, nuevos)])
    return len(nuevos)


def quitar_franja(franja, ahora=None):
    """Borra la franja y sus bloques futuros sin reservas.

    Los que tienen historial (reservas o cancelaciones, que pueden pagarse) se
    quedan: si hay alumnos, el profesor debe cancelar esas clases (paso A3).
    """
    ahora = ahora or timezone.now()
    with transaction.atomic():
        SesionClase.objects.filter(
            bloque_agenda__horario=franja, fecha_hora_inicio__gt=ahora, inscripciones__isnull=True,
        ).delete()
        franja.delete()
