"""Quien acepto los Terminos y la Politica de privacidad, que version y cuando: la prueba de la aceptacion al comprar."""

from django.conf import settings
from django.db import models


class AceptacionLegal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='aceptaciones_legales')
    version = models.CharField(max_length=40)  # fecha de actualizacion de los textos (alumnos/aceptacion.py)
    aceptada = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'version'], name='una_aceptacion_por_version')]
