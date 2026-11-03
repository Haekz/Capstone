"""Observaciones del profesor sobre una clase ya realizada (feedback docente de Mi Progreso).

Una por clase, escrita por el profesor de esa clase. La ve el alumno adulto en su Mi Progreso; la del menor la ve su
apoderado, no el menor: el profesor no tiene un canal propio hacia un menor sin supervision. Se borra con el alumno y,
pasados ``settings.OBSERVACIONES_MESES`` desde la clase, con el comando ``borrar_observaciones_vencidas``.
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

DIAS_POR_MES = 30.4375


def fecha_limite(ahora=None):
    """Las clases anteriores a esta fecha ya no admiten observacion y las que tenian se borran."""
    return (ahora or timezone.now()) - timedelta(days=round(DIAS_POR_MES * settings.OBSERVACIONES_MESES))


class ObservacionQuerySet(models.QuerySet):

    def vencidas(self, ahora=None):
        """Las de clases que ocurrieron hace mas de OBSERVACIONES_MESES: ya no sirven para orientar al alumno."""
        return self.filter(inscripcion__sesion__fecha_hora_inicio__lt=fecha_limite(ahora))

    def del_alumno(self, alumno):
        """Las vigentes que recibio ``alumno``, de la clase mas reciente a la mas antigua (una vencida que el cron
        aun no borro no se muestra)."""
        return (self.filter(inscripcion__alumno=alumno, inscripcion__sesion__fecha_hora_inicio__gte=fecha_limite())
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
