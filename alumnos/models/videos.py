"""Videos que el profesor le compartió a un alumno (agregado de videos, fase 3).

El archivo vive en MongoDB (GridFS, ver user_profesor/videoteca.py); aquí solo queda quién lo recibe y cuándo.
Cuelga del paquete: cuando el paquete vence, el alumno deja de verlos. Si el alumno es menor, ademas su apoderado
tiene que habilitar cada video. Si soporte retira uno por un reclamo (fase 5), deja de verse, de pagarse y de ocupar
cupo: por eso casi todo usa entregados(). La regla de no repetir un video al mismo alumno cuenta tambien los retirados.
"""

from datetime import timedelta

from django.db import models

from .. import paquetes
from .pagos import PaqueteClases, Suscripcion


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


class CompraVideosExtra(models.Model):
    """Videos comprados despues de contratar el paquete (fase 6, politica seccion 12). Un pago de Webpay propio.

    Como el paquete: nace pendiente al iniciar Webpay y solo vale cuando Transbank aprueba. El profesor tiene
    DIAS_ENTREGA_EXTRA desde el pago confirmado para compartirlos. Las reglas estan en alumnos/videos_extra.py.
    """
    ESTADO_PENDIENTE = Suscripcion.ESTADO_PENDIENTE
    ESTADO_ACTIVA = Suscripcion.ESTADO_ACTIVA
    ESTADO_RECHAZADA = Suscripcion.ESTADO_RECHAZADA

    paquete = models.ForeignKey(PaqueteClases, on_delete=models.CASCADE, related_name='compras_videos_extra')
    cantidad = models.PositiveSmallIntegerField()
    monto = models.PositiveIntegerField()  # lo pagado: con la promocion si corresponde
    buy_order = models.CharField(max_length=26, db_index=True)
    token_ws = models.CharField(max_length=100, blank=True, db_index=True)
    estado = models.CharField(max_length=10, choices=Suscripcion.ESTADOS, default=ESTADO_PENDIENTE)
    creada = models.DateTimeField(auto_now_add=True)
    codigo_autorizacion = models.CharField(max_length=20, blank=True)
    fecha_pago = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creada']

    def __str__(self):
        return f'{self.cantidad} extra -> {self.paquete} ({self.get_estado_display()})'

    @property
    def fecha_limite(self):
        """Hasta cuando el profesor debe compartirlos; None mientras el pago no se confirme."""
        if not self.fecha_pago:
            return None
        return self.fecha_pago + timedelta(days=paquetes.DIAS_ENTREGA_EXTRA)
