"""Notificaciones en la plataforma (la campanita del menu). Paso B2a, decidido 02-nov.

Privacidad: el texto lo arma el sistema, nunca el usuario, y solo lleva lo
necesario (asignatura, fecha, nombre de pila). Nada de RUT, correo ni telefono.
"""

from django.conf import settings
from django.db import models

LARGO_TEXTO = 200


class Notificacion(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificaciones')
    texto = models.CharField(max_length=LARGO_TEXTO)
    enlace = models.CharField(max_length=200, blank=True)  # ruta interna, ej. el panel
    creada = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

    class Meta:
        ordering = ['-creada']
        indexes = [models.Index(fields=['usuario', 'leida'])]
        verbose_name = 'Notificacion'
        verbose_name_plural = 'Notificaciones'

    def __str__(self):
        return self.texto


def notificar(usuario, texto, enlace=''):
    """Deja una notificacion en la campanita del usuario. Unico punto de creacion."""
    return Notificacion.objects.create(usuario=usuario, texto=texto[:LARGO_TEXTO], enlace=enlace)
