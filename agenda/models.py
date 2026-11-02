"""Horario semanal del profesor y los bloques que genera (paso B1b, decidido 02-nov).

El profesor dice "lunes de 15 a 19 h" y el sistema crea bloques de 60 min y
1 alumno para las proximas 4 semanas, uno por asignatura (agenda/bloques.py).
"""

from django.core.exceptions import ValidationError
from django.db import models

from alumnos.models import Profesor, SesionClase


class HorarioSemanal(models.Model):
    """Una franja del horario: un dia de la semana, de una hora en punto a otra."""

    DIAS = [(0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), (3, 'Jueves'),
            (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo')]

    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE, related_name='horario_semanal')
    dia_semana = models.PositiveSmallIntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        ordering = ['dia_semana', 'hora_inicio']
        verbose_name = 'Franja del horario semanal'
        verbose_name_plural = 'Horario semanal'
        constraints = [
            models.CheckConstraint(condition=models.Q(hora_fin__gt=models.F('hora_inicio')),
                                   name='horario_fin_posterior_a_inicio'),
        ]

    def __str__(self):
        return f'{self.get_dia_semana_display()} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}'

    def clean(self):
        super().clean()
        if self.hora_inicio is None or self.hora_fin is None:
            return
        if self.hora_inicio.minute or self.hora_fin.minute:
            raise ValidationError('Usa horas en punto (ej. 15:00): cada bloque dura 60 minutos.')
        if self.hora_fin <= self.hora_inicio:
            raise ValidationError('La hora de término debe ser posterior a la de inicio.')
        se_cruza = HorarioSemanal.objects.filter(
            profesor_id=self.profesor_id, dia_semana=self.dia_semana,
            hora_inicio__lt=self.hora_fin, hora_fin__gt=self.hora_inicio,
        ).exclude(pk=self.pk)
        if se_cruza.exists():
            raise ValidationError('Esa franja se cruza con otra del mismo día.')


class BloqueAgenda(models.Model):
    """Marca que una sesion salio de una franja: al quitar la franja se borran sus bloques libres.

    Sin tocar SesionClase: las sesiones de demo o del admin nunca se borran por aqui.
    """

    sesion = models.OneToOneField(SesionClase, on_delete=models.CASCADE, related_name='bloque_agenda')
    horario = models.ForeignKey(HorarioSemanal, on_delete=models.CASCADE, related_name='bloques')

    class Meta:
        verbose_name = 'Bloque de agenda'
        verbose_name_plural = 'Bloques de agenda'
