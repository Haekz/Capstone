"""Videos que el profesor le compartió a un alumno (agregado de videos, fase 3).

El archivo vive en MongoDB (GridFS, ver user_profesor/videoteca.py); aquí solo queda quién lo recibe y cuándo.
Cuelga del paquete: cuando el paquete vence, el alumno deja de verlos. Si el alumno es menor, ademas su apoderado
tiene que habilitar cada video. Si soporte retira uno por un reclamo (fase 5), deja de verse, de pagarse y de ocupar
cupo: por eso casi todo usa entregados(). La regla de no repetir un video al mismo alumno cuenta tambien los retirados.
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

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
    # Si pago el apoderado de un menor: quien y con que vinculo, como en CompraApoderado de los paquetes. SET_NULL: si
    # se borra la cuenta o el vinculo, la evidencia del pago queda.
    apoderado = models.ForeignKey('apoderados.Apoderado', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='compras_videos_extra')
    vinculo = models.ForeignKey('apoderados.Vinculo', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='compras_videos_extra')

    class Meta:
        ordering = ['-creada']

    def __str__(self):
        return f'{self.cantidad} extra -> {self.paquete} ({self.get_estado_display()})'

    @classmethod
    def confirmar_pago(cls, buy_order, aprobado, codigo_autorizacion='', fecha_pago=None):
        """Activa o rechaza la compra pendiente de la orden. Devuelve las que ESTA llamada dejo activas.

        Idempotente: solo toca las pendientes (el UPDATE condicional decide quien gana si dos retornos llegan juntos), asi
        un retorno repetido, o un rechazo tardio, no pisa lo ya resuelto y el aviso al profesor sale una sola vez.
        """
        pendientes = cls.objects.filter(buy_order=buy_order, estado=cls.ESTADO_PENDIENTE)
        if not aprobado:
            pendientes.update(estado=cls.ESTADO_RECHAZADA)
            return []
        fecha_pago = fecha_pago or timezone.now()
        activadas = []
        for compra in pendientes.select_related('paquete__profesor__user', 'paquete__alumno__user'):
            if cls.objects.filter(pk=compra.pk, estado=cls.ESTADO_PENDIENTE).update(
                    estado=cls.ESTADO_ACTIVA, codigo_autorizacion=codigo_autorizacion, fecha_pago=fecha_pago):
                compra.estado, compra.codigo_autorizacion, compra.fecha_pago = (
                    cls.ESTADO_ACTIVA, codigo_autorizacion, fecha_pago)
                activadas.append(compra)
        return activadas

    @property
    def fecha_limite(self):
        """Hasta cuando el profesor debe compartirlos; None mientras el pago no se confirme."""
        if not self.fecha_pago:
            return None
        return self.fecha_pago + timedelta(days=paquetes.DIAS_ENTREGA_EXTRA)


class DevolucionVideos(models.Model):
    """Dinero que se le devuelve al alumno por videos que el profesor no entrego (fase 6e, decidido 09-nov).

    Soporte la registra desde el ticket de Videos. Primero se intenta devolver por Transbank (alumnos/reembolsos.py); si
    no se puede, se transfiere a mano y eso lo aprueba un administrador antes (13-nov). ``monto`` lo calcula el servidor
    (alumnos/devoluciones_videos.py); ``devuelta`` queda cuando el dinero salio, sea por Transbank o a mano. SET_NULL:
    si se borra el ticket o la cuenta del agente, la evidencia queda.
    """
    paquete = models.ForeignKey(PaqueteClases, on_delete=models.CASCADE, related_name='devoluciones_videos')
    cantidad = models.PositiveSmallIntegerField()
    monto = models.PositiveIntegerField()  # pesos chilenos
    ticket = models.ForeignKey('soporte.Ticket', on_delete=models.SET_NULL, null=True, related_name='devoluciones_videos')
    registrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    creada = models.DateTimeField(auto_now_add=True)
    devuelta = models.DateTimeField(null=True, blank=True)  # vacio = por devolver
    # Por que fallo el ultimo intento de reembolso automatico por Transbank (alumnos/reembolsos.py); lo lee soporte.
    error_reembolso = models.CharField(max_length=200, blank=True)
    # Transferencia a mano: soporte la pide (escalamiento al admin) y el admin la aprueba; sin aprobacion no se transfiere.
    escalamiento = models.ForeignKey('soporte.Escalamiento', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='devoluciones_videos')
    aprobada = models.DateTimeField(null=True, blank=True)
    aprobada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+')

    class Meta:
        ordering = ['-creada', '-id']
        constraints = [models.CheckConstraint(condition=models.Q(cantidad__gt=0), name='devolucion_videos_cantidad_positiva')]

    def __str__(self):
        return f'{self.cantidad} video(s) sin entregar -> {self.paquete} (${self.monto})'

    @property
    def por_devolver(self):
        """Lo que falta devolver a mano: el monto menos lo que Transbank ya reembolso (confirmado)."""
        reembolsado = self.reembolsos.filter(confirmado__isnull=False).aggregate(total=models.Sum('monto'))['total']
        return self.monto - (reembolsado or 0)


class ReembolsoTransbank(models.Model):
    """Una devolucion hecha por Transbank sobre UNA transaccion (el agregado va en la del paquete; cada extra, en la suya).

    Se crea ANTES de llamar a Transbank y ``confirmado`` se llena al responder: la unicidad (devolucion, token) hace que
    dos intentos a la vez, o uno que se cayo a la mitad, nunca devuelvan dos veces. Un registro sin confirmar es una
    devolucion que hay que verificar en Transbank antes de repetir. Ver alumnos/reembolsos.py.
    """
    devolucion = models.ForeignKey(DevolucionVideos, on_delete=models.CASCADE, related_name='reembolsos')
    token_ws = models.CharField(max_length=100)
    monto = models.PositiveIntegerField()  # pesos chilenos
    tipo = models.CharField(max_length=10, blank=True)  # REVERSED o NULLIFIED, segun responde Transbank
    codigo_autorizacion = models.CharField(max_length=20, blank=True)  # una reversa no lo trae
    creado = models.DateTimeField(auto_now_add=True)
    confirmado = models.DateTimeField(null=True, blank=True)  # vacio = pedido sin respuesta todavia

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['devolucion', 'token_ws'], name='reembolso_unico_por_devolucion_y_transaccion'),
            models.CheckConstraint(condition=models.Q(monto__gt=0), name='reembolso_transbank_monto_positivo'),
        ]

    def __str__(self):
        return f'${self.monto} -> {self.token_ws[:8]}... ({self.tipo or "sin confirmar"})'
