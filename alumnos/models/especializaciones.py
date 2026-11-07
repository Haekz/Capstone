"""Especializaciones del profesor (fase 2 del flujo de especialidades, 06-nov).

El profesor sube un certificado (diplomado, postitulo, magister, curso) y propone asignaturas del
catalogo. Soporte revisa cada una por separado en el ticket de especializaciones del profesor.
El documento se guarda cifrado, como el titulo, y se borra al decidir.
"""

from django.db import models

from .clases import Asignatura
from .usuarios import Profesor


class Especializacion(models.Model):
    EN_REVISION = 'en_revision'
    APROBADA = 'aprobada'
    RECHAZADA = 'rechazada'
    ESTADOS = [(EN_REVISION, 'En revisión'), (APROBADA, 'Aprobada'), (RECHAZADA, 'Rechazada')]
    MAX_EN_REVISION = 5  # para subir mas, soporte debe decidir las que ya estan (decidido 06-nov)

    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE, related_name='especializaciones')
    nombre = models.CharField(max_length=120)  # ej. "Diplomado en Geometria, U. de Chile"
    propuestas = models.ManyToManyField(Asignatura, related_name='+')  # las que el profesor cree poder dictar
    contenido = models.BinaryField(null=True, blank=True)  # cifrado; None al decidir
    formato = models.CharField(max_length=4, blank=True)  # JPEG, PNG o PDF
    estado = models.CharField(max_length=12, choices=ESTADOS, default=EN_REVISION)
    observacion = models.CharField(max_length=200, blank=True)  # motivo del rechazo
    subida = models.DateTimeField(auto_now_add=True)
    revisada = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-subida', '-id']
        verbose_name = 'especialización'
        verbose_name_plural = 'especializaciones'

    def __str__(self):
        return f'{self.nombre} ({self.get_estado_display()})'
