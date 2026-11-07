"""Asignaturas que soporte le asigna al profesor al aprobar su titulo o una especializacion (fase 3, 06-nov).

Asignar = crear su Clase de esa asignatura, online (la cambiara el profesor en la fase 6). La hora es la de
cada bloque de su agenda. Si ya la tiene, no se duplica. Solo del catalogo:
las asignaturas nuevas las crea el admin (fase 4).
"""

from django.core.exceptions import ValidationError

from agenda import bloques
from alumnos.models import Asignatura, Clase


def del_catalogo(ids, obligatoria):
    """Las del catalogo que se eligieron. Un id ajeno al catalogo (o manipulado) rechaza todo."""
    ids = set(ids)
    asignaturas = list(Asignatura.objects.filter(pk__in=[i for i in ids if str(i).isdecimal()]))
    if len(asignaturas) != len(ids) or (obligatoria and not asignaturas):
        raise ValidationError('Elige al menos una asignatura de la lista.' if obligatoria
                              else 'Elige asignaturas de la lista.')
    return asignaturas


def asignar(profesor, asignaturas):
    """Crea las clases que le faltan y sus bloques en la agenda. Devuelve las nuevas.

    Llamar dentro de una transaccion con el profesor bloqueado: dos aprobaciones a la vez no duplican.
    """
    tiene = set(Clase.objects.filter(profesor=profesor).values_list('asignatura_id', flat=True))
    nuevas = Clase.objects.bulk_create([Clase(profesor=profesor, asignatura=a, modalidad='online')
                                        for a in asignaturas if a.pk not in tiene])
    if nuevas:
        bloques.generar(profesor)  # sin esto la clase no aparece en el catalogo hasta el proximo cron
    return nuevas
