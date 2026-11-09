"""Videos que el profesor le compartió a un alumno (agregado de videos, fase 3).

El archivo vive en MongoDB (GridFS, ver user_profesor/videoteca.py); aquí solo queda quién lo recibe y cuándo.
Cuelga del paquete: cuando el paquete vence, el alumno deja de verlos. Si el alumno es menor, ademas su apoderado
tiene que habilitar cada video. Si soporte retira uno por un reclamo (fase 5), deja de verse, de pagarse y de ocupar
cupo: por eso casi todo usa entregados(). La regla de no repetir un video al mismo alumno cuenta tambien los retirados.
"""

from django.db import models

from .pagos import PaqueteClases


class VideoCompartidoQuerySet(models.QuerySet):
    def entregados(self):
        """Los que siguen valiendo: sin los que soporte retiro."""
        return self.filter(retirado__isnull=True)


class VideoCompartido(models.Model):
    paquete = models.ForeignKey(PaqueteClases, on_delete=models.CASCADE, related_name='videos_compartidos')
    video_id = models.CharField(max_length=24)  # ObjectId del archivo en GridFS
    compartido = models.DateTimeField(auto_now_add=True)
    # Menores: el apoderado revisa cada video y recien ahi lo habilita (decidido 09-nov). Vacio = aun no.
    habilitado_menor = models.DateTimeField(null=True, blank=True)
    # Soporte lo retiro por un reclamo (no era de la materia o era inapropiado; decidido 09-nov). Vacio = vale.
    retirado = models.DateTimeField(null=True, blank=True)

    objects = VideoCompartidoQuerySet.as_manager()

    class Meta:
        ordering = ['-compartido', '-id']
        constraints = [models.UniqueConstraint(fields=['paquete', 'video_id'], name='video_unico_por_paquete')]

    def __str__(self):
        return f'{self.video_id} -> {self.paquete}'
