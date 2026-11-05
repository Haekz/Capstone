"""Datos propios del panel del admin."""

from django.db import models

from alumnos.models import CustomUser, Profesor


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


class AccesoTitulo(models.Model):
    """Cada vez que un agente de soporte abre un titulo (como AccesoDocumento en apoderados).

    Queda aunque el titulo se borre al decidir: sirve para ver quien abrio que, aunque nada se filtre.
    """
    agente = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='+')
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE, related_name='accesos_al_titulo')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'acceso a un título'
        verbose_name_plural = 'accesos a títulos'
        ordering = ['-fecha', '-id']


class MensajeContacto(models.Model):
    """Mensajes del formulario de contacto del sitio publico (alumnos/contactos)."""
    nombre = models.CharField(max_length=120)
    correo = models.EmailField()
    mensaje = models.TextField(max_length=2000)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'{self.nombre} <{self.correo}>'
