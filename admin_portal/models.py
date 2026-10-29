"""Mensajes del formulario de contacto del sitio publico (alumnos/contactos)."""

from django.db import models


class MensajeContacto(models.Model):
    nombre = models.CharField(max_length=120)
    correo = models.EmailField()
    mensaje = models.TextField(max_length=2000)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'{self.nombre} <{self.correo}>'
