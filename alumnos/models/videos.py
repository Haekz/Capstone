"""Videos que el profesor le compartió a un alumno (agregado de videos, fase 3).

El archivo vive en MongoDB (GridFS, ver user_profesor/videoteca.py); aquí solo queda quién lo recibe y cuándo.
Cuelga del paquete: cuando el paquete vence, el alumno deja de verlos.
"""

from django.db import models

from .pagos import PaqueteClases


class VideoCompartido(models.Model):
    paquete = models.ForeignKey(PaqueteClases, on_delete=models.CASCADE, related_name='videos_compartidos')
    video_id = models.CharField(max_length=24)  # ObjectId del archivo en GridFS
    compartido = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-compartido', '-id']
        constraints = [models.UniqueConstraint(fields=['paquete', 'video_id'], name='video_unico_por_paquete')]

    def __str__(self):
        return f'{self.video_id} -> {self.paquete}'
