"""Agregar una franja al horario y describirla. Lo usan el profesor (Mi Agenda) y el agente de soporte
asignado a su ticket de Horario (fase 7): las mismas reglas para los dos."""

from datetime import time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from alumnos.models import Clase, Profesor

from . import bloques
from .models import HorarioSemanal


def agregar(profesor, datos):
    """Valida y guarda la franja de ``datos`` (dia_semana, hora_inicio, hora_fin y clase, vacia = todas sus
    materias). Devuelve (franja, bloques nuevos), o None en bloques si aun no puede hacer clases.
    Lanza ValidationError; una materia ajena, 404."""
    with transaction.atomic():
        Profesor.objects.select_for_update().get(pk=profesor.pk)
        try:
            clase = None
            if datos.get('clase'):
                clase = get_object_or_404(Clase, pk=int(datos['clase']), profesor=profesor)  # solo las propias
            franja = HorarioSemanal(profesor=profesor, clase=clase, dia_semana=int(datos.get('dia_semana', '')),
                                    hora_inicio=time.fromisoformat(datos.get('hora_inicio', '')),
                                    hora_fin=time.fromisoformat(datos.get('hora_fin', '')))
        except ValueError:
            raise ValidationError('Elige el d\u00eda y las horas de la franja.') from None
        franja.full_clean()
        franja.save()
        generados = bloques.generar(profesor) if profesor.puede_hacer_clases else None
    return franja, generados


def descripcion(franja):
    """'lunes de 15:00 a 17:00, Algebra' (o 'todas tus materias'), para el mensaje al profesor."""
    materia = franja.clase.asignatura.nombre if franja.clase_id else 'todas tus materias'
    return (f'{franja.get_dia_semana_display().lower()} de {franja.hora_inicio:%H:%M} a {franja.hora_fin:%H:%M}, '
            f'{materia}')
