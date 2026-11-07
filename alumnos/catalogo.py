"""Catalogo de asignaturas: lo administra el admin (fase 4, decidido 07-nov).

Crear y renombrar con nombres limpios y sin duplicados (sin distinguir mayusculas: la base si las distingue).
Eliminar solo si nadie la usa: Clase.asignatura es CASCADE, borrar una en uso borraria sus clases y reservas.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Asignatura, Clase, Especializacion

LARGO = Asignatura._meta.get_field('nombre').max_length
Propuesta = Especializacion.propuestas.through  # propuestas tiene related_name='+': se consulta por aqui


def _nombre_valido(nombre, salvo=None):
    """El nombre limpio (sin espacios de mas). Lanza ValidationError si esta vacio, es largo o ya existe."""
    nombre = ' '.join((nombre or '').split())
    if not nombre:
        raise ValidationError('Escribe el nombre de la asignatura.')
    if len(nombre) > LARGO:
        raise ValidationError(f'El nombre puede tener hasta {LARGO} caracteres.')
    if Asignatura.objects.filter(nombre__iexact=nombre).exclude(pk=getattr(salvo, 'pk', None)).exists():
        raise ValidationError(f'Ya existe la asignatura «{nombre}».')
    return nombre


def crear(nombre):
    return Asignatura.objects.create(nombre=_nombre_valido(nombre))


def renombrar(asignatura, nombre):
    asignatura.nombre = _nombre_valido(nombre, salvo=asignatura)
    asignatura.save(update_fields=['nombre'])
    return asignatura


def en_uso():
    """Ids de las asignaturas que alguien usa (una clase o una propuesta de especializacion)."""
    return (set(Clase.objects.values_list('asignatura_id', flat=True))
            | set(Propuesta.objects.values_list('asignatura_id', flat=True)))


def eliminar(asignatura):
    with transaction.atomic():
        Asignatura.objects.select_for_update().filter(pk=asignatura.pk).first()  # a la vez que una asignacion
        if (Clase.objects.filter(asignatura=asignatura).exists()
                or Propuesta.objects.filter(asignatura=asignatura).exists()):
            raise ValidationError(f'«{asignatura.nombre}» est\u00e1 en uso (clases o especializaciones): no se puede '
                                  'eliminar. Puedes renombrarla.')
        asignatura.delete()
