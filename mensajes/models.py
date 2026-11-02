"""Mensajes entre alumno y profesor (paso C1a, decidido 02-nov).

Una conversacion por alumno, profesor y `cliente`: quien habla por el lado del alumno.
Hoy es el propio alumno adulto; en C2 sera cada apoderado, por el menor (que nunca escribe).
El estado de la conversacion (reportada, retencion) y la lectura llegan en C1b-C1d.
"""

from django.conf import settings
from django.db import models

from alumnos.models import Alumno, Profesor

LARGO_MAX = 1000


class Conversacion(models.Model):
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='conversaciones')
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE, related_name='conversaciones')
    cliente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Conversacion'
        verbose_name_plural = 'Conversaciones'
        constraints = [models.UniqueConstraint(fields=['alumno', 'profesor', 'cliente'], name='conversacion_unica')]

    def __str__(self):
        return f'{self.alumno.user.first_name} - {self.profesor.user.first_name}'

    def es_participante(self, user):
        return user.pk in (self.cliente_id, self.profesor.user_id)


class Mensaje(models.Model):
    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name='mensajes')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    texto = models.CharField(max_length=LARGO_MAX)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['creado', 'pk']
        indexes = [models.Index(fields=['conversacion', 'creado'])]

    def __str__(self):
        return self.texto[:40]
