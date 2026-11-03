"""Solicitud de un usuario para eliminar su cuenta (respuesta legal del 02-nov, punto E3).

Es la constancia de la solicitud: cuando se pidio, quien la resolvio, cuando y con que resultado. Sobrevive al
borrado de la cuenta, por eso no guarda ningun dato personal: ni nombre, ni correo, ni RUT. El ticket de soporte
(categoria Privacidad) es la conversacion con el usuario y se borra junto con la cuenta si esta se elimina completa.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q


class SolicitudSupresion(models.Model):
    ABIERTA, EJECUTADA, RECHAZADA = 'abierta', 'ejecutada', 'rechazada'
    ESTADOS = [(ABIERTA, 'Abierta'), (EJECUTADA, 'Ejecutada'), (RECHAZADA, 'Rechazada o cerrada sin ejecutar')]
    BORRADA, SEUDONIMIZADA = 'borrada', 'seudonimizada'
    RESULTADOS = [(BORRADA, 'Cuenta borrada'), (SEUDONIMIZADA, 'Cuenta seudonimizada')]

    # SET_NULL: si la cuenta se borra completa, la solicitud queda como registro, sin a quien pertenecia.
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    rol = models.CharField(max_length=12)  # alumno, profesor o apoderado, al pedirla
    ticket = models.OneToOneField('soporte.Ticket', on_delete=models.SET_NULL, null=True,
                                  related_name='solicitud_supresion')
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ABIERTA)
    creada = models.DateTimeField(auto_now_add=True)
    resuelta = models.DateTimeField(null=True, blank=True)
    resuelta_por = models.ForeignKey('soporte.AgenteSoporte', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+')
    resultado = models.CharField(max_length=15, choices=RESULTADOS, blank=True)
    motivo_rechazo = models.TextField(blank=True)

    class Meta:
        verbose_name = 'solicitud de eliminacion de cuenta'
        verbose_name_plural = 'solicitudes de eliminacion de cuenta'
        ordering = ['-creada', '-pk']
        constraints = [models.UniqueConstraint(fields=['usuario'], condition=Q(estado='abierta'),
                                               name='una_solicitud_abierta_por_usuario')]

    def __str__(self):
        return f'Solicitud #{self.pk} ({self.get_estado_display()})'
