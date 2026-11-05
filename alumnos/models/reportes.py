"""Reportes del canal antiguo: solo lectura, los nuevos casos son tickets de soporte."""

from django.db import models
from django.conf import settings



class Reporte(models.Model):
    id_reporte = models.AutoField(primary_key=True)
    remitente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    descripcion = models.TextField()
    fecha_reporte = models.DateField(auto_now_add=True)
    estado = models.CharField(max_length=15, choices=[('pendiente', 'Pendiente'), ('resuelto', 'Resuelto')], default='pendiente')

    def __str__(self):
        return f"Reporte de {self.remitente.first_name}"
