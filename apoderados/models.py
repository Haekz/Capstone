"""Fase 1a de menores: cuenta del apoderado y verificacion de su identidad.

Una cuenta verificada NO da permisos sobre estudiantes, salas ni el portal
admin: eso llega con el vinculo de cada menor (fase 1b). Minimizacion de
datos: no se guardan copias de documentos ni la IP; solo la evidencia de que
un administrador reviso la identidad, y que version de la declaracion se acepto.
"""

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class Apoderado(models.Model):
    CORREO_PENDIENTE = 'correo_pendiente'
    REVISION_PENDIENTE = 'revision_pendiente'
    VERIFICADO = 'verificado'
    RECHAZADO = 'rechazado'
    ESTADOS = [
        (CORREO_PENDIENTE, 'Correo por confirmar'),
        (REVISION_PENDIENTE, 'Identidad en revisión'),
        (VERIFICADO, 'Identidad verificada'),
        (RECHAZADO, 'Verificación rechazada'),
    ]

    id_apoderado = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='perfil_apoderado')
    estado = models.CharField(max_length=20, choices=ESTADOS, default=CORREO_PENDIENTE)
    correo_verificado = models.DateTimeField(null=True, blank=True)
    version_declaracion = models.CharField(max_length=10)
    declaracion_aceptada = models.DateTimeField()
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['creado']

    def __str__(self):
        return f'{self.nombre} ({self.get_estado_display()})'

    @property
    def nombre(self):
        return self.user.first_name

    @property
    def ultima_revision(self):
        return self.revisiones.first()

    def confirmar_correo(self):
        """Marca el correo como propio. El token deja de servir (un solo uso)."""
        if self.estado != self.CORREO_PENDIENTE:
            return
        self.correo_verificado = timezone.now()
        self.estado = self.REVISION_PENDIENTE
        self.save(update_fields=['correo_verificado', 'estado'])

    def aplicar_revision(self, revision, administrador):
        """Guarda la evidencia y el nuevo estado juntos: o quedan ambos o ninguno."""
        revision.apoderado = self
        revision.administrador = administrador
        self.estado = self.VERIFICADO if revision.decision == revision.APROBAR else self.RECHAZADO
        with transaction.atomic():
            revision.save()
            self.save(update_fields=['estado'])


class RevisionIdentidad(models.Model):
    """Evidencia de la revision de identidad. Nunca guarda el documento."""
    APROBAR = 'aprobar'
    RECHAZAR = 'rechazar'
    DECISIONES = [(APROBAR, 'Aprobar'), (RECHAZAR, 'Rechazar')]
    DOCUMENTOS = [('cedula', 'Cédula de identidad'), ('pasaporte', 'Pasaporte')]
    CANALES = [('presencial', 'Presencial'), ('videollamada', 'Videollamada')]

    apoderado = models.ForeignKey(Apoderado, on_delete=models.CASCADE, related_name='revisiones')
    # SET_NULL: si se borra la cuenta del admin, la evidencia sigue registrada.
    administrador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, related_name='revisiones_apoderados')
    decision = models.CharField(max_length=10, choices=DECISIONES)
    documento = models.CharField('documento revisado', max_length=10, choices=DOCUMENTOS, blank=True)
    canal = models.CharField(max_length=12, choices=CANALES, blank=True)
    rut_coincide = models.BooleanField('el RUT del documento coincide', default=False)
    observacion = models.CharField(max_length=300, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'revisión de identidad'
        verbose_name_plural = 'revisiones de identidad'
        ordering = ['-fecha', '-id']
