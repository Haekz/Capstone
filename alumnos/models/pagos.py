"""Pagos de alumnos: suscripciones y paquetes de clases (Webpay)."""

from datetime import timedelta
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone

from .. import paquetes
from .usuarios import Alumno, Profesor


class SuscripcionQuerySet(models.QuerySet):
    def vigentes(self):
        return self.filter(estado=Suscripcion.ESTADO_ACTIVA, fecha_fin__gt=timezone.now())


def _activar_pendientes(modelo, buy_order, aprobado):
    """Activa o rechaza los pagos pendientes de una orden de Webpay (Suscripcion o PaqueteClases).

    Idempotente: si Webpay vuelve dos veces, la segunda no encuentra pendientes.
    """
    pendientes = modelo.objects.filter(buy_order=buy_order, estado=modelo.ESTADO_PENDIENTE)
    if not aprobado:
        pendientes.update(estado=modelo.ESTADO_RECHAZADA)
        return
    ahora = timezone.now()
    for pago in pendientes:
        pago.estado = modelo.ESTADO_ACTIVA
        pago.fecha_fin = ahora + timedelta(days=pago.dias)
        pago.save(update_fields=['estado', 'fecha_fin'])


class Suscripcion(models.Model):
    """Plan contratado por un alumno.

    Nace pendiente al iniciar Webpay y solo se activa cuando Transbank aprueba
    el pago (se busca por buy_order: la vuelta desde Webpay puede llegar sin la
    cookie de sesion). Es la unica fuente de verdad del plan: nada de localStorage.
    """
    # Codigos de plan que envia el formulario de planes.html.
    PLAN_BASICO = '1'
    PLANES = [
        (PLAN_BASICO, 'Plan Básico'),
        ('2', 'Plan Medio'),
        ('3', 'Plan Superior'),
        ('5', 'Plan Personalizado'),
    ]
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_ACTIVA = 'activa'
    ESTADO_RECHAZADA = 'rechazada'
    ESTADOS = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_ACTIVA, 'Aprobado'),
        (ESTADO_RECHAZADA, 'Rechazado'),
    ]

    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='suscripciones')
    plan = models.CharField(max_length=2, choices=PLANES)
    dias = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    monto = models.PositiveIntegerField()
    buy_order = models.CharField(max_length=26, db_index=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ESTADO_PENDIENTE)
    creada = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    objects = SuscripcionQuerySet.as_manager()

    class Meta:
        verbose_name = 'Suscripción'
        verbose_name_plural = 'Suscripciones'
        ordering = ['-creada']

    def __str__(self):
        return f'{self.get_plan_display()} - {self.alumno} ({self.get_estado_display()})'

    @property
    def es_premium(self):
        return self.plan != self.PLAN_BASICO

    @classmethod
    def confirmar_pago(cls, buy_order, aprobado):
        """Activa o rechaza las suscripciones pendientes de la orden."""
        _activar_pendientes(cls, buy_order, aprobado)


class PaqueteClasesQuerySet(models.QuerySet):
    def vigentes(self):
        return self.filter(estado=PaqueteClases.ESTADO_ACTIVA, fecha_fin__gt=timezone.now())


class PaqueteClases(models.Model):
    """Paquete Flexible, Progreso o Intensivo comprado a un profesor (ver alumnos/paquetes.py).

    Nace pendiente al iniciar Webpay y solo se activa cuando Transbank aprueba.
    Plan, clases, tarifa y monto quedan fijos al comprar: si el profesor cambia
    su tarifa, lo ya vendido no cambia. Cada inscripcion activa consume una
    clase; al cancelarla vuelve, porque las usadas se cuentan, no se restan.
    """
    ESTADO_PENDIENTE = Suscripcion.ESTADO_PENDIENTE
    ESTADO_ACTIVA = Suscripcion.ESTADO_ACTIVA
    ESTADO_RECHAZADA = Suscripcion.ESTADO_RECHAZADA

    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='paquetes')
    # SET_NULL: si se borra el profesor, el pago queda en el historial.
    profesor = models.ForeignKey(Profesor, on_delete=models.SET_NULL, null=True, related_name='paquetes_vendidos')
    plan = models.CharField(max_length=10, choices=paquetes.CHOICES)
    clases = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    tarifa = models.PositiveIntegerField()
    monto = models.PositiveIntegerField()
    dias = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    buy_order = models.CharField(max_length=26, db_index=True)
    estado = models.CharField(max_length=10, choices=Suscripcion.ESTADOS, default=ESTADO_PENDIENTE)
    creada = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    objects = PaqueteClasesQuerySet.as_manager()

    class Meta:
        verbose_name = 'Paquete de clases'
        verbose_name_plural = 'Paquetes de clases'
        ordering = ['-creada']

    def __str__(self):
        return f'{self.get_plan_display()} - {self.alumno} ({self.get_estado_display()})'

    @property
    def clases_usadas(self):
        return self.inscripciones.consumidas().count()

    @property
    def clases_disponibles(self):
        return max(0, self.clases - self.clases_usadas)

    @property
    def precio_por_clase(self):
        return self.monto // self.clases

    @classmethod
    def confirmar_pago(cls, buy_order, aprobado):
        _activar_pendientes(cls, buy_order, aprobado)
