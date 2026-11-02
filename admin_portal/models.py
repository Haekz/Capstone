"""Datos propios del panel del admin."""

from django.db import models

from alumnos.models import CustomUser


class IngresoDiario(models.Model):
    """Cuantas personas distintas de un rol iniciaron sesion ese dia (H8).

    Solo el numero: no guarda quien entro (admin_portal/ingresos.py).
    """
    fecha = models.DateField()
    rol = models.CharField(max_length=15, choices=CustomUser.ROLES)
    personas = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['fecha', 'rol'], name='ingreso_unico_por_dia_y_rol')]
        ordering = ['fecha', 'rol']

    def __str__(self):
        return f'{self.fecha} {self.rol}: {self.personas}'
