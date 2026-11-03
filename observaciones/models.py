"""Observaciones del profesor sobre una clase ya realizada (feedback docente de Mi Progreso).

Una por clase, escrita por el profesor de esa clase. La ve el alumno adulto en su Mi Progreso; la del menor la ve su
apoderado, no el menor: el profesor no tiene un canal propio hacia un menor sin supervision. Se borra con el alumno.
"""

from django.db import models


class ObservacionQuerySet(models.QuerySet):

    def del_alumno(self, alumno):
        """Las que recibio ``alumno``, de la clase mas reciente a la mas antigua."""
        return (self.filter(inscripcion__alumno=alumno)
                .select_related('inscripcion__clase__asignatura', 'inscripcion__clase__profesor__user',
                                'inscripcion__sesion')
                .order_by('-inscripcion__sesion__fecha_hora_inicio'))


class Observacion(models.Model):
    MAXIMO = 500

    inscripcion = models.OneToOneField('alumnos.Inscripcion', on_delete=models.CASCADE, related_name='observacion')
    texto = models.CharField(max_length=MAXIMO)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    objects = ObservacionQuerySet.as_manager()

    class Meta:
        verbose_name = 'observación'
        verbose_name_plural = 'observaciones'

    def __str__(self):
        return f'Observación de la inscripción {self.inscripcion_id}'
